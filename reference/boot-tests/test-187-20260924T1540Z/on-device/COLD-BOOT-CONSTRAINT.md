# A true cold boot is not reachable while USB is attached

Operator-supplied hardware fact, verified against this attempt's capture:

> holding the power key powers the tablet down, and the tablet powers itself back on
> when it is connected to a computer over Type-C. The stock system behaves the same way.

## Measured

```
00:17:57.828  PRESENCE usb0525:a4a7=False      <-- power key pressed, device off
00:17:57.848  port closed (read error)
00:18:08.600  PRESENCE usb0525:a4a7=True       <-- VBUS re-applied, device back on
00:18:08.607  port open on COM19
00:18:09.649  RECV  [    6.470539] gts9-prev-boot-evidence ...
00:18:09.654  RECV  Reached target multi-user.target
```

**11 seconds off.** The tablet came back by itself as soon as VBUS was present. And
the new boot has its own boot id:

```
BID=b0cd2e21-67aa-4fa9-8e90-3d16d74f89a7
```

## The consequence for the experiment

A genuine cold boot — power removed, VBUS absent, battery-only start — **cannot be
observed with the console attached**, because attaching the console is what
re-applies VBUS and reboots the device. The observer changes the thing observed, and
here that is not a subtle effect: it truncates the off period to ~11 s.

So the cold-boot row in the brief's boot taxonomy (cold / warm / panic) is
**unreachable on this bench configuration** unless the console is given up:

* with the cable attached, every power event is a "power-key off, VBUS-on boot";
* without the cable, a true cold boot is possible but **nothing can capture it** —
  no COM port, no console, no host.

The only evidence that survives a cable-free cold boot is what the device writes
about itself: `gts9-prev-boot-evidence` archives each boot, so the *next* attached
boot can report how the unattached boot ended. That gives a verdict and a marker
count, but not the boot's own console output.

## What this attempt DID produce, and it is not nothing

The power-key path is a **distinct boot class** from `systemctl reboot`, and it had
never been exercised:

| boot class | trigger | how many observed | result |
|---|---|---|---|
| warm reboot | `systemctl reboot` over the console | 16 cycles | all clean |
| **power-key off → VBUS-on boot** | operator holds power, cable re-powers | **1** | **clean** |

The prior boot, ended by the power key, reads:

```
previous_boot_end=clean-shutdown
marker_panic=0  marker_soft_lockup=0  marker_hard_lockup=0
marker_hung_task=0  marker_rcu_stall=0  marker_dpu_timeout=0  marker_mmc_timeout=0
```

and its journal ends normally rather than being cut off:

```
[   31.712407] regulator: Not disabling unused regulators
[  627.750978] kworker/u32:1 (13) used greatest stack depth: 9168 bytes left
```

with no `systemd-shutdown`-absent truncation of the kind that defined the round-7
failure. The new boot also shows the panel's cold-enable sequence and recovers:

```
[    0.772087] ana38407 panel id: 00 00 00
[    4.768726] ana38407 panel id: 80 00 04
```

## What remains unreachable

A battery-only cold start. If that is needed, the protocol is:

1. read `/var/log/gts9-boot-evidence/` for the current state and record the newest id;
2. disconnect the cable, power the tablet **off**, confirm it stays off;
3. power it on from the button with the cable still disconnected;
4. wait for a normal boot (4-6 minutes is typical), then reconnect the cable;
5. read the newest evidence directory — it will describe the unattached boot.

That costs the console for the boot itself, and it is the only way to get the
battery-only datapoint. It is a deliberate tradeoff, not an oversight, and it should
only be spent if the battery-only case is believed to matter.
