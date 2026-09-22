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

## Correction: Windows USB serial is ttyGS0, not ttyMSM0

The first Debian candidate was initially diagnosed from a silent Windows COM port. The
handoff had actually succeeded. The host-visible Windows COM port is the USB gadget ACM
function, whose device-side tty is `/dev/ttyGS0`.

`ttyMSM0` is a different interface: it is the Qualcomm GENI UART selected by
`console=ttyMSM0,115200n8` for the kernel console. It must not be used as the name for the
Windows USB ACM path.

The initramfs creates the ACM gadget before `boot_rootfs()`. On a successful rootfs boot,
`exec switch_root /newroot /sbin/init` runs before the later BusyBox `ttyGS0` shell code,
so the gadget survives the handoff but no initramfs userspace shell is left reading it.
Debian therefore needs its own getty on `ttyGS0`:

```
sudo systemctl enable --now serial-getty@ttyGS0.service
```

The owner verified that Windows serial access works after enabling that service. See
`docs/USB_SERIAL_CONSOLE.md` for the stable mapping and the reason for the silent-port
symptom.

## Owed: the three key confirmations from the owner

Requested from the tty1 session (the screen with the pogo keyboard):

```
cat /etc/os-release                       expect Debian GNU/Linux 13 (trixie)
ps -p 1 -o pid,comm,args                  expect systemd
findmnt /                                 expect source /dev/mmcblk1p1
```

## Owner confirmations (the three key items)

```
Debian GNU/Linux 13 (trixie)
systemd
/dev/mmcblk1p1
```

That closes the chain the task asked for, each link observed on hardware:

```
Samsung ABL -> mainline boot.img -> SM-X710 DTB -> this initramfs
  -> /dev/mmcblk1p1 (ext4, mounted rw on /newroot)
  -> switch_root -> systemd as PID 1 -> getty@tty1 on the panel
  -> EF-DX710 keyboard login -> Debian shell
```

The Debian boot goal is met. The Windows USB serial login is now independently verified via
`serial-getty@ttyGS0.service`. A getty on `ttyMSM0`, if explicitly enabled for a physical
UART setup, is separate from the USB ACM console.
