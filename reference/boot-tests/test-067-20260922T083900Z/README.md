# test-067 — the announce line reads 1: the MCU is alive and in stock's state

- started: 2026-09-22T08:39:00Z
- source commit: `bbf3fbf`
- images: `boot.img 8c37beaf…` and `vendor_boot.img 4d496064…` (both carry the new
  DTB); `init_boot 12b77d17…`, `dtbo c17418be…` unchanged
- authorization: standing device-test authorisation recorded for tests 046-066

## Hypothesis

The announce line is the only signal the MCU drives by itself. Stock prints it as
`int:1` while its application runs; test 066 could not read it because this
platform's irqchip does not implement `IRQCHIP_STATE_LINE_LEVEL`. Samsung's node
hands the line over as a GPIO (`stm32,irq_gpio` + `gpio_to_irq`), so this
candidate claims it the same way and prints the level.

## Result — level 1, the same value stock reports

```
[    4.772818] MCU rail on with BOOT0 low, announce line armed (level 1)
[    4.772826] MCU announced itself (1)
```

Read through a gpiolib descriptor of the same pin, after the rail cycle and
before any host transaction, the line is **high** - exactly what stock's status
line prints as `int:1` while the keyboard works.

Two conclusions follow, and they change the question:

1. **The application is not "not running".** The MCU drives its own announce line
   high, which is the state stock shows when the keyboard is fully working, so
   under mainline the part is alive and in the same idle condition as under
   stock. Test 061's zero interrupts must be re-read in that light: a level-low
   line that stays **high** never fires, which is what "no announcement" meant
   there - not a dead application.
2. **The failure is at the interface, not in the MCU's state.** An alive MCU that
   leaves its announce line high nevertheless NACKs address `0x2a` while the bus
   is idle and the bootloader at `0x51` answers on the same controller (tests
   051/063). So the application interface, not the application, is what mainline
   is missing.

The interrupt that arrived together with the level read is a leftover pending
one from the rail cycle, not an announcement - the level, not the interrupt, is
the signal, and it is now a number that can be compared with stock's.

## Next step

Ask the MCU what it is instead of inferring it: immediately after the rail cycle,
and without any SWCLK dance, probe **both** addresses - if `0x51` answers on its
own the part is sitting in its bootloader with the announce line high, and if only
`0x2a` answers it is running the application interface and something else is
wrong. That single measurement separates "the part never leaves the bootloader"
from "the part runs but its application interface is not serviced".
