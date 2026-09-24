# test-186 — capture one real 13-14 s stall with the RPMh timeout diagnostic on

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
`ring_summary`, `holder_tcs`, `irq_status`, soft-lockup/DPU/MMC counts, and a
verdict.

## Success / failure criteria

* Valid only if the preflight shows `rpmh_debug=1`, `heavy=0`,
  `flight=inactive`, `mirror=inactive`.
* Evidence of the RPMh layer: the dump's `ring_summary` and `holder_tcs` lines
  say whether the request was programmed without completing, completed but was
  not observed, or never reached programming.
* An anomaly printed *before* the first `gts9-rpmh: TIMEOUT` means RPMh is a
  victim: follow that anomaly instead, per the plan's decision tree.
* No stall in any round → record **"not reproduced this round"**. It is not
  evidence that anything was fixed, and it is not a reason to change code or
  add more instrumentation.
