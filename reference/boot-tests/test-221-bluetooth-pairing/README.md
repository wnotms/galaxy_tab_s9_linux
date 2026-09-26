# Test 221 — pairing against a real peer (level 10)

**Result: NOT_TESTED, but it advanced further than a "no peer available" note
would suggest.** A real BR/EDR peer was found and the pairing reached the SSP
passkey exchange, where it stopped for a reason that belongs to the peer, not to
the tablet.

## What was attempted

The Windows host beside the tablet has an Intel Bluetooth adapter. It is a real,
independent BR/EDR device, so it was used as the peer instead of nothing:

| direction | result |
|---|---|
| host discovers the tablet | **works** — `38:8A:06:59:04:E7  gts9` |
| tablet pairs with the host | **reaches SSP, then refused** |

The tablet's side, in order:

```
$ btmgmt pair -c 2 -t 0 F8:CF:52:CD:BE:9F      # -t 0 = BR/EDR
Pairing with F8:CF:52:CD:BE:9F (BR/EDR)
hci0 F8:CF:52:CD:BE:9F type BR/EDR connected eir_len 17   <- page + ACL up
hci0 F8:CF:52:CD:BE:9F request passkey                    <- SSP started
Pairing with F8:CF:52:CD:BE:9F (BR/EDR) failed. status 0x05 (Authentication Failed)
```

and a BlueZ agent on the system bus **was consulted**:

```
AGENT REGISTERED
AGENT RequestPasskey -> 0
```

ACL traffic moved in both directions (`acl:7` rx, `acl:8` tx), so this is a real
link, not advertising.

## Why it stopped, and why that is the peer's limitation

`request passkey` is the HCI event for the **passkey-entry** association model:
the *remote* displays a passkey and the local side must enter it. The agent
answered `0` and authentication failed, because no agent can supply a value that
is being displayed on a screen it cannot see — Windows chose DisplayOnly for this
adapter and shows a dialog, and this test cannot click it.

That is a property of the Windows peer. Steps 1–3 above are the parts that matter
for this project, and all three worked: page, SSP negotiation, and the agent
callback.

LE pairing was attempted too (`-t 1`) and did not engage: this Windows adapter is
central-only, so it never advertises or accepts an LE pairing from the tablet.

## Therefore level 10 stays NOT_TESTED

No bond was created, so there is nothing to reconnect and level 11 also stays
NOT_TESTED. The levels are not marked as passed on the strength of getting close:

* the test plan asks for a **mouse or keyboard**, and that is still the right
  peer — a HID device uses "Just Works" and completes without a screen;
* "pairing reached the passkey exchange" is not "pairing works".

The one thing this run does establish is that the tablet's controller, firmware,
address and BlueZ agent path are all functional enough to page a real device and
begin authenticated pairing — which is a stronger statement than the earlier
"no peer available".

## State left on the tablet

Two Debian packages were installed to get a working pairing agent, because this
rootfs has no D-Bus bindings and `bluetoothctl` cannot register an agent over
ssh:

| package | why |
|---|---|
| `python3-dbus` | the agent needs to own a name on the system bus |
| `python3-gi` | dbus-python needs a GLib mainloop; without it the agent cannot service calls |

**They are test scaffolding, not part of this project.** The shipped rootfs has no
pairing agent by design — BlueZ's own agent is started by a desktop session, and
this image is headless — so nothing in the repository depends on either package.
Remove them if the tablet is meant to match the repository exactly:

```sh
apt-get remove --purge python3-dbus python3-gi
```

The temporary agent (`/tmp/btagent.py`), the cached peer entry and the
discoverable/pairable flags were all cleaned up; `pairable` and `discoverable`
are back to `no`.
