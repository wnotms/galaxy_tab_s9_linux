# `samsung-pogo` — Samsung's own `stm32_pogo_v3`, imported for an A/B

This directory is the second half of the A/B the investigation needs: the same
hardware, kernel, DTS, GENI driver and initramfs, with **only** the pogo driver
swapped. If this one brings the application interface up and
`drivers/input/keyboard/keyboard-samsung-pogo.c` does not, the fault is in the
driver's logic; if neither does, the fault is below the driver — controller,
pinctrl, regulator, clock or runtime PM.

## What is here

Imported verbatim from `/home/ms/Samsung/kernel_platform/msm-kernel/drivers/input/sec_input/stm32/`
(the official SM-X710 source release):

```
stm32_pogo_i2c_v3.c        probe, i2c transport, runtime PM
stm32_pogo_core_v3.c       start, interrupt init, wakeup source
stm32_pogo_cmd_v3.c        commands: version, mode, CRC, touchpad, sysfs
stm32_pogo_fw.c            firmware update path (and the bootloader it uses)
stm32_pogo_interrupt_v3.c  both ISRs, connect/check work, key dispatch
stm32_pogo_fn_v3.c         regulator, delay, status printing
stm32_pogo_v3.h            the vendor's own header, unchanged
pogo_notifier_v3.h         device/event ids and notifier payloads
```

## What was removed, and why that cannot affect the bring-up

* `stm32_pogo_keyboard_v3*.c`, `stm32_pogo_touchpad_v3.c` — the child input
  devices. They register only *after* the application answers, so they are the
  last stages of the plan, not part of the A/B's first question.
* `sec_class` sysfs, factory test, FOTA and debug interfaces — `stm32_init_cmd()`
  and friends are the only users, and the owner's brief allows dropping them.
* Samsung framework includes (`../sec_input.h`, `../sec_tsp_log.h`,
  `<linux/msm-bus.h>`, `<linux/muic/...>`) — replaced by
  `samsung_pogo_compat.h`, which supplies the logging wrappers, the notifier
  registration, `kbd_max77816_*`, MUIC and msm-bus as no-ops that log the same
  thing the vendor driver logs on this board ("not support device").
* `stm32_pogo_i2c.h` — the v1/v2 header; nothing in the v3 path uses its types.

Nothing in this list runs on the path between the rail coming up and
`CHECK_VERSION` succeeding, which is the only thing the first A/B step asks.

## Done in the import

* the match table now carries the board DTS's compatible
  (`samsung,x710-pogo-keyboard`) beside the vendor's own string;
* `stm32_init_cmd()` keeps its place in the probe sequence and its success
  contract but no longer creates the sec_keypad class device or its sysfs group;
* the MUIC path is empty in the bring-up set (only one msm-bus vote is used, and
  the compat header provides it as a no-op).

## Remaining work, and the one real adaptation

The first compile attempt stops at the first vendor header line:

```
stm32_pogo_v3.h:36:10: fatal error: 'linux/of_gpio.h' file not found
```

This kernel has removed the integer GPIO API, and the vendor driver is written
against it: `stm32_parse_dt()` stores raw gpio numbers with
`of_get_named_gpio()` and the driver then uses `gpio_direction_output()`,
`gpio_get_value()` and `gpio_to_irq()` at about thirty call sites. The board DTS
already names every one of those lines with a standard `-gpios` suffix
(`connect-gpios`, `swclk-gpios`, `nrst-gpios`, `sda-gpios`, `scl-gpios`,
`announce-gpios`), so the conversion is mechanical and changes no behaviour:

1. the six `dtdata->gpio_*` fields become `struct gpio_desc *`;
2. `stm32_parse_dt()` uses `devm_gpiod_get_optional()` for those six names;
3. `gpio_direction_output` → `gpiod_direction_output`, `gpio_get_value` →
   `gpiod_get_value`, `gpio_to_irq` → `gpiod_to_irq`, and the explicit
   `gpio_request`/`gpio_free` pairs disappear with devm;
4. then wire `KEYBOARD_SAMSUNG_POGO_VENDOR_PORT` into the kernel Kconfig and into
   `scripts/prepare-kernel.sh`'s driver copy list (the port is a directory, not a
   `keyboard-*.c` file, so the script needs one more rule), and let
   `scripts/build-kernel.sh`'s required-symbol check accept either driver;
5. compile, then run the A/B on hardware and record it as a new test.
