# test-060 — thirty seconds of silence and a side-effect-free poll: still no answer

- started: 2026-09-22T08:00:00Z
- source commit: `6462158` ("pogo: leave the MCU completely alone while its
  application starts")
- images: `boot.img ae45f240…`; vendor_boot/init_boot/dtbo unchanged
- authorization: standing device-test authorisation recorded for tests 046-059

## What it separates

Whether the application is alive but kept from answering by this driver's own
early activity. Every poll window until now carried side effects: the first
failure called `pogo_recover_bus()`, which bit-bangs nine clocks plus a STOP on
SCL/SDA and switches the controller's pinmux, and the failure path scanned every
address. Test 057's silent-window result was never captured, so neither silence
nor side-effect-free polling had ever been measured.

Change: after powering the MCU up with BOOT0 low, `connect_work` waits 30 s
without touching the bus, the pins, NRST or `0x51`, then polls `CHECK_VERSION`
with a window that itself has no side effects; the recovery bit-bang and the bus
scan run only after both poll windows and the bootloader visit have failed.

## Result — disproved

```
[    4.100977] samsung-pogo-keyboard 5-002a: MCU rail on with BOOT0 low
[    4.123272] samsung-pogo-keyboard 5-002a: leaving the MCU alone for 30000 ms
[   36.130264] samsung-pogo-keyboard 5-002a: silent window over; connect line 0
[   36.143371] samsung-pogo-keyboard 5-002a: waiting up to 60000 ms for the MCU application
[   99.612028] samsung-pogo-keyboard 5-002a: no answer from the MCU application after 60000 ms (-6)
[   99.707754] samsung-pogo-keyboard 5-002a: MCU application did not answer; entering its bootloader
[   99.845705] MCU bootloader took the 0xFF sync / version 0x12 / IC version 00340034
[  100.086692] after the disconnected reset: application -6, bootloader -6, connect 1
```

Thirty seconds of complete silence and sixty seconds of polling that changed
nothing on any pin produced no answer at `0x2a`, while the bootloader answered
first try. This driver's early activity is not what keeps the application quiet,
and the follow-up question — is the application running at all — is what test 061
asks passively on the announce line.
