# test-076 — with no bus traffic at all, the application announces itself

- started: 2026-09-22T10:00:00Z
- source commit: `1ed2712`
- images: `boot.img 2035f42f…`; vendor_boot/init_boot/dtbo unchanged
- authorization: standing device-test authorisation recorded for tests 046-075

## The measurement that had never been made cleanly

Five seconds of watching the MCU's own line every 100 ms after the rail rises,
with **not one byte** on the bus - earlier silent windows sampled only at their
end (test 060) or had already produced traffic (tests 068/075).

## Result — the application is alive and calls for attention by itself

```
[    3.575996] MCU rail on with BOOT0 low, announce line armed (level 0)
[    3.593097] just after the rail rose: rail on, boot0/swclk 0, nrst 1, announce 0
[    3.810104] announce line 0 -> 1 after 200 ms of silence
[    5.203952] announce line 1 -> 0 after 1000 ms of silence
[    9.497457] right after the rail cycle: application -6, bootloader -6, announce level 0
[    9.540062] waiting up to 60000 ms for the MCU application
```

With nothing driving it and nothing talking to it, the MCU takes its announce
line high 200 ms after the rail rises and releases it a second later. That is
the application running and asking to be read - unprompted, on a bus the host
has not touched.

This corrects the shape of the investigation once more. The question is no longer
"does the application start" (it does) and no longer "does it want to talk" (it
does): the host's read of that announcement is the whole fault.

## Two differences this also shows

* **The idle level and polarity differ from stock's.** Stock prints `int:1` as
  the resting level and its ISR fires when the line goes *low*; here the line
  rests low and the pulse is *high* - and it still rests low with the pull-up
  this port added (test 073), so something drives it low when idle.
* **The application's I2C slave answers nothing**, not even at 0x51, while the
  same peripheral answers perfectly in boot mode on the same controller. The
  probe of test 074 covered only 0x2a-0x2d and 0x51, so if the application
  serves a different address it was never in range.

## Next step

Scan the whole address range with the working probe (0x08-0x77) while the MCU is
signalling, not the five addresses test 074 tried. If the application serves
another address, that finds it; if the whole range is silent while its own line
is being pulsed, the slave itself is not participating and the difference is in
how the host's controller presents the address phase to it - the one layer still
uncompared, since stock runs i2c-msm-geni and mainline runs i2c-qcom-geni.
