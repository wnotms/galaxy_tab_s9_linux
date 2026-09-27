# Diagnostic-only kernel patches

These patches are retained for targeted experiments and are not applied by
`scripts/prepare-kernel.sh`. The default patch queue is `kernel/patches/*.patch`;
subdirectories are intentionally ignored except for the explicit
`GTS9_POWEROFF_TRACE=1` opt-in documented below.

## `0008-i2c-qcom-geni-log-bus-lines-on-error.patch` — DIAGNOSTIC ONLY

This temporarily raised Qualcomm GENI I2C NACK/timeout logs and printed FIFO,
IRQ, and `SE_GENI_IOS` state. It helped distinguish a real address NACK from a
bus whose lines were not idle during Pogo bring-up. The default Pogo path no
longer depends on those measurements, and changing log levels in the shared
GENI controller adds noise for every device on the system.

For a one-off measurement, first prepare a disposable kernel worktree, then
apply this patch manually and rebuild:

```sh
scripts/prepare-kernel.sh <worktree>
git -C <worktree> apply <repo>/kernel/patches/diagnostic/0008-i2c-qcom-geni-log-bus-lines-on-error.patch
```

Running `prepare-kernel.sh` again restores the pinned source and reapplies only
the default queue.

## `0020-gts9-poweroff-path-trace.patch` — DIAGNOSTIC ONLY

This patch adds command-line-gated markers around Linux poweroff stages and
the registered sys-off callbacks. With `gts9_poweroff_trace=1`, it identifies
the callback symbol and priority, and prints immediately before PSCI
`SYSTEM_OFF`; if firmware returns, it prints the returned value. The PSCI
marker is flushed before the call, adding up to one second to this diagnostic
poweroff attempt. It does not change the default kernel or the poweroff
handler. The early-boot flag is default-off.

Prepare and build it in a disposable worktree and output directory:

```sh
GTS9_POWEROFF_TRACE=1 \
KERNEL_WORKTREE="$PWD/.work/build/linux-src-poweroff-trace" \
KERNEL_BUILD_DIR="$PWD/.work/build/linux-out-poweroff-trace" \
KERNEL_OUT_DIR="$PWD/out/kernel-poweroff-trace" \
scripts/build-kernel.sh
```

Package with `boot/cmdline.poweroff-trace.example.txt`. It enables the initramfs
report trace, kernel poweroff trace, and framebuffer console while keeping
`ttyMSM0` last as `/dev/console`. Re-running `prepare-kernel.sh` with the
default environment resets the diagnostic changes and restores the ordinary
patch queue.

## `0021-gts9-rpmh-timeout-state-dump.patch` — DIAGNOSTIC ONLY

Opt-in with `GTS9_RPMH_DEBUG=1` (the only diagnostic patch besides 0020 that
`scripts/prepare-kernel.sh` will apply) and inert at runtime unless the command
line carries `gts9_rpmh_debug=1`.

Why it exists: the earliest anomaly captured in a real 13-14 s stall is an
ACTIVE_ONLY RPMh transaction timing out in `rpmh_write_batch()`
(`drivers/soc/qcom/rpmh.c`, the `WARN_ON(1)` after `RPMH_TIMEOUT_MS`). That
warning says *that* it timed out, not *where* it stopped. This patch answers the
next question — client, TCS claim, TCS programming, trigger, RSC, IRQ,
`tcs_tx_done`, `rpmh_tx_done` or the completion — from captured state.

Cost and scope:

* the normal path gains one predictable branch on send and on completion
  (`if (unlikely(gts9_rpmh_debug))`), nothing else;
* a 128-entry, 20-byte ring of send/completion events lives in RAM (2.5 KiB,
  no allocation, no I/O, no per-event print, no continuous tracing);
* **only a real timeout prints**: one structured dump with the calling task,
  RSC name, state, every command's addr/data/wait, `tcs_in_use`, the RSC IRQ
  status, the per-TCS `CMD_ENABLE`/`CMD_MSGID`/`CMD_ADDR`/`CMD_DATA` registers,
  whether the request is still stashed in a `tcs->req[]` slot, the ring tail and
  a `ring_summary` line that states whether a matching completion was seen;
* the request is remembered after the timeout, so a completion that arrives
  later prints `LATE COMPLETION ... the rpmh_write_batch() lifetime hazard is
  real`. This only *reports* the hazard the existing code comments warn about
  (analysis in `docs/NEXT_STALL_DEBUG_PLAN.md` §3a: `tcs->req[]` is cleared only
  by `tcs_tx_done()`, so a late interrupt would touch a freed request); it does
  not change the lifetime or the semantics, and no fix is bundled;
