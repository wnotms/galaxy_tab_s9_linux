# test-188 — the shutdown series repeated on the post-hwspinlock kernel

Status: **run complete.** Six cycles, zero stalls, zero unattended resets. The
result is in `RESULT.md`; the raw round records are `shutdown-N-*.txt`, the
classifier's output is `classify-captures.txt`.

## Why this series exists

test-187's 16 clean shutdown cycles were all run on the **AOSS-QMP + IPCC**
kernel. Round 15 then enabled `CONFIG_HWSPINLOCK_QCOM`, which is not a cosmetic
change: it unbound the whole SMEM → smp2p → ADSP chain, so four more drivers now
bind and a remoteproc exists that did not exist during any of those 16 cycles.
Measured on the device afterwards:

```
qcom_smem / qcom_hwspinlock bound, smp2p-adsp, smp2p-cdsp, smp2p-modem bound,
remoteproc0 -> adsp state=offline
```

The failure under investigation is in the **shutdown** path (see
`test-187/on-device/STALL-SIGNATURE.md`). A change to which drivers exist changes
what shutdown has to do, so the old series can no longer be cited as evidence
about the current kernel. This series re-establishes it.

It is **profile A**: no command-line change, no flash, no partition write. The
kernel under test is the one already flashed:

| image | sha256 |
|---|---|
| `boot.img` | `bf6a02bbe19e9561be2bae6d691cbaad0c3871ed4efc3878b8f689f2af00bd3e` |
| `vendor_boot.img` (profile A) | `06902f993f6fe9b682686ab36ad956032a8f6a250e595a85e1d7ac82092f211f` |

## Why the new ADSP remoteproc is not a new shutdown hazard

The obvious worry is that binding `qcom_q6v5_pas` added a remoteproc that
shutdown now has to stop, and that a failed firmware load leaves it in a state
that hangs. Checked in the pinned source; it does not:

* `rproc_shutdown()` (`drivers/remoteproc/remoteproc_core.c:1979`) returns
  `-EINVAL` immediately unless the state is `RPROC_RUNNING` or `RPROC_ATTACHED`:

  ```c
  if (rproc->state != RPROC_RUNNING &&
      rproc->state != RPROC_ATTACHED) {
          ret = -EINVAL;
          goto out;
  }
  ```

  and the device reports `state=offline` — so there is nothing to stop.
* `qcom_scm_pas_shutdown()` is reached only from `qcom_pas_stop()`, which the core
  calls only from `rproc_stop()`, which is only reachable past that guard.
* the firmware request is asynchronous — `rproc_trigger_auto_boot()` uses
  `request_firmware_nowait()`, so a missing image fails in a work item and never
  blocks probe;
* **no remoteproc code registers a reboot notifier, a `.shutdown` callback or a
  syscore op.** `grep -rn "reboot_notifier\|register_reboot_notifier\|syscore_ops"`
  over `drivers/remoteproc/` matches nothing; the only `.shutdown` is
  `xlnx_r5_remoteproc.c`, which is not this platform. Neither does
  `drivers/firmware/qcom_scm.c` or `drivers/soc/qcom/`.

So the ADSP registration is measurable but inert at shutdown, and this series
tests it rather than assuming it.

## Three harness defects this round found and fixed

### The workqueue-stall metric could never read 0

`warm-rounds.sh` scored a stall with
`journalctl -b -k | grep -c "workqueue.*stall"`. `journalctl -b -k` includes the
`Kernel command line:` line, and this board's cmdline carries
`workqueue.panic_on_stall_time=45` — so the pattern matched the command line and
returned **1 on every boot**. Measured on the device:

```
OLDWQ=1   NEWWQ=0
```

The metric was therefore constant and useless. It now excludes the command-line
line and matches the real banner from `kernel/workqueue.c:7839`,
`BUG: workqueue lockup - pool`. All eight `journalctl`-based counts in this
runner were given the same command-line filter, because any of them could pick up
a same-named kernel parameter in future.

### The console harness could not run from this host at all

