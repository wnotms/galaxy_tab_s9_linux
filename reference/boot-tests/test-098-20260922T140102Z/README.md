# test-098 — the keyboard works: stock's post-announcement frames were the missing step

- date: 2026-09-22T14:01Z (flash) – 14:04Z (key presses)
- source: working tree on `d69adb4`; `boot.img 52a26bc6…` flashed and read back
- authorization: `刷入测试`, `继续修复`, `修复键盘驱动，可以参考s9u的对应驱动或搜索其它开源仓库的实现`
- raw logs: `to-recovery.log`, `boot.log`, `keys.log`

## Change (one purpose: finish stock's post-announcement sequence)

The port stopped after GET_MODE, which is precisely where the MCU went quiet. Stock
sends two more frames (extracted from `stm32_pogo_fn_v3.c` and the vendor ISR, and
confirmed against two stock byte captures on this unit): **CHECK_CRC** (`04 00 01` +
`03`) and **GET_TC_FW_VERSION on EP 2** (`04 00 02` + `18`), after a 200 ms settle.
Both are now sent from `pogo_hello()` once the application has answered the version
read, with a new `pogo_read_reg_ep()` helper for the EP-2 frame.

## Result — every acceptance stage met

```
[    4.328309] packet from the MCU: 03 00 02 (size 3)         stage 1: 0x2a answers
[    4.347185] MCU model 0x1 hw 0 firmware 1.4 mode 1         stage 2: mode 1, EF-DX710 v1.4
[    4.576032] CHECK_CRC: 0 - answered
[    4.576039] CRC32 6e 37 df ea                              stage 2: CRC32 EADF376E
[    4.578814] GET_TC_FW_VERSION (EP2): 0 - answered
[    4.578843] MCU announced itself (2)                        <- the MCU speaks again
[    4.579735] packet from the MCU: 04 00 04 (size 4)
[    4.579997] payload (1 bytes): 02                           <- the hall packet stock's capture shows
 169:          2  ...  msmgpio     75 Level     5-002a
```

Then the owner pressed keys on the unfolded cover:

```
[   32.010043] key 0x1e pressed (from the MCU packet)          stage 3 + 4: real key IRQ and EV_KEY
[   32.144566] key 0x1e released (from the MCU packet)         0x1e = KEY_A
[   33.138769] key 0x39 pressed (from the MCU packet)          0x39 = KEY_SPACE
[   33.329488] key 0x39 released (from the MCU packet)
[   34.732962] key 0x1c pressed (from the MCU packet)          0x1c = KEY_ENTER
[   34.928394] key 0x1c released (from the MCU packet)
 169:          8  ...  msmgpio     75 Level     5-002a
```

The interrupt count rose from 2 to 8 on key presses, six key transitions were
decoded, and the codes are the correct Linux key codes for the keys pressed. The
input device is `Book Cover Keyboard Slim (EF-DX710)` with handlers
`sysrq kbd leds event0`, so the events reach `/dev/input/event0`.

**The keyboard is functional on mainline.** Root cause, now measured end to end: the
MCU had to be released from its system bootloader by a BOOT0-low NRST pulse before
the rail was raised (tests 092/093), and once its application had answered the
handshake it still had to be asked for the CRC and touch-controller version before
it would start reporting (this test).

## Excluded along the way, each with the application alive

Bus rate (test 097, 400 kHz as stock runs it), the event wire protocol (identical to
`stm32_dev_isr`), a missing start/keep-alive write (there is none; the booster call is
provably a no-op on X710), the decode path (never given a packet before this test),
firmware revision (V34 works in TWRP and here), and pin/level semantics.
