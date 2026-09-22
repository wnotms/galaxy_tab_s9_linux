# test-082 — with nothing touched at all, the application is already running and calling

- started: 2026-09-22T11:00:00Z
- source commit: `8e00aa5`
- images: `boot.img 40af28f6…`; vendor_boot/init_boot/dtbo unchanged
- authorization: standing device-test authorisation recorded for tests 046-081

## Why this window

Every candidate so far enabled the rail before reading, and since test 058 the
rail's pinctrl state holds gpio10 low until this driver enables it - so the MCU's
supply appeared to be switched by the driver and nothing else. A part that was
already running and was disturbed by that enablement would look exactly like a
part that never starts.

Thirty seconds of touching nothing: no rail, no pin writes, no IRQ arming, only
the announce line read every 100 ms.

## Result — the application runs without this driver, and calls repeatedly

```
[   26.534207] no-action: announce 1 -> 0 after 20800 ms
[   27.165925] no-action: announce 0 -> 1 after 21400 ms
[   27.381924] no-action: announce 1 -> 0 after 21600 ms
[   28.013927] no-action: announce 0 -> 1 after 22200 ms
... a low pulse of about 200 ms every 600 ms, for the whole window
```

Two facts follow, and together they change the picture again:

1. **The MCU is not powered by gpio10.** With that pin held low by the driver's
   own pinctrl state and nothing else touched, the application still runs and
   drives its line - so the part has another supply, and gpio10 is something
   else: the most likely candidate is the level shifter between the AP and the
   keyboard, which is exactly what a rail that "has to be up for the MCU to
   answer" behaves like.
2. **The line's sense is inverted relative to stock.** Here it rests low and
   pulses high; stock prints `int:1` at rest and its ISR fires when the line goes
   low. A level shifter whose supply is missing is a plausible cause of both the
   inversion and the silence on I2C: an unpowered translator clamps or floats its
   outputs, so the host's transactions never reach the MCU - which is precisely
   the "nothing acknowledges at any address" of test 077.

## Next step

Measure the level gpio10 actually reaches once the driver has enabled it, rather
than trusting the regulator's own report: the TLMM diagnostic of test 080 shows
the pin's input bit at probe (low, as the bootloader left it), and a second
sample later in the boot says whether enabling the regulator really moves the
pin. If it does not - because the pin's pinctrl state says `output-low` and wins
over the regulator's write - then the level shifter has been off in every test
since 058, which would explain every NACK this project has recorded.
