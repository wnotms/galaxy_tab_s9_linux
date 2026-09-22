# test-094 — raw packet logging: the MCU sends one packet and then nothing, even on key presses

- date: 2026-09-22T13:46:50Z (recovery) – 13:49:55Z (key-press read)
- source: working tree on `75f950b`; `boot.img e63a3b61…` flashed and read back
  from its partition byte-for-byte (`IMAGE-SHA256SUMS`)
- authorization: `刷入测试`, `继续修复`, `修复键盘驱动…`, and the owner's request to
  cut the waiting time out of device operations
- raw logs: `to-recovery.log`, `boot.log`, `keys.log`

## Change (one purpose: make every MCU packet visible)

The handler logged only successful key decodes, so a packet that arrived with an
unexpected size or id was invisible. It now logs every packet it reads, header and
payload, before any decode decision:

```
packet from the MCU: 03 00 02 (size 3)
payload (N bytes): ...
```

## Timing (owner instruction: stop paying fixed sleeps)

`scripts/console-run.ps1` replaces the fixed waits: it opens the port, sends an
`echo READY<n>` heartbeat every second and returns the moment the shell answers, so
a boot costs its real duration. Measured on this cycle: recovery trigger 13:46:50,
flash 13:48:55 (the gap is the tablet's own reboot into TWRP), `reboot system`
13:48:57, console shell answering 13:49:23 — **26 s instead of the 75–95 s of blind
sleep** this project had been paying per test, and the key-press read at 13:49:55
answered after one poll.

## Result — the application comes up and then never speaks again

```
[    3.514724] input: Book Cover Keyboard Slim (EF-DX710) as .../i2c-5/5-002a/input/input0
[    4.300093] application-entry reset: BOOT0 low, NRST 2 ms low then high, 150 ms settle, rail on
[    4.312548] keyboard powered; DATA IRQ armed, waiting for model packet
[    4.433268] MCU announced itself (1)
[    4.447915] packet from the MCU: 03 00 02 (size 3)      <- the model announcement
[    4.462774] MCU model 0x1 hw 0 firmware 1.4 mode 1
 170:          1  ...  msmgpio     75 Level     5-002a
dmesg | grep -cE "packet from the MCU|key 0x"  ->  1
```

The owner then pressed keys on the **unfolded** cover. Afterwards: the interrupt
count is still 1 and the packet count is still 1. **The MCU sends nothing at all on
a key press** - no key packet, no malformed packet, no announcement. The host-side
decode path is therefore not implicated: it has never been given anything to
decode. Stage 3 and stage 4 remain unmet, and the reason is now on the accessory
side of the wire.

This matches the survey's note that a V34-era application under a V37-oriented
sequence "boots fine, pulses the connection line every ~2.1 s and never sends
0xd6". This unit is V34-era (test 049 read reset vector `0x0800c4a5`; the published
V37 image is `0x0800c515`), which makes the revision the leading explanation.

## Next discriminators

1. **Read the application revision directly** (`0x08000200`, read-only, one boot):
   `00 34 00 34` would confirm the V34 correlation; `00 37 00 37` would send the
   search back to the host sequence. Nothing is written to the MCU.
2. **Run the vendor A/B with the app-entry reset.** Samsung's own port implements
   stock's whole application phase, including whatever it does after the model
   handshake; if stock's logic makes this V34 application emit keys, the missing
   piece is host-side after all - and that is testable without touching firmware.
3. Only if both fail does the firmware revision itself become the subject, and
   rewriting the MCU is a decision for the owner, not something this project does
   on its own.
