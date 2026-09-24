# test-186 — capture one real 13-14 s stall with the RPMh timeout diagnostic on

> **NOT RUN. The files under `fixtures/` are synthetic, not captured.**
>
> This test has never been executed on the device: there is no `rounds/`
> directory and no capture exists. The three files in `fixtures/`
> (`victim.log`, `programmed-no-completion.log`, `no-anomaly.log`) were written
> by hand to pin the branches of `classify-round.sh`; the commit that added them
> says so ("Three synthetic fixtures pin the branches").
>
> They must **never** be cited as hardware evidence. A round-1 revision of
> `docs/GPU_GMU_RPMH_STALL_PLAN.md` did exactly that and had to be corrected —
> see that document's "Correction (round 2)" note and
> `tests/test_gpu_gmu_rpmh_stall.py::EvidenceProvenanceTests`. The timestamps in
> them (for example `13.400000`) appear nowhere else in this repository.
>
> When this test is eventually run, the real dumps go in `rounds/` and these
> fixtures stay fixtures.

Goal: reproduce a real stall with **exactly one** new variable compared with
test-184 profile A — the opt-in RPMh timeout state dump — and decide, from the
pre-agreed tree in `docs/NEXT_STALL_DEBUG_PLAN.md` §8, which layer of

```
client -> rpmh_write_batch -> rpmh_rsc_send_data -> TCS claim -> TCS program
       -> trigger -> RSC -> IRQ -> tcs_tx_done -> rpmh_tx_done -> completion
```

the transfer stopped in.

## Profile

```
gts9_watchdog_debug=1     detectors armed
gts9_rpmh_debug=1         the diagnostic (kernel patch 0021)
console=ttyGS1            kernel console captured on COM19
gts9_kmsg_mirror          OFF
gts9_dpu_flight           OFF
Pogo / PCIe / regulators / PMIC / panel recovery: untouched
```

Boot images needed (see the candidate summary in the round report):
`boot.img` with `CONFIG_U_SERIAL_CONSOLE` (unchanged, `2e8a693f…`),
`vendor_boot.img` built from `boot/cmdline.rpmh-debug.example.txt`, and the
kernel from `GTS9_RPMH_DEBUG=1 scripts/build-kernel.sh`.

## Running it

```sh
# preflight only, no boot issued:
reference/boot-tests/test-186-*/rpmh-stall-capture.sh 5

# real capture, explicitly authorised:
GTS9_ALLOW_POWER=1 reference/boot-tests/test-186-*/rpmh-stall-capture.sh 5
```

Never flashes; never writes a partition or the BCB.

## What is captured per round

The kernel console for the whole shutdown → boot → 13-14 s window, and then,
over the shell, the previous boot's kernel log filtered to
`gts9-rpmh|soft lockup|workqueue stall|rcu stall|frame done timeout|mmc
timeout|rpmh_write_batch` in monotonic order. Recorded per round: boot_id
before/after, the first anomaly by monotonic timestamp, the RPMh dump block
(`rounds/round-N-rpmh-dump.txt`), the timeout count, any `LATE COMPLETION`, the
`ring_summary`, `holder_tcs`, `irq_status`, soft-lockup/DPU/MMC counts, and the
branch from `classify-round.sh` (`docs/NEXT_STALL_DEBUG_PLAN.md` §8).

## Success / failure criteria

* Valid only if the preflight shows `rpmh_debug=1`, `heavy=0`,
  `flight=inactive`, `mirror=inactive`.
* Evidence of the RPMh layer: the dump's `ring_summary` and `holder_tcs` lines
  say whether the request was programmed without completing, completed but was
  not observed, or never reached programming.
* An anomaly printed *before* the first `gts9-rpmh: TIMEOUT` means RPMh is a
  victim: follow that anomaly instead, per the plan's decision tree.
* No stall in any round → the classifier prints `branch=no-anomaly`: record
  **"not reproduced this round"**. It is not evidence that anything was fixed,
  and it is not a reason to change code or add more instrumentation.
* `branch=victim-other-anomaly-earlier` means RPMh is a victim: follow the
  earlier anomaly, do not deepen the RPMh dump.
* `branch=rpmh-programmed-no-completion` → RSC/TCS/hardware-completion/IRQ;
  `branch=rpmh-irq-pending` → IRQ delivery/masking/CPU state;
  `branch=rpmh-completed-late` → the request-lifetime hazard of plan §3a is
  confirmed and a *separate* fix patch is the next discussion, not this one.
