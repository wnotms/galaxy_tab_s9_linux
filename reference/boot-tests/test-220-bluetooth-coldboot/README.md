# Test 220 — the Bluetooth address unit, on a real cold boot

**Results: Test 1 PASS, Test 2 PASS (after a fix), Test 3 PASS, Test 4 PASS,
Test 6 PASS. Test 5 (pairing) and Test 7 (cold boot after pairing) NOT RUN** —
no peer device was available, and the tablet wedged again before they could be.

This is the first run of `reference/bluetooth-test-plan.md`. It found two real
bugs in the fix, both of which only appear on hardware.

## Test 1 — the unit applies the address automatically: PASS, after a fix

The first attempt **failed**, and the failure is the useful part:

```
Sep 26 21:08:59 gts9-bluetooth-address[840]: gts9-bt-addr: could not set the
    public address: Set Public Address for hci0 failed with status 0x11 (Invalid Index)
```

The unit *had* run automatically — the earlier `ConditionPathExists` bug was
genuinely fixed — but it raced the controller. Measured on the tablet:

| readiness point | when |
|---|---|
| `hci0` present in `/sys/class/bluetooth` | **+0 s** |
| `btmgmt public-addr` accepted | **+1 s** |

So checking for the sysfs node and acting once was not enough: the node exists
while the controller is still in `HCI_SETUP`, and the management layer answers
`Invalid Index`. The helper now treats that reply as a retry condition.

After the fix, on a subsequent cold boot, with **no manual step**:

```
Sep 26 21:14:47 gts9-bluetooth-address[676]: gts9-bt-addr: set public address
    38:8A:06:59:04:E7 after 1s (controller was still registering)
Sep 26 21:14:48 gts9 systemd[1]: Finished gts9-bluetooth-address.service
```

```
$ hciconfig hci0
hci0:	BD Address: 38:8A:06:59:04:E7  ACL MTU: 1024:7  SCO MTU: 240:4
	UP RUNNING
```

Boot `dd0336cd`, `up 0 minutes` at the time of capture. Files: `unit-status.txt`,
`controller.txt`.

## Test 2 — idempotency: PASS, after a fix

Also found a bug. Re-running the unit against an **already-configured**
controller reported `bluetooth-address-failed`, because `public-addr` then
answers:

```
Set Public Address for hci0 failed with status 0x0b (Rejected)
```

`Rejected` is not an error — the controller already has an address and refuses to
take another one. The controller was never disturbed (`unchanged: yes`, and its
address and MTU were identical before and after), but the *reporting* was wrong,
and a wrong stage would have been read as a regression.

The helper now decides the outcome by **re-reading the controller's address**
rather than by parsing the reply, because the three replies are ambiguous:

| controller state | reply | correct meaning |
|---|---|---|
| not configured | `... complete` | accepted |
| mid-transition | `... 0x11 (Invalid Index)` | retry |
| already configured | `... 0x0b (Rejected)` | already done, not a failure |

It also now checks the address *before* acting at all, so an already-configured
controller gets no management call whatsoever:

```
gts9-bt-addr: controller already reports 38:8A:06:59:04:E7; leaving it alone
```

The address is read with `hciconfig`, which needs no daemon and no management
socket. (Sysfs was checked and exposes no address attribute:
`/sys/class/bluetooth/hci0/` holds only `device power reset rfkill0 subsystem
uevent`.) File: `idempotency.txt`.

## Test 3 — Bluetooth power cycling does not disturb Wi-Fi: PASS

The brief's §25 concern. Wi-Fi state and latency are identical with Bluetooth
off, and the PCI endpoint never disappears:

```
--- before ---                    wlp1s0 UP 10.191.121.48/24   0% loss, avg 19.2 ms
--- after bluetooth power off --- wlp1s0 UP 10.191.121.48/24   0% loss, avg 31.7 ms
pci endpoint: /sys/bus/pci/devices/0000:01:00.0
--- after power on ---            BD Address: 38:8A:06:59:04:E7  ACL MTU: 1024:7
```

The controller returns cleanly after `power on`. File: `coexistence-power.txt`.

## Test 4 — scan: PASS

`btmgmt find` discovers both named and unnamed LE devices:

```
hci0 dev_found: FF:0F:62:31:03:02 type LE Public rssi -96  name TBIT-WD219G
hci0 dev_found: C4:7F:0E:33:30:DF type LE Public rssi -81  name KLCXKJ-Water
```

BR/EDR inquiry starts and completes cleanly (`hci0 type 1 discovering on/off`)
with no classic device in range. **Test condition: only BLE devices were
available in this location.** Files: `scan.txt`, `scan-bredr.txt`.

## Test 6 — coexistence: PASS

| case | result |
|---|---|
| A Wi-Fi up, Bluetooth off | association held, 0% loss |
| B Wi-Fi up **while scanning** | 10/10 pings, 0% loss, association unchanged |
| C Bluetooth up + transfer | no `ath11k` reset, no MHI RDDM, no controller reset |

```
--- resets during the test? ---
(none - clean)
```

**One honest caveat, established by A/B rather than assumed.** The first
attempt at case C showed HTTP transfers timing out (`http 000` after 20 s), which
would have looked like a coexistence failure. Running the *same* transfers with
Bluetooth **off** reproduced it, and by a worse margin:

| | Bluetooth ON + scanning | Bluetooth OFF |
|---|---|---|
| HTTP result | 200, 200, 000 | 000, 000, 000 |

so the slow WAN is **not** caused by Bluetooth. It is also not DNS (the name
resolves) and not the certificate problem already documented in this repository
(plain HTTP fails too, and so does a fetch by raw IP). Case C was therefore
re-run as an on-LAN ping test, where it passes cleanly:

```
10 packets transmitted, 10 received, 0% packet loss   (while scanning, BT on)
```

Files: `coexistence-load.txt` (the misleading first run),
`coexistence-baseline.txt` (the A/B control), `coexistence-lan.txt` (the clean
re-run).

## The wedge interrupted the session again

The reboot that was meant to start Test 5 ended in the repository's CPU wedge
again, and this time it presented as a **black screen** rather than the stall
text — the owner saw only a blinking cursor and then nothing. It is the same
failure, and the journal of that boot proves it:

```
Sending NMI from CPU 7 to CPUs 4:
After 10 seconds, these CPUS still haven't responded to the NMI: 4
rcu: rcu_preempt kthread starved for 2502 jiffies! g805 f0x0 RCU_GP_WAIT_FQS(5)
BUG: workqueue lockup - pool cpus=1 node=0 flags=0x0 nice=0 stuck for 52s!
```

"these CPUS still haven't responded to the NMI" is the marker
`docs/CPU_WEDGE_EVIDENCE.md` requires; CPU 4 is one of the CPUs that document
names. The blank screen is a *symptom* of the wedge, not a display regression —
the panel recovered normally on the successful boots either side of it
(`cycle 1 recovered panel ID 80 00 04`).

Recorded as coincident, per the brief. No kernel code was changed this round
(`git diff --exit-code 24dd156 HEAD -- kernel/ boot/` is empty), so nothing in
this work can reach the RCU or CPU layer.

## Still not tested

* **Test 5, pairing and reconnect** — needs a physical Bluetooth mouse or
  keyboard. This is the last level-10/11 claim and it is **not** implied by a
  working scan.
* **Test 7, cold boot after pairing** — blocked by the same missing peer.
* The helper's real `mount` of `efs` at boot did succeed on these boots (the
  address could not have been read otherwise), but the mount was not separately
  instrumented.
