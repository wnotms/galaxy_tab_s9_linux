# test-075 — the application's startup signals match stock's

- started: 2026-09-22T09:50:00Z
- source commit: `fbc8d1a`
- images: `boot.img 05c28b50…`; `vendor_boot 3ec6c8d1…`, `init_boot aed8f3c5…`,
  `dtbo c17418be…` unchanged
- authorization: standing device-test authorisation recorded for tests 046-074

## What this closes

Every in-driver comparison is now made. The last one was what the application
finds at the instant it starts - the rail as its power, SWCLK as its BOOT0, NRST
as its reset - and it matches what stock has at the same moment:

```
[    4.782067] just after the rail rose:                 rail on, boot0/swclk 0, nrst 1, announce 0
[    4.929008] at the moment stock's application speaks: rail on, boot0/swclk 0, nrst 1, announce 0
[    5.014095] right after the rail cycle: application -6, bootloader -6, announce level 0
```

Rail up, BOOT0 low, NRST released - the same three states the stock trace shows
when its application is running, and 130 ms later, the moment stock's application
speaks, they are unchanged. The announce line reads 0 in this boot and read 1 in
tests 067 and 074, which is consistent with a signal that is driven in bursts
rather than a steady level.

## Where the investigation stands

| layer | verdict | evidence |
| --- | --- | --- |
| pogo driver logic | not the fault | test 070's A/B: Samsung's own driver behaves the same |
| firmware path | reproduced value for value | test 072: checksum `0x7E2341C8`, `PID 0x460/0x12`, `skip - fw update` |
| application startup signals | identical to stock | this test |
| address, framing, bus rate, timing, power-on order, resets | excluded by measurement | tests 046-068 |
| the MCU's own state | powered and running, but its I2C slave serves **no** address | test 074's real probe: nothing acknowledges at 0x2a/0x2b/0x2c/0x2d/0x51 |

What remains is what the pogo path cannot show: the environment the rail itself
depends on and the controller's behaviour on the wire - the supply behind the
GPIO-switched rail (mainline's `vreg_pogo` models no parent), the pinctrl and
clock state of the serial engine, and the GENI driver's address phase. Each of
those is outside the driver that has now been compared exhaustively, and each is
measurable only from that layer: the rail's parent supply by registering it, the
engine's state from its own registers.
