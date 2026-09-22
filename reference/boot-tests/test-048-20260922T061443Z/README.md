# test-048 — does the application answer if we never reset it?

- started: 2026-09-22T06:14:43Z
- source commit: `74c8ec6` (`74c8ec662ed3fc5825a196ac393f0785e97c824b`)
- upstream: `a13c140cc289c0b7b3770bce5b3ad42ab35074aa` (v7.2-rc3)
- images: `boot.img 722ad2b8…`, `init_boot.img 2fb24cd0…` (already on device),
  `vendor_boot.img 828dadec…`, `dtbo.img c17418be…` (stock, untouched)
- authorization: owner asked to continue the repair ("检查仓库变化，继续修复") and
  had already authorised flashing ("刷入测试") for tests 046 and 047

## Hypothesis

Test 047 accepted both GO acknowledgements and then reset the MCU 150 ms later, so
the application was never given time to answer. A slower, uninterrupted, read-only
start had never been measured. Candidate `74c8ec6` therefore polls the application
for up to five seconds after GO and after the reset entry, resetting nothing.

## Result — hypothesis disproved

```
[    4.088964] MCU application did not answer; entering its bootloader
[    4.496022] MCU bootloader took the 0xFF sync
[    4.505181] MCU bootloader version 0x12
[    4.515268] MCU bootloader accepted GO 0x08000000, application should be running
[    9.563508] application after GO: -6 after 5036 ms without reset (no version response)
[   14.642114] application after reset entry: -6 after 5052 ms without reset (no version response)
[   17.346017] no answer from the MCU after 40 resets (-6)
```

Both five-second windows elapsed with `-ENXIO` (`-6`) on every poll: five seconds
after GO and five seconds after the reset entry. The application never answers the
version command, with or without a reset, so the fault is not the reset timing and
not the polling window.

## What this leaves

`GO 0x08000000` is acknowledged, but `0x08000000` is the *header* of the firmware
image, not necessarily the application entry. `struct stm32_fw_header` in
`stm32_pogo_v3.h` starts the flash layout and carries `boot_bank_addr` at offset 28
and `target_bank_addr` at offset 32, so the application is started by jumping to the
bank address recorded in that header. The next candidate reads the header over the
bootloader's READ (`0x11`) command and jumps to the bank address instead of
`0x08000000`. See test-049.
