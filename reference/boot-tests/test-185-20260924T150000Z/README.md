# test-185 — shutdown/reboot baseline with the heavy instrumentation off

Question: test-184 observed a ~3.5 minute shutdown while the DPU ftrace stream
was writing megabytes per second to the microSD, and a stale
`/etc/systemd/system/gts9-dpu-flight.service` meant the "off by default" flag
was not actually in effect then. With the flag now effective, does the slow
shutdown still happen?

Profile under test — the currently flashed image, detectors only:

```
gts9_watchdog_debug=1      detectors armed (watchdog OK)
gts9_kmsg_mirror           must be OFF
gts9_dpu_flight            must be OFF
ttyGS0                     login shell (gts9-acm-getty.service)
ttyGS1                     kernel console (console=ttyGS1)
```

## Running it

```sh
# preflight only (no power action is sent):
reference/boot-tests/test-185-*/shutdown-baseline.sh 3 reboot

# real measurement, explicitly authorised:
GTS9_ALLOW_POWER=1 reference/boot-tests/test-185-*/shutdown-baseline.sh 3 reboot
GTS9_ALLOW_POWER=1 reference/boot-tests/test-185-*/shutdown-baseline.sh 3 poweroff
```

The script never flashes and never writes a partition or the BCB. `poweroff`
leaves the tablet off: the harness waits for the operator to power it back on
and records that the return came from a human, not from the script.

## What each round records

boot_id before/after, `/proc/cmdline` flags, failed units, the command's issue
time, USB-gap start/end from both the shell and console captures, the previous
boot's shutdown journal tail (`journalctl -b -1 -o short-monotonic | tail -25`)
plus its stall-marker counts (workqueue stall, RCU stall, RPMh timeout, DPU
timeout, MMC timeout, soft lockup, hung task), watchdog state, DPU flight and
kmsg mirror service state, and ttyGS0/ttyGS1 state.

## Success / failure criteria

* The measurement is valid only if the preflight reports `flags=0`,
  `flight=inactive` and `mirror=inactive`; otherwise it is confounded and the
  script says so.
* "Slow shutdown reproduces" = USB-gap start to shell return in the multiple
  minutes range, with no stall markers in the previous boot's tail.
* "Slow shutdown does not reproduce" = sub-minute return in all rounds. That
  bounds the rate; it does **not** prove the recorder was the cause, and it is
  not a reason to touch PSCI/PMIC.
