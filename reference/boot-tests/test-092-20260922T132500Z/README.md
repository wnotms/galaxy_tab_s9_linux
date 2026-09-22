# test-092 — the MCU was in its system bootloader: an ordered app-entry reset makes 0x2a answer

- date: 2026-09-22T13:25Z, executed 13:26–13:33Z
- source: working tree on top of `0f0b759` (prepared as one change; images
  `boot.img 6dec0bc4…`, read back from its partition byte-for-byte before boot)
- authorization: `刷入测试`, `继续修复`, `修复键盘驱动，可以参考s9u的对应驱动或搜索其它开源仓库的实现`
- raw logs: `c.log` (recovery trigger), `c2.log` (result)

## Change (one purpose: release the MCU into its application)

The normal startup path now performs the app-entry reset stock and the SM-X910
port perform, **before** raising the rail, and never talks to 0x51:

```
claim the supply, drive it low      (regulator_enable + regulator_disable)
swclk/BOOT0 = 0                      -> run the application, not the bootloader
nrst = 0, 2 ms, nrst = 1             -> BOOT0 is sampled on this edge
msleep(150)                          -> STM32_BOOT_I2C_STARTUP_DELAY
rail on, 50 ms, arm DATA             -> wait for the model packet
```

The "ask 0x2a directly after 1.5 s" poll added for test 091 is removed: test 091
measured it NACKing (`-6`, irq 170 = 0), and the survey found SM-X800 measuring
12,158 polls with zero ACKs — `0x2a` is served only inside the ATTN handshake.

## Result — stage 1 met, and stage 2's values with it

```
[    4.082862] input: Book Cover Keyboard Slim (EF-DX710) as .../i2c-5/5-002a/input/input0
[    4.584829] application-entry reset: BOOT0 low, NRST 2 ms low then high, 150 ms settle, rail on
[    4.597188] keyboard powered; DATA IRQ armed, waiting for model packet
[    4.716681] MCU announced itself (1)          <- the application answered, 120 ms after the reset
[    4.733333] MCU model 0x1 hw 0 firmware 1.4 mode 1
 170:          1  ...  msmgpio     75 Level     5-002a     <- first delivery in the project's history
```

`mode 1` is `POGO_MODE_APP` and firmware `1.4` matches TWRP's own
`EF-DX710_v1.4.1.0`, so the application is running and speaking. **The root cause
was state, not a broken bus**: on STM32 BOOT0 is sampled on the NRST release, the
part had been left in its ROM bootloader (where 0x51 answers and 0x2a NACKs), and
a Linux reboot does not power-cycle the MCU — so nothing ever released it. Asking
without resetting could never work.

- stage 1 (`0x2a` answers): **met**
- stage 2 (`EF-DX710_v1.4.1.0`, `GET_MODE=1`, CRC): version and mode met; the CRC
  value is not printed by this path, so it stays unclaimed
- stage 3 (real key IRQ) and stage 4 (`EV_KEY` on `/dev/input/eventX`): **not yet
  measured — they need a physical key press**

## Not claimed

This unit's application is V34-era (test 049 read reset vector `0x0800c4a5`; the
public V37 blob is `0x0800c515`, `0x200 = 00 37 00 37`). V34 works in TWRP and the
model read now succeeds, so no firmware change is proposed or needed here; the
observation is recorded, nothing is written to the MCU.
