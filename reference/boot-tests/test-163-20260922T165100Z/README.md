# test-163 — the Debian microSD boot works: switch_root handed PID 1 to the card

Owner report, after flashing `vendor_boot 4b3df932` (cmdline with
`gts9_rootfs=/dev/mmcblk1p1`) and `init_boot a121147d`: **Debian is up and basic commands
work, typed on the tablet.** That is the section 24 chain - kernel, panel, pogo keyboard,
mmcblk1p1, ext4, switch_root, systemd, tty1 login - reached end to end.

## What is implemented

`boot_rootfs()` in `boot/bringup-init.sh`, reached after the display and pogo bring-up and
before `start_panel_shell`:

```
requested root device -> wait for the block device (15 s, GTS9_ROOTFS_WAIT_MS)
-> mount -t ext4 -o rw on /newroot -> require /newroot/sbin/init
-> require the switch_root applet -> create /newroot/{dev,proc,sys,run}
-> mount --move each virtual filesystem (falling back to -o move, warning only)
-> exec switch_root /newroot /sbin/init
```

Ordering is the safety property: every check that can fail happens before the irreversible
part, the moves come last, and `exec switch_root` is the only statement after them. A
return from `boot_rootfs()` therefore means no handoff happened and the caller falls back to
the BusyBox rescue environment - no panic, no reboot, PID 1 never exits. In rootfs mode the
root device is refused as a USB mass-storage backing whatever the cmdline says, and the
proof/recovery timers are disabled so nothing reboots the tablet out from under Debian.

Commits: `477d21a` (the handoff), `8446136` (the Debian cmdline profile), `d11fd3b` (keep
the rescue shell reachable when a handoff fails).

## Correction recorded here too

When the first candidate was flashed I read the silent *serial* line as "handoff failed and
the rescue shell was suppressed". Both halves were wrong: the handoff had succeeded, and the
serial has no userspace getty because systemd's getty generator only matches known serial
name prefixes - `ttyMSM0` is not one of them. The guard removal in `d11fd3b` is still
correct for the failure path, which is what section 18 asks for.

## Owed: the three key confirmations from the owner

Requested from the tty1 session (the screen with the pogo keyboard), because neither the
serial console nor my host tools can reach a shell inside Debian:

```
cat /etc/os-release                       expect Debian GNU/Linux 13 (trixie)
ps -p 1 -o pid,comm,args                  expect systemd
findmnt /                                 expect source /dev/mmcblk1p1
```

Also decided: the owner wants a `serial-getty@ttyMSM0` so the Windows serial console can
host a shell in Debian as well, which needs one file inside the rootfs - their explicit
authorisation for this change, since the stage normally forbids touching the card's
contents.
