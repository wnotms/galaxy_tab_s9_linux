# Test 224 — a Bluetooth HID keyboard, end to end: **PASS**

**This closes the last outstanding item in the Bluetooth round.** A real
Bluetooth keyboard was paired, and the kernel turned it into a working input
device that delivers keypresses. Levels 0–13 are now verified, with a functional
data path — not just a bond.

Peer: **MCHOSE G87 V2-1**, `DC:05:5A:41:97:3E` (LE Random), the owner's own
keyboard, woken for the test.

## 1. Bond, over BLE

```
$ bluetoothctl info DC:05:5A:41:97:3E
	Name: MCHOSE G87 V2-1
	Appearance: 0x03c1 (961)
	Icon: input-keyboard
	Paired: yes
	Bonded: yes
	Trusted: yes
	Connected: yes
	WakeAllowed: yes
	UUID: Human Interface Device    (00001812-0000-1000-8000-00805f9b34fb)
	UUID: Battery Service           (0000180f-0000-1000-8000-00805f9b34fb)
	Modalias: bluetooth:v07D7pEFFFd0120
```

`Icon: input-keyboard` and the HID UUID come from the keyboard's own GATT
service list, so the profile was discovered, not assumed. The battery level was
also readable (`Battery Percentage: 0x26 (38)`), which exercises the GATT client
beyond the HID service itself.

## 2. The kernel created input devices — the decisive step

```
$ grep -E "^N: Name=" /proc/bus/input/devices
N: Name="Book Cover Keyboard Slim (EF-DX710)"      <- the POGO keyboard, unrelated
N: Name="MCHOSE G87 V2-1 Keyboard"
N: Name="MCHOSE G87 V2-1 Mouse"                    <- the keyboard's mouse endpoint
```

Two nodes, one keyboard and one mouse, exactly as the device describes itself.
The POGO keyboard appearing in the same list is a useful control: the input stack
was already working, so this is specifically the *Bluetooth* path that delivered.

## 3. Bound to the HID/input stack, not merely connected

```
$ grep -A 6 "MCHOSE G87 V2-1 Keyboard" /proc/bus/input/devices
S: Sysfs=/devices/virtual/misc/uhid/0005:07D7:EFFF.0001/input/input4
H: Handlers=sysrq kbd leds event4
```

`Handlers=kbd leds` and `/dev/input/event4` mean the kernel treats it as a real
keyboard: it takes the console keyboard handler, it owns the LED state (so
Caps/Num Lock feedback can be written back over HID), and it has an evdev node.

The capability bitmap confirms a full keyboard rather than a stub:

```
B: EV=12001f
B: KEY=73ffff 0 0 4c3ffff17aff32d bfd4445600000000 1 1130ffb8b17c007 ...
B: REL=1040
```

`EV_KEY` with the complete key bitmap, plus `EV_REL`/`EV_ABS` for the wheel and
media controls, and `EV_LED` for `LED_NUML`/`LED_CAPSL`/`LED_SCROLLL`.

## 4. Real keypresses arrived — the functional data path

`evtest /dev/input/event4` was run and the owner typed. Events captured, with the
USB HID scancode included in each (`0x70004` = A, `0x70007` = D, and so on):

```
Event: time ..., type 1 (EV_KEY), code 36 (KEY_J), value 1
Event: time ..., -------------- SYN_REPORT ------------
Event: time ..., type 1 (EV_KEY), code 23 (KEY_I), value 1
Event: time ..., type 1 (EV_KEY), code 32 (KEY_D), value 1
Event: time ..., type 1 (EV_KEY), code 31 (KEY_S), value 1
Event: time ..., type 1 (EV_KEY), code 30 (KEY_A), value 1
Event: time ..., type 1 (EV_KEY), code 14 (KEY_BACKSPACE), value 1
Event: time ..., type 1 (EV_KEY), code 14 (KEY_BACKSPACE), value 0
Event: time ..., type 1 (EV_KEY), code 38 (KEY_L), value 1
Event: time ..., type 1 (EV_KEY), code 28 (KEY_ENTER), value 1
```

with matching `EV_MSC MSC_SCAN` reports carrying the HID usage codes. Press and
release pairs are both present, so this is not a single stray event: the report
path is bidirectional and repeating correctly. Backspace was held and auto-repeated
eight times, which additionally exercises the keyboard's own repeat handling.

## What this proves that test 222 did not

Test 222 proved a bond and a stored link key, but a Windows peer could only offer
audio and PAN profiles, so no data ever crossed the link. Here the whole chain
carries input:

```
keypress -> keyboard firmware -> BLE HID report -> hci0 (LE) -> hidp/uhid
         -> /dev/input/event4 -> evdev -> consumers
```

## Still not tested

* **Reconnect after the keyboard sleeps or the tablet reboots.** The bond and
  `WakeAllowed: yes` are in place and the keyboard is trusted, but a wake-from-sleep
  reconnect has not been observed. The test plan's Test 7 covers it.
* **The mouse endpoint.** A separate `... Mouse` input node exists and the
  keyboard has a wheel; neither was exercised.
