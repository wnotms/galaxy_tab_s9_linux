# test-065 — the rail cycle produces an interrupt, but not an application

- started: 2026-09-22T08:45:00Z
- source commit: `c3b699e`
- images: `boot.img 9e0f212c…`; `vendor_boot 8d76f912…`, `init_boot 12b77d17…`,
  `dtbo c17418be…` unchanged
- authorization: standing device-test authorisation recorded for tests 046-064

## Hypothesis

From the captured stock cycle (`reference/twrp-pogo-working/bringup-cycle-dmesg.log`):
the MCU asserts its announce line 135 ms after the rail rises, with no host
transaction in between, and stock's own sequence at that moment is rail off,
410 ms, rail on, 50 ms, event IRQ enabled. Reproducing exactly that, and
servicing the interrupt instead of only observing it, should produce the
announcement that this port has never seen.

## Result — hypothesis disproved, and the interrupt was a false positive

```
[    4.792353] MCU rail on with BOOT0 low, announce line armed
[    4.792364] MCU announced itself (1)          <- 11 us after arming, not 135 ms later
[    4.848644] waiting up to 60000 ms for the MCU application
[   76.094034] no answer from the MCU application after 60000 ms (-6)
[   79.848620] application poll finished (-6), 1 announcement(s)
[   79.858185] MCU application did not answer; entering its bootloader
```

The interrupt arrived **11 µs** after the handler was armed, which is not an
announcement: the line is `IRQ_TYPE_LEVEL_LOW` with `bias-disable`, so arming it
while the line already reads low fires immediately. The handler then failed to
read an event, the 60 s poll never succeeded, and the model line never appeared -
so nothing here says the application is running, and the "1 announcement" counter
must not be read as a success.

The real content of this test is the contrast it exposes at the same line:

- stock, every status line: `int:1` - the announce line sits **high**;
- stock, when the application has something to say: the interrupt fires and the
  ISR reads a real event (`03 00 02`, model 0x2);
- mainline, after this rail cycle: the line reads **low** at arm time, and
  because it is `bias-disable` with no pull its idle level cannot be trusted
  either way - yet it is the one signal the MCU drives by itself.

Hypothesis disproved: stock's rail-cycle timing is not what starts the
application in mainline. The follow-up measurement is the line's *level* rather
than its interrupts - `int:1` in stock against an unknown in mainline - which the
next candidate reads from the irqchip (`IRQCHIP_STATE_LINE_LEVEL`) instead of
inferring it from firing.
