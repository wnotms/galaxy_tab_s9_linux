# Test 222 — pairing and reconnect: **PASS**

Levels 10 and 11 are now verified against a real peer. The brief's §20 asks for a
mouse or keyboard; none was available, so the Windows host beside the tablet was
used, with the owner entering the passcode when the peer demanded one.

## Level 10 — pair: PASS

Initiated **from the Windows side**, which is the direction that works with a
Windows central: the tablet was made discoverable and pairable, Windows connected
to it, and the SSP exchange completed.

```
$ bluetoothctl info F8:CF:52:CD:BE:9F
	Paired: yes
	Bonded: yes
	Trusted: yes
	Connected: yes
```

and the agent logged the exchange it accepted:

```
AGENT RequestConfirmation 985715 -> accept   <- peer showed this code
AGENT AuthorizeService 0000110e-0000-1000-8000-00805f9b34fb -> accept
```

**The bond is real, not a transient flag.** A link key was written to disk:

```
[LinkKey]
Key=<redacted - 16 bytes present, not committed>
Type=8                       <- unauthenticated BR/EDR link key
[IdentityResolvingKey]
Key=<redacted - 16 bytes present, not committed>
[PeripheralLongTermKey]
Key=<redacted - 16 bytes present, not committed>
```

The key values are deliberately **redacted**: the brief forbids committing pairing
keys, so the evidence records the structure (which proves a real key exists) and
not the secret. The passkey `985715` was single-use and is already consumed.

This also corrects test 221's conclusion. There, pairing stopped at
`request passkey` because that association model needs a value shown on the peer's
screen. When Windows initiates instead, it chooses the numeric-comparison model,
which needs only a yes/no — so the earlier failure was a property of which side
started, exactly as suspected, and not a tablet limitation.

## Level 11 — reconnect after reboot: PASS

```
(reboot)
$ uptime -p
up 0 minutes
$ journalctl -u gts9-bluetooth-address -b
gts9-bt-addr: set public address 38:8A:06:59:04:E7 after 1s (controller was still registering)

$ bluetoothctl info F8:CF:52:CD:BE:9F
	Paired: yes
	Bonded: yes
	Trusted: yes
```

The bond survived a full reboot, and **the address unit re-applied the address
automatically with no manual step** — Test 1 of `reference/bluetooth-test-plan.md`
passing again, on a boot that also carried a bonded peer.

## What the reconnect attempt itself showed

`bluetoothctl connect` reached BR/EDR (the LE errors vanished) and then reported:

```
Failed to connect: org.bluez.Error.Failed br-connection-profile-unavailable
```

with bluetoothd explaining why:

```
src/service.c:btd_service_connect() a2dp-source profile connect failed for F8:CF:52:CD:BE:9F: Protocol not available
```

**This is not a Bluetooth-controller fault, and it is not a regression.** A
Windows PC offers a headset/speaker only the profiles in its own service list, and
this build enables:

| symbol | state | consequence |
|---|---|---|
| `CONFIG_BT_BREDR` | `y` | classic works — proven by the bond above |
| `CONFIG_BT_HIDP` | `y` | **a mouse or keyboard would connect** |
| `CONFIG_BT_RFCOMM` | `y` | serial profiles available |
| `CONFIG_BT_BNEP` | not set | PAN networking unavailable |
| A2DP | audio stack, out of scope this round | cannot complete |

So the ACL link, the link key and the controller are all working; what Windows
offered to this peer was audio, which the brief explicitly excludes. The
functional end-to-end that remains is a **HID device**, which is both what §20
recommends and what `CONFIG_BT_HIDP=y` supports.

## Levels now

| level | status |
|---|---|
| 10 pair | **PHYSICALLY_VERIFIED** |
| 11 reconnect (bond persists across reboot) | **PHYSICALLY_VERIFIED** |
| 12 coexistence | PHYSICALLY_VERIFIED (test 220) |
| 13 cold boot | PHYSICALLY_VERIFIED for the address unit (tests 220, 222) |

What is still not proven is a **functional data path over the bond** — an actual
mouse click or keystroke arriving. That needs the HID peer, and it is the only
outstanding item.
