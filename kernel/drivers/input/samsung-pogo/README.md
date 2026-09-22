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

## Remaining work before it can be built

1. Give the port the same compatible string as the board DTS
   (`samsung,x710-pogo-keyboard`) or add the key's node to its match table.
2. Replace the missing `sec_device_create()`/sysfs and `stm32_init_cmd()` body
   with a no-op (the compat header documents the boundary).
3. Strip the msm-bus DT parse and the MUIC notifier registration from
   `stm32_pogo_core_v3.c`.
4. Wire the Kconfig choice into the kernel build and into
   `scripts/prepare-kernel.sh`'s driver copy list, so
   `CONFIG_KEYBOARD_SAMSUNG_POGO_VENDOR_PORT=y` builds this instead of
   `keyboard-samsung-pogo.c`.
5. Compile, then A/B on hardware and record the result as a new test.
