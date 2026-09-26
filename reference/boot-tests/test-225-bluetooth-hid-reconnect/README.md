# Test 225 — HID keyboard reconnect after a full reboot: **PASS**

Level 11, now with the real HID peer rather than the Windows adapter. The
keyboard's bond survived a reboot and the kernel re-created its input node
**without any re-pairing**.

Peer: **MCHOSE G87 V2-1**, `DC:05:5A:41:97:3E`.

## The reboot

The tablet was rebooted (`systemctl reboot`). On the fresh boot
(`boot_id 3260f9d5`, `up 0 minutes` at the first check) the address unit ran again
with no manual step:

```
gts9-bt-addr: set public address 38:8A:06:59:04:E7 (from /run/gts9-bt-efs/bluetooth/bt_addr)
GTS9_DEBIAN_STAGE=bluetooth-address-set
```

That is test 1 of `reference/bluetooth-test-plan.md` passing for the third time,
now on a boot that also carries a HID bond.

## The reconnect

Immediately after the reboot the keyboard was `Connected: no` — correct, because a
Bluetooth keyboard sleeps when idle and therefore stops advertising. Pressing a key
woke it, and the existing bond was reused:

```
15:04:51 watching for DC:05:5A:41:97:3E to wake
15:06:49 CONNECTED after 4 cycles
         Device DC:05:5A:41:97:3E ServicesResolved: yes
         Device DC:05:5A:41:97:3E Paired: yes      <- existing bond, reused
15:06:49 input nodes for the keyboard: 1
```

`ServicesResolved: yes` is the important one: the HID GATT services were
re-discovered over the stored bond, which is what makes the device usable again
rather than merely linked. No pairing agent was involved and the passkey exchange
did not repeat — the link key from test 224 was reused.

## The input node came back

```
$ grep -A 6 "MCHOSE G87 V2-1 Keyboard" /proc/bus/input/devices
S: Sysfs=/devices/virtual/misc/uhid/0005:07D7:EFFF.0001/input/input4
H: Handlers=sysrq kbd leds event4
```

Same node (`event4`), same handlers, so consumers see the keyboard return rather
than a new device appearing.

## An honest note on what "automatic" means here

The reconnect required **one keypress on the keyboard**. That is not a shortcoming
of the tablet: a Bluetooth keyboard powers its radio down when idle, so it is not
advertising and cannot be connected to until it wakes. The tablet did the rest —
it reused the bond, resolved the HID services and re-created the input node with
no user action on the Linux side, no `bluetoothctl` command in normal use, and no
re-pairing.

What was **not** tested is `WakeAllowed: yes`, i.e. the keyboard waking the
*suspended tablet*. Suspend/resume is explicitly out of scope for this round, and
the property is merely recorded as present.

## Levels

| level | status |
|---|---|
| 10 pair | PHYSICALLY_VERIFIED — including real keypresses (test 224) |
| 11 reboot reconnect | **PHYSICALLY_VERIFIED** (this test) |
| 12 coexistence | PHYSICALLY_VERIFIED (test 220) |
| 13 cold boot | PHYSICALLY_VERIFIED (tests 220, 222, 225) |
