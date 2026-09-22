# test-070 — the A/B: Samsung's own driver runs and reads `0x2a` no better

- started: 2026-09-22T09:05:00Z
- source commits: `506195e`, `f246769`, `c109ed1`
- images: `boot.img 31a17ded…`, `vendor_boot.img 3a2f767c…` (both carry the DTS
  that now also has Samsung's property names); `init_boot 12b77d17…`,
  `dtbo c17418be…` unchanged
- authorization: standing device-test authorisation recorded for tests 046-069,
  plus the owner's stages five and six

## What was asked

With kernel, DTS, GENI driver, initramfs and hardware identical, run Samsung's own
`stm32_pogo_v3` (imported into `kernel/drivers/input/samsung-pogo/`) instead of
`keyboard-samsung-pogo.c`. If the vendor driver brings the application interface
up, the fault is in the port's logic; if it does not, the fault is below the
driver.

Three boots were needed to get the vendor driver as far as its own handshake,
each one a documented property or API gap rather than a guess:

1. `unable to get gpio_sda` — mainline gives gpio72/106 to the controller as
   `qup2_se7`, so claiming them as GPIOs returns `-EINVAL`; the vendor driver only
   reads those lines for diagnostics, so their absence is now tolerated (`506195e`);
2. `Failed to get irq_type property` and then `unable to get model_name` — the
   vendor's parse reads `stm32,irq_type`, `stm32,irq_conn_type`,
   `stm32_vddo-supply`, `stm32,model_name` and friends, which the board node did
   not carry (`f246769`);
3. `unable to get fota_fw_path -22` — plus `stm32,i2c-burstmax` and
   `support_open_close` (`c109ed1`).

## Result — the A/B answers the owner's question

With the last gap closed the vendor driver runs completely in mainline:

```
[    4.732381] stm32_dev_probe++            (after "deferred_flag boot")
[    4.738218] stm32_i2c_new_dummy: client_boot address:0x51
[    4.777361] gpio_sda not available (-22), continuing
[    4.795425] irq_type property:2008, 8200
[   19.652164] stm32_enable_irq: enable dev irq
[   19.659702] stm32_keyboard_start done
[   19.909690] stm32_dev_regulator on: vdd:on
[   21.871038] kbd_max77816_control : not support device
[   21.880383] stm32_dev_regulator on: vdd:on
[   21.944260] stm32_enable_irq: enable dev irq
```

Its probe succeeds, it switches the rail itself, its connect ISR and both
workqueues run — **and it never reads the application interface either**: across
the whole boot there is no `stm32_read_version`, no `[MODE]`, no CRC line, only
`CRC32 instructions` from the CPU feature dump. So:

> **Neither driver brings `0x2a` up under mainline.** By the owner's own rule the
> fault is therefore *below* the pogo driver: the controller, pinctrl, regulator,
> clock or runtime-PM layer. Stages five and six have done their job.

## A new, concrete difference this boot exposed

Because the vendor driver gates everything on the connect line, its log shows what
the floating line does: `stm32_conn_isr (0)` / `(1)` alternate, and each transition
runs `stm32_keyboard_stop()` or `stm32_keyboard_start()`, i.e. **the MCU's rail is
switched on and off repeatedly** (19.6-21.9 s in this log). In stock the same line
reads `con:1/1` and never moves, so the keyboard is powered once and left alone.
Both trees configure gpio62 as `input-enable; bias-disable`, so the difference is
not the pin configuration: in stock something drives that line and in mainline
nothing does.

That is a measurable, board-level difference on the same pin the A/B just showed
to be irrelevant to the driver question, and it is the first item for the next
stage, followed by the owner's list: GENI driver, pinctrl, regulator, clock and
runtime PM - now with the vendor driver available as a second, independent probe
of the same layer.
