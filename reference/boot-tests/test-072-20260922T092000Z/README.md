# test-072 — stock's firmware path reproduced in mainline, and the last blocker

- started: 2026-09-22T09:20:00Z
- source commit: `af5b80e` (initramfs carries the firmware), kernel = the vendor
  port from test 070 with Samsung's property names in the DTS
- images: `boot.img 31a17ded…`, `init_boot.img aed8f3c5…` (the initramfs now
  carries `lib/firmware/keyboard_stm/stm32_gts9family.bin`, 52012 bytes);
  `vendor_boot 3a2f767c…`, `dtbo c17418be…` unchanged
- authorization: standing device-test authorisation recorded for tests 046-071

## Where the firmware was

The boot-time stock trace (test 019's `BOOT-SEQUENCE.md`) showed the vendor
driver running its whole firmware path at boot, which mainline could not because
`request_firmware()` fails there. The file is **not** in the firmware partition
and **not** embedded in the kernel; it is in TWRP's ramdisk at
`recovery/root/vendor/firmware_mnt/image/keyboard_stm/stm32_gts9family.bin`,
which the running system hides because TWRP later mounts the real partition over
that path. Its size, 52012 bytes, is the one the stock driver logs for its own
checksum.

## Result — the sequence is now identical to stock's

```
5.666928 stm32_target_empty_check_status Flash Word: 0x200056C0
5.676035 stm32_dev_checksum address: 0x800c800, len=812
5.727310 stm32_dev_checksum: checksum ic:0x7E2341C8 bin 0x7E2341C8
5.736714 stm32_sysboot_disconnect start
6.065150 stm32_sysboot_mcu_validation Connection OK
6.142118 stm32_sysboot_mcu_validation Get target info OK Target PID: 0x460 Bootloader version: 0x12
6.159497 stm32_sysboot_disconnect start
6.332661 stm32_dev_check_firmware_version phone:00340034 ic:00340034
6.342215 stm32_dev_firmware_update_mode: skip - fw update
6.353890 stm32_interrupt_init INT mode (170)
```

Every number matches the stock boot trace: the empty check reads the same
`0x200056C0`, the IC checksum is stock's own `0x7E2341C8`, the target is
`PID 0x460 / bootloader 0x12`, the firmware versions agree
(`phone:00340034 ic:00340034` - the port's own IC read) and the driver takes
stock's decision, `skip - fw update`. The firmware path is therefore no longer a
difference between the two systems.

## The last difference this exposes

With the path reproduced, the vendor driver still never reaches
`stm32_read_version`, and its log says why:

```
34.065566 stm32_keyboard_connect: 1
36.051905 stm32_conn_isr (0) / (1) / (0)
36.248979 stm32_keyboard_connect: 0
36.369051 stm32_check_conn_work: con:0, current:1
38.364481 ... the same pattern every two seconds
```

The **connect line oscillates**, so the vendor state machine alternates
`stm32_keyboard_start()` / `stm32_keyboard_stop()`, switching the MCU's rail on
and off and never settling on the path that reads the application. In stock the
same line reads `con:1/1` and never moves. Both trees configure gpio62 as
`input-enable; bias-disable`, so the difference is not the pin configuration:
in stock something drives that line high and in mainline nothing does, and the
vendor driver - unlike the mainline port - gates everything on it.

That is now the single blocking difference, and it is a one-line board change to
test: give the connect line a pull-up so it reads high when undriven, as stock
observes it, and let the vendor driver's state machine run to the application
read.