* all output is prefixed `gts9-rpmh:` so a harness can extract it;
* the patch is **purely additive** - it removes no upstream line, so it cannot
  have changed the warning, the free, the return path or the timeout value.

Build and package:

```sh
GTS9_RPMH_DEBUG=1 \
KERNEL_WORKTREE="$PWD/.work/build/linux-src-rpmh-debug" \
KERNEL_BUILD_DIR="$PWD/.work/build/linux-out-rpmh-debug" \
KERNEL_OUT_DIR="$PWD/out/kernel-rpmh-debug" \
scripts/build-kernel.sh
```

Package with `boot/cmdline.rpmh-debug.example.txt` (watchdog detectors plus
`console=ttyGS1` and `gts9_rpmh_debug=1`; the kmsg mirror and the DPU ftrace
stream stay off). Re-running `prepare-kernel.sh` without `GTS9_RPMH_DEBUG=1`
drops the patch again.

## `0010-pinctrl-report-pogo-pin-state-at-probe.patch` — DIAGNOSTIC ONLY

This sampled TLMM registers for GPIO10, 12, 13, 62, 72, 75, and 106 at probe,
then logged another sample every 30 seconds forever. It helped inspect pin
ownership while bringing up the board, but the Pogo driver does not consume
these samples: the patch only reads and logs MMIO state. Its periodic worker
also changes generic Qualcomm pinctrl code for every board using that driver,
so it is excluded from the default build.

For a one-off measurement, apply the patch manually to a disposable prepared
kernel worktree and rebuild:

```sh
scripts/prepare-kernel.sh <worktree>
git -C <worktree> apply <repo>/kernel/patches/diagnostic/0010-pinctrl-report-pogo-pin-state-at-probe.patch
```

Running `prepare-kernel.sh` again restores the pinned source and reapplies only
the default queue.

## `0022-gts9-lastactivity.patch` — DIAGNOSTIC ONLY

Opt in with `GTS9_DIAGNOSTIC_PATCHES=0022-gts9-lastactivity.patch` and
`gts9_lastactivity=1`; package with boot/cmdline.lastactivity.example.txt.
The early-init, X710-only observer stores last positive IPI/CSD activity in
six cells per CPU, with counts, timestamps and raw addresses. Nested writers
are counted and skipped; a frozen snapshot marks racing CPUs invalid without
waiting on them. The first RCU stall or root write of 1 to
`/sys/module/gts9_lastactivity/parameters/dump` emits one bounded snapshot and
stops recording. No complete history or missing-event inference is supported.
See test-230's preregistration and scripts/lastactivity-evidence.py. This changes
tracepoint static keys during initialization and adds callback overhead, so it
is a diagnostic instrument, not a production fix for CPU non-response.

## `0023-gts9-ramoops-live-readback.patch` — DIAGNOSTIC ONLY

Test-233 retained a known binary pmsg record with 464 changed bytes. This patch
adds a root-only, read-only `gts9_pmsg_live` bin attribute on the existing
ramoops device, only on X710 and only with `ramoops.gts9_live_read=1`.
It maps no new RAM and changes no writer, geometry, ECC or reset behavior.
Stop PMSG writers and require two equal reads; it is not an atomic snapshot.
`scripts/pstore-probe.py check --raw-ring` decodes the pinned ARM64 ECC=0 ring
and requires the exact expected payload. Never use that decoder for an ECC
layout without updating the capacity calculation. The attribute is removed
before freeing the backing mapping. Build with
`GTS9_DIAGNOSTIC_PATCHES=0023-gts9-ramoops-live-readback.patch` and use
`boot/cmdline.ramoops-live.example.txt`. Test-234 preregisters the trial.

## `0024-gts9-ramoops-ecc64.patch` — DIAGNOSTIC ONLY

Adds upstream `ecc-size = <64>` to the existing X710 ramoops DT node for an
isolated integrity trial after tests 233/234. Default 128-byte blocks plus
64 parity symbols fit the Reed–Solomon field. At most 32 erroneous symbols
per block can be corrected; parity corruption and layout changes matter.
Reserved region/zone sizes and mem-type remain unchanged, but usable capacity
shrinks. Source and observer must have the same ECC layout. Old ECC=0 data is
incompatible; do not treat first-boot correction errors as this trial's result.

Select only `GTS9_DIAGNOSTIC_PATCHES=0024-gts9-ramoops-ecc64.patch`, retain the
production cmdline/config, and require exact identified bytes after reboot.
See test-235's preregistration. This is not a CPU fix or crash-retention proof.
