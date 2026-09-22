# test-093 — keyboard key press, prepared (not yet flashed)

- date: 2026-09-22T13:35Z
- source: working tree on `b5e3835` (test 092's verified fix plus source-only cleanups)
- image: `boot.img 8e332436…` (`IMAGE-SHA256SUMS`), built and hashed, **not flashed**
- authorization: `刷入测试`, `继续修复`, `修复键盘驱动…`

## Why

Test 092 met stage 1 and stage 2's values: after the ordered app-entry reset the MCU
announced itself and answered `MCU model 0x1 hw 0 firmware 1.4 mode 1`. Stages 3 and
4 - a real key interrupt and `EV_KEY` on `/dev/input/eventX` - need a physical key
press, and this device has no `evtest` and no adbd in mainline, so this build logs
every key the driver reports:

```
samsung-pogo-keyboard 5-002a: key 0xNN pressed (from the MCU packet)
samsung-pogo-keyboard 5-002a: key 0xNN released (from the MCU packet)
```

Host gates before the build: 10/10 unittest cases, kernel build with no errors.

## Result of this round's attempt: blocked on the bench, not measured

Two console sessions were taken at 13:35Z. COM17 is present on the host and opens,
but the tablet sent nothing at all, and `adb devices` is empty - so the device is
not in its mainline state (mainline has no adbd, but it does print to this console)
and is most likely powered off or running stock Android. No flash was attempted and
no result is claimed. The empty sessions are not archived (the capture files were not written to the host).

## Next step

With the tablet powered and reachable: flash this image (read-back hash check, BCB
clear, `reboot system`), confirm the two test-092 lines reappear, then press keys on
the cover keyboard while the console is captured - the key lines above are stage 4
and the `5-002a` interrupt count in `/proc/interrupts` is stage 3. If the count now
rises on key presses but no key line appears, the MCU is announcing without a key
packet, which is a different failure and would be recorded as such.
