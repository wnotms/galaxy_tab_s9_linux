# `samsung-pogo` — Samsung's own `stm32_pogo_v3`, retained for reference

This is a reference implementation only. The default SM-X710 build uses
`kernel/drivers/keyboard-samsung-pogo.c` and does not copy this directory into
the prepared kernel tree. `scripts/prepare-kernel.sh` installs it only when run
with `GTS9_INSTALL_VENDOR_POGO=1`, for a deliberate manual A/B comparison.

It preserves the source needed for future A/B comparisons without adding a
second Pogo implementation to the normal source overlay or default Kbuild path.

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

## The adaptation, and its result

This kernel has removed the integer GPIO API the vendor driver was written
against, and the first compile stopped at `'linux/of_gpio.h' file not found`.
The conversion is done and changes no behaviour:

* the six `dtdata->gpio_*` fields are `struct gpio_desc *`, and `stm32_parse_dt()`
  uses `devm_gpiod_get_optional()` with the board DTS's own property names
  (`announce`, `connect`, `swclk`, `nrst`, `sda`, `scl`);
* `gpio_direction_output`/`gpio_get_value`/`gpio_to_irq` became their `gpiod_*`
  equivalents, and the explicit request/free pairs disappeared with devm;
* four smaller API moves: the 1-argument i2c probe and void `remove`, an inlined
  `i2c_new_dummy_device()` (the vendor's version guard hid it), a `linux/types.h`
  include, and `SEC_TS_WAKE_LOCK_TIME`, `sec_delay()` and `sec_device_destroy()`
  from `samsung_pogo_compat.h`;
* `samsung_pogo_stubs.c` defines the notifier, backlight and msm-bus services the
  vendor header declares, so the signatures match exactly.

All seven objects now compile clean:

```
stm32_pogo_i2c_v3  stm32_pogo_core_v3  stm32_pogo_cmd_v3  stm32_pogo_fw
stm32_pogo_interrupt_v3  stm32_pogo_fn_v3  samsung_pogo_stubs
```

## Optional A/B setup

Run `GTS9_INSTALL_VENDOR_POGO=1 scripts/prepare-kernel.sh <worktree>` to copy
this reference driver and add its Kconfig/Makefile entries for a manual A/B.
The normal `scripts/build-kernel.sh` intentionally requires the verified
mainline symbol; changing the kernel configuration for a vendor comparison is
an explicit experiment. A later default prepare resets the worktree and removes
the optional files and Kbuild edits.
