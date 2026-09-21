# Test 025 — every hardware step behind a timeout (2026-09-21T14:49:11Z)

Every command in `/init` that touches hardware is wrapped in `timeout` now:
the RTC write, the mounts, the copy, the GPT reads and the raw report write.
The point was to stop a stalled step from blocking the report and the proof,
which is what tests 021-024 looked like from the outside.

Artifacts: `boot ba948a93…` (unchanged from test 024), `init_boot 52aca5d8…`,
`vendor_boot 139e0f5d…` (proof action back to `poweroff`).

## Result: the timeout does not help, and that is the finding

The gadget came up on the host at 14:49:49Z and **stayed** for the next eight
minutes: the proof never fired, and the card kept test 020's report
(`dfbabbe0…`, identical to the file test 020 wrote), so `/init` never reached
the report either.  A `timeout` that cannot interrupt a step means the step is
sleeping uninterruptibly - and the two steps that hang are both SPMI **writes**:

- `RTC_SET_TIME` (busybox `hwclock -w`, and the same ioctl from TWRP returns
  EACCES before any write happens, i.e. the capability check is the only thing
  that stops it there),
- the SDAM reboot-mode write that `reboot recovery` performs in test 024.

Everything that *reads* through SPMI works: the PMIC GPIOs (card detect), the
RTC registers, the regulators, the ADC.  So the board's kernel blocks in an
uninterruptible SPMI write, and `/init` must not do one - see test 026, where
`gts9_rtc_report` is off again and `/proc/interrupts` plus the SPMI device list
go into the report for the next look at it.