Fixed separately — see the `tests: run the console harness from the WSL host`
commit. Both `console-run.sh` and `console-watch.sh` are host-agnostic now.

### `systemd-shutdown` is not a reliable completion marker

The runner classifies a round on that one marker, and the USB gadget disappears at
exactly the moment systemd-shutdown starts printing: its count fell 3, 0, 2, 1, 1, 0
across this series, so rounds 2 and 6 came out `unknown-capture-empty` even though
round 2's device verdict says `clean-shutdown`. `classify-captures.py` classifies
from the device's own `previous_boot_end`, from `reboot.target` (printed before the
handover), and from a calibrated open-port-silence measure. See `RESULT.md`.

## One more defect: the capture was ~99% PowerShell stack traces

`console-run.ps1` caught only `TimeoutException` around `ReadLine()`. When the
tablet reset, the port closed and every iteration wrote a full PowerShell error
record, so each round's trigger capture reached ~2 MB — 41 649 lines for round 1,
of which 9 were console output. The same defect is why test-184's
`probe-A-5-raw.txt` is 24 608 lines of noise, and it is part of why nobody read
that file for five rounds.

The script now logs the failure once, keeps reading in case the port returns, and
re-arms the message on the next line that arrives. The already-captured trigger
files were pruned to the console-run lines only, with the original size recorded
in each file's header; 15 MB became 472 KB. Nothing else was altered.

## What each round records

Per round, in `shutdown-N-verdict.txt`:

| field | why |
|---|---|
| `systemd_shutdown_seen` | **the decisive one.** Its absence on a boot that *started* shutting down is the failure found in round 7 |
| `panic_lines`, `softlockup_lines`, `hardlockup_lines`, `hungtask_lines`, `rcu_lines`, `calltrace_lines` | the watchdog verdicts, from the COM19 capture held across the reset |
| `connection_terminated`, `sd_shutting_down` | distinguishes "never began shutting down" from "began and never finished" |
| `ctxfault_lines` | the early SMMU faults, counted from the same capture |
| `burst_lines` | the deferred-probe burst the round-11 analysis says is not sufficient |

Per round, in `probe-N.txt`, from the device itself: `BID`, `UP`, `GPU`, `DEF`,
`CTXFAULTS`, `CTXSID`, `ADSP`, `PFW`, `ACD`, `DROP`, `RCGWARN`, `SL`, `HT`,
`RCU`, `WQ`, `RPMH`, `DPU`, `MMC`, `BURST`, `FAILED`.

`CTXFAULTS`/`CTXSID` are new here so that the claim in
`docs/EARLY_SMMU_CONTEXT_FAULTS.md` — that every early SMMU context fault on this
port is `SID=0x1c00`, the MDSS — is re-measured every round instead of asserted
once.

A round is only accepted if a **command executed**, not merely echoed: the
liveness probe requires `GTS9_ALIVE_<uptime>_END` as *output*. Echo without
execution is the stall state itself, not a clean round.

## Honest labelling

Every cycle is a **warm reboot** issued over the console. These are not cold
boots and no cold-boot claim is made anywhere; a cold boot needs the power button
and cannot be captured while USB is attached (the tablet powers on from VBUS —
see `test-187/on-device/COLD-BOOT-CONSTRAINT.md`).

There is still **no pre-fix rate**, so this series bounds the failure rate on the
current kernel; it cannot by itself prove the fix. That limitation is unchanged
and is stated in `test-187/on-device/SHUTDOWN-SERIES-RESULT.md`.

## Reproducing

```sh
reference/boot-tests/test-188-*/shutdown-series.sh              # dry run: preflight only
GTS9_ALLOW_POWER=1 GTS9_ROUNDS=6 reference/boot-tests/test-188-*/shutdown-series.sh
```

Environment: `GTS9_ROUNDS` (default 6), `GTS9_WINDOW` seconds of COM19 capture per
round (default 300), `GTS9_SHELL_PORT` (COM17), `GTS9_CONSOLE_PORT` (COM19).
