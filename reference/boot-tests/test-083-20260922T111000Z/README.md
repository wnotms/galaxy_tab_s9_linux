# test-083 — gpio10 never goes high, and that has been true since test 058

- started: 2026-09-22T11:10:00Z
- source commit: `9de099e`
- images: `boot.img fa7f32d1…`; vendor_boot/init_boot/dtbo unchanged
- authorization: standing device-test authorisation recorded for tests 046-082

## What it measured

The plan's P3 ends on whether the pin the keyboard's rail switches is really
driven where the driver thinks it is. The diagnostic now samples the seven pogo
pins twice: at probe (what the bootloader left, test 080) and again every thirty
seconds, where the IO register shows the value the TLMM is driving as well as the
input bit.

## Result — pin 10 is low with the regulator enabled

```
[    2.988246] pogo pin 10 (gpio10) at probe: ctl 0x1 io 0x0
...
[   34.081264]   pin 10:  io 0x0     <- still low, with the rail "on"
[   34.085933]   pin 12:  io 0x0     BOOT0 low
[   34.090542]   pin 13:  io 0x3     NRST: output bit 1 and input bit 1, i.e. driven high
[   34.095146]   pin 62:  io 0x1
[   34.099747]   pin 72:  io 0x1     SCL idle high
[   34.104374]   pin 75:  io 0x1     announce line high
[   34.108979]   pin 106: io 0x1     SDA idle high
```

Pin 13 proves the register is readable as expected - this driver drives it high
and both bits show it. Pin 10 shows neither bit set while
`regulator_is_enabled(pogo-vdd)` is true, so **the regulator's enable has not
been reaching the pad**: the pin's pinconf state says `output-low` (a change made
in test 058, when the rail was deliberately kept low until the driver enabled it)
and it wins over the regulator's own write.

That means gpio10 has been low in **every test since 058** - including the vendor
port's complete firmware reproduction (test 072) and every read attempt since -
while in stock the same pin is high when the application answers.

## Why this is not the whole story, and why it still has to be fixed

Before test 058 the state was `output-high`, the pad was high (test 055 read
`gpio10: out high`), and the application was silent then too - so a low gpio10
cannot explain all of the history on its own. What has changed since is that
everything else about the stock path is now reproduced (test 072), so the pin's
failure to rise is the last known difference between the two systems on this
signal, and it must be fixed before any further conclusion can be drawn from a
read attempt.

## The fix, for the next test

One line: stop the pinconf from holding the pad down, so the fixed regulator's
own write decides it - either drop `output-low` from `pogo_supply` and let the
regulator own the level entirely, or set it to `output-high` as it was before
test 058. The measurement then repeats: if the pad goes high when the driver
enables the rail and `0x2a` answers, the fault is found; if the pad goes high and
`0x2a` still NACKs, then this configuration bug is fixed and the investigation
returns to the MCU's own state with one fewer unknown.
