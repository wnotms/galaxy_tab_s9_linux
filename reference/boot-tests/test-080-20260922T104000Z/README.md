# test-080 — what the bootloader leaves in the pogo pins

- started: 2026-09-22T10:40:00Z
- source commit: `7c9eaf9` (patch 0010)
- images: `boot.img 7c7eebf1…`; `vendor_boot 7bd7dcf9…`, `init_boot aed8f3c5…`,
  `dtbo c17418be…` unchanged
- authorization: standing device-test authorisation recorded for tests 046-079

## What it asked

P3 of the plan, the last host-controlled item never measured: not the pins' final
states (they match stock, tests 055/064) and not any settable variable (excluded
in 075-079), but the *transition* - what the bootloader leaves in the pin control
registers before any driver owns the pins.

## Result — the handoff state, measured

```
[    2.987988] sm8550-tlmm f100000.pinctrl: pogo pin 10  (gpio10)  at probe: ctl 0x1 io 0x0
[    2.996839] sm8550-tlmm f100000.pinctrl: pogo pin 12  (gpio12)  at probe: ctl 0x1 io 0x0
[    3.005676] sm8550-tlmm f100000.pinctrl: pogo pin 13  (gpio13)  at probe: ctl 0x1 io 0x0
[    3.014513] sm8550-tlmm f100000.pinctrl: pogo pin 62  (gpio62)  at probe: ctl 0x1 io 0x0
[    3.023349] sm8550-tlmm f100000.pinctrl: pogo pin 72  (gpio72)  at probe: ctl 0x1 io 0x1
[    3.032183] sm8550-tlmm f100000.pinctrl: pogo pin 75  (gpio75)  at probe: ctl 0x1 io 0x0
[    3.041022] sm8550-tlmm f100000.pinctrl: pogo pin 106 (gpio106) at probe: ctl 0x1 io 0x1
```

Every one of the seven is left in mux function **1**, not GPIO (mux 0), and the
input bits read low except on the two controller lines (72 and 106, which read
high because the controller holds the bus idle).

Two things follow for the transition question:

* the MCU's **NRST reads low** at handoff, i.e. the part is held in reset from
  the bootloader until the keyboard driver applies its own pinctrl state - in
  mainline at ~4.7 s, in stock at ~1.6 s because its driver is a module loaded
  early. BOOT0 reads low, which is the app-mode level.
* before the driver probes, none of these pins is a GPIO: the board's bootloader
  hands them over in function 1 and the mainline pinctrl state only turns them
  into GPIOs when the keyboard driver is probed.

Neither is a difference from stock in kind - the same bootloader hands over the
same state, and stock's driver also applies the same pinctrl state - but this is
the first measurement of that window, and it narrows what a remaining transition
difference could be: only the *moment* the state is applied differs (1.6 s versus
4.7 s), because stock's driver is loaded as a module while this one is built in.

## Next step

Test the only difference this leaves: apply the pogo pin state as early as
mainline can, rather than at i2c probe time. If the MCU's reset line being
released at 1.6 s instead of 4.7 s matters, an early pin configuration shows it;
if it does not, the transition is closed like every other host-side item.
