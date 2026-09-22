# test-049 — the firmware header is not at 0x08000000, and GO is not how this part starts

- started: 2026-09-22T06:28:22Z
- source commit: `e9ac79e` (`e9ac79ec…`, the bank-address GO candidate)
- upstream: `a13c140cc289c0b7b3770bce5b3ad42ab35074aa` (v7.2-rc3)
- images: `boot.img 55f73ebe…` (built from `out/boot-bundle-test049`),
  `init_boot.img 2fb24cd0…`, `vendor_boot.img 828dadec…`, `dtbo.img c17418be…`
  unchanged
- authorization: owner asked to continue the repair ("检查仓库变化，继续修复"); the
  flash continues the authorisation recorded for tests 046–048 ("刷入测试")

## Hypothesis

`GO 0x08000000` is acknowledged but nothing runs (tests 047 and 048), because
`0x08000000` is the firmware *header*: `struct stm32_fw_header` carries
`boot_bank_addr` at offset 28 and `target_bank_addr` at offset 32, so the
application should be started by jumping at the bank address it names. The
candidate reads the 48-byte header over the bootloader's READ (`0x11`) command
and jumps at the first bank address that points into flash.

## Result — the READ works, the layout assumption was wrong

```
[    4.104772] MCU firmware header: magic c0560020a5c40008 boot bank 0x0 target bank 0x0
[    4.113158] no usable bank address in the header
[    4.128247] bootloader GO 0x8000000: accepted
[    9.177830] application after GO: -6 after 5044 ms without reset (no version response)
[   14.256384] application after reset entry: -6 after 5052 ms without reset (no version response)
[   16.951994] no answer from the MCU after 40 resets (-6)
[   17.009594] i2c-5 answers at: (nothing)
```

The READ framing is correct — 48 bytes came back, and the first eight are a
genuine Cortex-M vector table:

| bytes | little-endian word | meaning |
| --- | --- | --- |
| `c0 56 00 20` | `0x200056c0` | initial stack pointer, in SRAM |
| `a5 c4 00 08` | `0x0800c4a5` | reset vector, in flash, Thumb bit set |

So `0x08000000` holds the application image, not Samsung's header: the magic
there is `"STM32"` and the header lives at file offset `0xBC` (`L0`) or `0xC0`
(`G0`) inside that image (`stm32_pogo_cmd_v3.c`), i.e. at `0x080000BC` or
`0x080000C0`, never at `0x08000000`. The candidate fell back to the only address
it had and the result was the same as tests 047/048.

Two further facts came out of this run:

- after `GO` the MCU answered on **neither** address — the bus scan found nothing
  at all, so the acknowledged jump left the core somewhere that does not serve
  I2C, and a later NRST pulse did not bring the application back;
- the transfer counts in the transfer log (`i2c-5 answers at: (nothing)`) are the
  only way to see that, so the scan stays in the failure path.

## What the vendor actually does

`stm32_dev_firmware_update_mode()` runs on every stock boot, and it never sends
GO. Its sequence is: `stm32_sysboot_mcu_validation()` (enter the system
bootloader, Get Version, Get ID), read the IC version at `0x08000200`, then
`stm32_sysboot_disconnect()` — BOOT0 low, one NRST pulse, 150 ms — which releases
the part so the application runs from flash. Stock's log is the proof that the
application is up afterwards: `mcu_fw(bin):34, mcu_fw(ic):34,
EF-DX710_v1.4.1.0`, `con:1/1, int:1, rst:0`.

The next candidate replaces GO with exactly that sequence. See test-050.
