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

## Result — flashed, app comes up reproducibly, but no key event arrives

The image was flashed and verified (`boot=8e332436…` read back from the partition,
BCB cleared, `reboot system`), and the boot reproduced test 092 exactly:

```
[    4.056308] input: Book Cover Keyboard Slim (EF-DX710) as .../i2c-5/5-002a/input/input0
[    4.552068] application-entry reset: BOOT0 low, NRST 2 ms low then high, 150 ms settle, rail on
[    4.564413] keyboard powered; DATA IRQ armed, waiting for model packet
[    4.686490] MCU announced itself (1)
[    4.709593] MCU model 0x1 hw 0 firmware 1.4 mode 1
 170:          1  ...  msmgpio     75 Level     5-002a
N: Name="Book Cover Keyboard Slim (EF-DX710)"
H: Handlers=sysrq kbd leds event0
```

The owner then pressed keys on the cover keyboard. Measured immediately afterwards:

```
 170:          1  ...  msmgpio     75 Level     5-002a      <- unchanged: no new interrupt
dmesg | grep -c "key 0x"  ->  0                             <- no key packet was reported
```

So **stage 3 is not met and stage 4 is not met**: the application answers the
handshake once and then never announces again, and nothing reaches `event0`. The
input device exists with the `kbd` handler, so the registration half is done; what
is missing is the MCU actually sending a key packet.

Nothing here says the driver's packet decoder is wrong - it has never been given a
packet to decode. The open question is what the application needs after the model
handshake in order to start reporting keys.

## Next discriminators, cheapest first

1. **Confirm the physical state** with the owner: the cover must be attached *and
   unfolded*, since a folded cover disables its own keys (and the tablet's hall
   sensor is not wired up in mainline).
2. **Run the vendor A/B again now that the reset is understood.** The owner built
   that pair for exactly this question: Samsung's own `stm32_pogo_v3` port
   (`CONFIG_KEYBOARD_SAMSUNG_POGO_VENDOR_PORT`) implements stock's whole
   application-phase logic, including whatever it does after the model handshake to
   receive key events. Test 070 ran it *before* the app-entry reset was known, so it
   never got this far; with the reset it can be compared like for like. If the vendor
   driver receives keys, the missing piece is in this driver's event path; if it does
   not, the difference is above both drivers or in the accessory's state.
3. **Log what the application says on each announcement** rather than only on
   decode success: the handler currently logs a key line only after a valid packet,
   so a malformed or unexpected packet would be invisible. (Header size and id are
   already logged ratelimited on the invalid path.)
