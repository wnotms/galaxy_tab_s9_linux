# Round 7: the anomalous boot was mid-shutdown, and the evidence channels measured

Three questions answered by measurement on the device this round. One earlier
conclusion is **corrected**.

## 1. The anomalous boot was interrupted during SHUTDOWN, not during startup

`…-8d7db274` (`previous_boot_end=hard-reset-or-incomplete`) ends with an ordinary
shutdown sequence in progress, at 70.5 s:

```
[   70.502896] systemd[1]: Stopped target multi-user.target - Multi-User System.
[   70.503293] systemd[1]: Stopping cron.service ...
[   70.503721] systemd[1]: Stopping gts9-acm-getty.service ...
[   70.505368] systemd[1]: Stopped target getty.target - Login Prompts.
[   70.505990] systemd[1]: Stopping getty@tty1.service ...
[   70.506420] systemd[1]: Stopping gts9-power-key.service ...
[   70.506895] systemd[1]: Stopped gts9-prev-boot-evidence.service ...
```

and it contains **three** `Connection terminated` errors just before, from
`systemd-logind`, `systemd-hostnamed` and `systemd-networkd`:

```
[   62.605911] systemd-logind.service: Unexpected error response on installing
              NameOwnerChanged signal match: Connection terminated
```

`Connection terminated` on those three units means **`dbus.service` had already
gone away** — i.e. the shutdown was well advanced. Then `systemd-shutdown` never
appears (a clean boot has exactly two `systemd-shutdown` lines; this boot has
zero).

So the sequence is: **shutdown begins normally → services stop → the record ends
before `systemd-shutdown` runs → the machine resets.** This is a failure to
*complete a shutdown*, not a failure to boot.

That also fits the episodes observed live: they followed `systemctl reboot`
issued from the shell.

## 2. pstore still does not survive a reboot — re-measured, not assumed

The DTS comment (test-183) said records do not survive. That was measured before
this round's kernel changes, so it was re-measured directly:

| step | result |
|---|---|
| backend state | `pstore: Registered ramoops as persistent store backend`, `printk: legacy console [ramoops-1] enabled`, `ramoops: using 0x200000@0x880900000, ecc: 0` |
| `/dev/pmsg0` | **present** (`252,0`) — note test-183 recorded no such node |
| parameter sizes | `record_size=131072`, `console_size=524288`, `pmsg_size=2097152` |
| write | `echo GTS9_PMSG_MARKER_… > /dev/pmsg0` → `written` |
| `systemctl reboot`, then read | `/sys/fs/pstore/` **empty**; `grep -ral GTS9_PMSG_MARKER /sys/fs/pstore/` finds **nothing** |

The reboot itself succeeded (uptime came back at 316 s), so this is not a failed
reboot masking the result. **The 2 MiB region at `0x8_80900000` does not survive a
reset on this board**, regardless of `no-map` and the reserved-memory declaration.
Kernel-panic capture via pstore is therefore unavailable, and that is now a
measured fact for the current kernel rather than an inherited note.

## 3. The host console DOES carry kernel output — correcting round 6

Round 6 concluded that COM19 carries only userspace output. **That was wrong**,
and the error was mine: the test wrote to `/dev/kmsg` without controlling the
loglevel.

`/proc/sys/kernel/printk` is `4.4.1.7` — console loglevel **4**, so `KERN_INFO`
is suppressed by design. Repeating the test with the level raised:

```
$ cat /sys/class/tty/console/active
tty0 ttyMSM0 ttyGS1
$ dmesg -n 8; echo GTS9_KERNEL_MARKER_B > /dev/kmsg
```
```
2026-09-24T19:48:19Z RECV  [  345.478381][ T1011] GTS9_KERNEL_MARKER_B
```

The marker arrived on COM19. So `ttyGS1` **is** a working kernel console and
`docs/USB_SERIAL_CONSOLE.md` is correct; what failed in round 6 was the test, not
the console.

**Why this matters for the stall:** panic output is emitted at `KERN_EMERG`,
which bypasses the loglevel, so **a host console capture spanning a reset will
capture a panic report.** That is the one experiment capable of settling whether
the shutdown failure panics, and it is now known to be viable. Round 6 had
written it off.

## What is now established for the next attempt

1. Capture **COM19 with a host process left running across the reboot** — it will
   carry a panic if one occurs.
2. Trigger the suspect path directly: `systemctl reboot`.
3. Detect the failure as "the device never returns a command result" (the
   `status=stalled-or-no-shell` gate), or as a reset with no `systemd-shutdown`.
4. Read the restored console log for a panic banner; if there is none, the
   shutdown failure is a hang that the watchdog does not classify as a soft
   lockup — which is itself a strong statement about the mechanism.
