# test-066 — the irqchip cannot report the announce line's level

- started: 2026-09-22T08:34:00Z
- source commit: `c6f1974`
- images: `boot.img 2008d152…`; vendor_boot/init_boot/dtbo unchanged
- authorization: standing device-test authorisation recorded for tests 046-065

## Hypothesis

Test 065's interrupt arrived 11 µs after the handler was armed, i.e. it was a
`bias-disable` level-low line that was already low rather than an announcement,
and an interrupt therefore says nothing about the MCU's state. Stock prints the
same line as `int:1` while its application runs, so the level itself is the
measurement: read `IRQCHIP_STATE_LINE_LEVEL` from the irqchip.

## Result — the measurement is not available on this platform

```
[    4.718431] MCU rail on with BOOT0 low, announce line armed (level -1)
[    4.736655] MCU announced itself (1)
```

`level -1` is `pogo_announce_level()` returning failure:
`irq_get_irqchip_state(irq, IRQCHIP_STATE_LINE_LEVEL, &level)` is not
implemented by this platform's irqchip, so the level cannot be read through the
interrupt at all. The hypothesis is not disproved - it was never measured - and
the port has to own a descriptor for the line instead.

That is exactly the structure Samsung's driver uses: `stm32,irq_gpio` through
`of_get_named_gpio()` with `gpio_to_irq()` deriving the interrupt, so the driver
owns a GPIO it can read. Test 067 claims the line the same way
(`announce-gpios` + `devm_gpiod_get_optional(GPIOD_IN)`) and measures it.
