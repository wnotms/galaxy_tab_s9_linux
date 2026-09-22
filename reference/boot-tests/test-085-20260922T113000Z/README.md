# test-085 — the rail is high from boot and the application still does not answer

- started: 2026-09-22T11:30:00Z
- source commit: the early-high commit
- images: `boot.img dd00574e…`, `vendor_boot.img b5f3cda0…` (new DTB);
  `init_boot aed8f3c5…` (with firmware), `dtbo c17418be…` unchanged
- authorization: standing device-test authorisation recorded for tests 046-084
- driver: the vendor port, with the firmware present

## Hypothesis and result

The MCU is powered independently of gpio10 (test 082), so it runs from tablet
power-on and could check whatever that rail feeds at its own power-up - before
any driver exists. Every earlier build with the pin high early lacked the
firmware path, the vendor driver and the reproduced firmware state, so this
combination had never been measured.

```
[   34.833645]   pin 10: io 0x3                      <- high, verified by register
[   13.616528] stm32_i2c_write_burst: I2C retry 3, ret:-6
[   20.286462] stm32_i2c_write_burst: I2C retry 3, ret:-6
[   35.864329] stm32_i2c_write_burst: I2C retry 3, ret:-6
```

The pad is high from the earliest moment the TLMM can drive it, the vendor
driver runs stock's complete firmware path, and `0x2a` still NACKs. **Hypothesis
disproved**: the rail's timing is excluded as well as its level (test 084).

## The host side is closed, by measurement

| item | test | state |
| --- | --- | --- |
| rail level (pad verified) | 084 | high, matching stock |
| rail from the earliest moment | 085 | high, still no answer |
| BOOT0 / NRST at startup | 075 | identical to stock |
| stock's firmware path, value for value | 072 | reproduced |
| the application runs unprompted | 076, 082 | it announces, even with the rail low |
| whole address range probed for real | 077 | nothing acknowledges |
| both driver implementations | 070, 078 | both fail identically |
| bus rate 100 / 400 kHz | 059, 079 | both fail identically |
| bootloader handoff state of all seven pins | 080 | recorded |
| pin state applied early | 081 | impossible by construction, reverted |

## The one concrete lead left, and why it needs a decision

There is a measured inconsistency between the MCU's flash and the firmware file
this project compares it against: stock's own driver checksums the application's
*last sector* and it matches the file exactly (`0x7E2341C8` in both), but the
image's *start* does not - reading 0x08000000 gives a valid vector table, and
0x080000BE/0xC0 read as zeros where the file carries Samsung's `"STM32"` header
(test 051, and the file layout in test 049's analysis). An application whose
first bytes are wrong and whose last sector is right is a partially written
image, which would explain a part that runs - the vector table and the reset
handler are intact - while the code that would bring up its I2C slave never
executes.

The vendor driver can now rewrite that flash: it runs the complete firmware path
here and stops at `skip - fw update` only because the versions match. Forcing the
update writes the MCU's flash, which is a decision this project has so far taken
only with the owner's explicit agreement (as with the option bytes in test 053,
which turned out to need no write at all). It is therefore proposed rather than
performed.
