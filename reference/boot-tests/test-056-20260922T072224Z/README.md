# test-056 — the MCU powered up in stock's order, and it changed nothing

- started: 2026-09-22T07:22:24Z
- source commit: `9c9808e` ("pogo: power the MCU up after its pins, the way the
  stock driver does")
- images: `boot.img 08c53526…`, `vendor_boot baac5dc5…` (both carry the changed
  DTB); `init_boot 12b77d17…`, `dtbo c17418be…` unchanged
- authorization: standing device-test authorisation recorded for tests 046-055

## Hypothesis

Stock reaches a working application without ever entering the bootloader (test
055), and it switches the rail in `stm32_interrupt_init()` - after the driver
owns gpio12 (SWCLK/BOOT0) and gpio13 (NRST) - while mainline drove gpio10 high
from the regulator's pinctrl default state, before those pins were configured.
If this part latches its boot source at power-on, that ordering alone would
explain every measurement since test 046.

Change: `pogo_supply` no longer drives gpio10; `connect_work` powers the MCU up
as SWCLK low, NRST asserted, rail on, NRST released, and only then polls.

## Result — disproved

```
[    3.987325] input: Book Cover Keyboard Slim (EF-DX710) as .../5-002a/input/input0
[    4.425486] samsung-pogo-keyboard 5-002a: MCU powered up with BOOT0 low and NRST released
[    4.492811] samsung-pogo-keyboard 5-002a: waiting up to 60000 ms for the MCU application
[   68.511861] samsung-pogo-keyboard 5-002a: no answer from the MCU application after 60000 ms (-6)
[   68.586161] samsung-pogo-keyboard 5-002a: MCU application did not answer; entering its bootloader
[   68.723862] samsung-pogo-keyboard 5-002a: MCU bootloader took the 0xFF sync
[   68.740627] samsung-pogo-keyboard 5-002a: MCU bootloader version 0x12
[   68.753287] samsung-pogo-keyboard 5-002a: MCU IC version 00340034
[   68.804367] samsung-pogo-keyboard 5-002a: MCU option bytes 0xfefffeaa: RDP 0xaa, bit 24 clear
[   68.985581] samsung-pogo-keyboard 5-002a: after the disconnected reset: application -6, bootloader -6, connect 1
```

The ordered power-up ran, the application stayed silent for sixty seconds, and
the bootloader answered exactly as before. Power-on ordering is not the cause.
The official X710 DTS later settled it from the other side as well: stock's
`fixed_regulator@1` drives gpio10 high from its own pinctrl state at the
regulator's probe, so the stock part also powers up with BOOT0 and NRST
undriven - and still runs its application.
