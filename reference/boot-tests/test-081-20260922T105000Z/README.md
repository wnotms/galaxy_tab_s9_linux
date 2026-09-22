# test-081 — moving the pin state earlier cannot be done that way (reverted)

- started: 2026-09-22T10:50:00Z
- source commits: `c61cb7c` (the experiment) and `c6bc627` (its revert)
- images: the experiment's `boot.img e1257ebe…` / `vendor_boot.img 6078701261…`;
  the reverted build is byte-identical to test 080's `boot.img 7c7eebf1…` /
  `vendor_boot.img 7bd7dcf9…`
- authorization: standing device-test authorisation recorded for tests 046-080

## The hypothesis, and why the result is not about the MCU

Test 080 measured the one transition difference left: the bootloader hands the
pins over with the MCU's NRST low, and it is released when a driver applies the
board's pin state - ~4.7 s here, where the keyboard driver is built in, against
~1.6 s in stock, where it is a module loaded early. The experiment added
`pogo_swclk` and `pogo_nrst` to the rail regulator's pinctrl state, because the
regulator probes first.

## Result — the driver can no longer apply its own state

```
[    4.072872] stm32_pogo_i2c 5-002a: deferred_flag boot stm32_dev_probe
[    4.854547] stm32_pogo_i2c 5-002a: error -EINVAL: Error applying setting, reverse things back
```

The keyboard driver's own pinctrl application fails with `-EINVAL` and its probe
never completes: one pinctrl group cannot be applied by two devices. The
experiment therefore measured nothing about the MCU - and it left the driver
worse off than before, which is why it was reverted in full (`c6bc627`).

**The revert is exact**: the rebuilt images are byte-identical to test 080's
(`boot.img 7c7eebf1…`, `vendor_boot.img 7bd7dcf9…`), which is the working state
this project has been measuring with.

## What this leaves

The transition question is closed by construction rather than by measurement: the
pins can only be configured by the driver that owns them, so their state is
applied when that driver probes, and that is the earliest mainline can do it.
Nothing host-controlled remains that has not been measured or excluded:

| item | test |
| --- | --- |
| rail, BOOT0, NRST at startup | 075 |
| stock's firmware path, value for value | 072 |
| no early traffic; the application announces itself | 076 |
| real address probe over the whole range | 077 |
| both driver implementations | 070, 078 |
| bus rate at 100 and 400 kHz | 059, 079 |
| bootloader handoff state of all seven pins | 080 |
| moving the state earlier | 081 (this test) |
