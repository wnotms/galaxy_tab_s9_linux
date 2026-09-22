# test-051 — no header in flash, and neither interface answers after the reset

- started: 2026-09-22T06:51:20Z
- source commit: `17647ad` ("pogo: report where the firmware header is and which
  interface answers")
- upstream: `a13c140cc289c0b7b3770bce5b3ad42ab35074aa` (v7.2-rc3)
- images: `boot.img c4d07441…` (from `out/boot-bundle-test051`), `init_boot.img
  2fb24cd0…`, `vendor_boot.img 828dadec…`, `dtbo.img c17418be…` unchanged
- authorization: owner asked to continue the repair ("检查仓库变化，继续修复") and
  asked to reduce the wait between system switches

## Question

After test 050 reproduced stock's sequence exactly and the application still did
not answer, two readings had to separate the remaining cases: where Samsung's
`"STM32"` firmware header actually is, and which interface answers after the
disconnected reset.

## Result

```
[    4.302536] MCU IC version 00340034
[    4.436876] no STM32 header at 0x80000c0 or 0x80000bc, first bytes 00000000000000000000000000000000
[    4.642448] after the disconnected reset: application -6, bootloader -6, connect 1
[    9.683301] application after bootloader start: -6 after 5024 ms without reset (no version response)
[    9.697711] five seconds later: application -6, bootloader -6, connect 1
[   12.394354] no answer from the MCU after 40 resets (-6)
[   12.468966] i2c-5 answers at: (nothing)
```

1. **No header in flash.** Both offsets the vendor's flasher uses for the magic
   (`0x080000bc` for L0, `0x080000c0` for G0) read as zeros. Samsung's
   `struct stm32_fw_header` is read from the *firmware file*
   (`stm32->fw->data[magic_offset]` in `stm32_pogo_cmd_v3.c`), which is what the
   userspace flasher compares and writes; the flash at `0x08000000` holds the
   application image itself — a valid vector table, the IC version word at
   `0x08000200` and zeros between. The bank addresses are therefore not readable
   from the part this way, and the earlier idea of jumping at a bank address read
   from flash is closed.

2. **After the disconnected reset neither interface answers.** The bootloader at
   `0x51` is silent (correct for BOOT0 low) and the application at `0x2a` is
   silent too, five seconds apart, with `connect` still reading 1 — so the part is
   not parked in its bootloader, and it is not answering as an application either.

3. The 40-reset retry loop that follows leaves the bus completely empty
   (`i2c-5 answers at: (nothing)`), i.e. each reset restarts whatever the MCU was
   doing.

## What this turned into

The `connect` line reads 1 at power-on and 0 after the first reset, and stock's
driver first reads the application 33 s into its boot without ever resetting the
part (`rst:0`). Taken together with test 051's second reading, the remaining
explanation is that the application needs time from power-on before it answers,
and that this port's 4-second poll followed by a reset every ~50 ms restarted it
permanently. Test 052 replaces the reset loop with a patient, read-only poll.
