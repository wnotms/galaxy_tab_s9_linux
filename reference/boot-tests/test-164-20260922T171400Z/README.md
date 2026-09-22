# test-164 — Debian first boot, evidence collected over the serial console

The handoff goal was already confirmed by the owner; this is the section 22/23 evidence,
gathered from a shell on the tablet itself over the ttyMSM0 serial line.

```
$ uname -a
Linux gts9 7.2.0-rc3-gts9wifi-dirty #1 SMP PREEMPT Sun Jul 12 21:16:39 UTC 2026 aarch64 GNU/Linux

$ cat /etc/os-release
PRETTY_NAME="Debian GNU/Linux 13 (trixie)"
NAME="Debian GNU/Linux"
VERSION_ID="13"

$ ps -p 1 -o pid,comm,args
    PID COMMAND         COMMAND
      1 systemd         /sbin/init

$ findmnt /
TARGET SOURCE         FSTYPE OPTIONS
/      /dev/mmcblk1p1 ext4   rw,noatime

$ lsblk -f | grep mmcblk1
mmcblk1
mmcblk1p1 ext4   1.0   debian-root 851819a7-0d96-4217-b64a-aeeee5d8be61  106.4G     1% /

$ cat /proc/cmdline | tr ' ' '\n' | grep -E 'gts9_rootfs|gts9_proof|gts9_reboot|console=|loglevel'
console=ttyMSM0,115200n8
gts9_rootfs=/dev/mmcblk1p1
loglevel=4
console=null            <- the bootloader's own append, which ignore_console_null is for

$ cat /sys/class/tty/tty0/active
tty1

$ systemctl status getty@tty1 --no-pager | head -4
getty@tty1.service - Getty on tty1
     Loaded: loaded (/usr/lib/systemd/system/getty.service; enabled; preset: enabled)
     Active: active (running) since ...; 22min ago

$ systemctl --failed --no-pager
0 loaded units listed.

$ cat /proc/bus/input/devices | grep -A5 EF-DX710
N: Name="Book Cover Keyboard Slim (EF-DX710)"
S: Sysfs=/devices/platform/soc@0/8c0000.geniqup/89c000.i2c/i2c-5/5-002a/input/input0
H: Handlers=sysrq kbd leds event0

$ ls /dev/input/ ; command -v evtest
by-path event0 event1
/usr/bin/evtest
```

Every item the task asked to check is answered: systemd is PID 1, the root filesystem is
the microSD partition with its `debian-root` label mounted rw, the cmdline carries
`gts9_rootfs=` and no `gts9_proof_code`/`gts9_proof_action`/`gts9_reboot_after`, the
foreground VT is tty1, getty@tty1 is enabled and running, systemd reports no failed units,
and the pogo keyboard still carries the `kbd` handler with `event0`.  The Windows serial
console hosts a shell on the tablet as well now, which is where this was collected.

## Deliberately not in this repository

The raw console captures live outside the tree and are not committed: they contain the
login attempt typed while opening the session.  No credential - username or password -
is written into this repository, by the owner's explicit instruction, and none appears in
the commits.

## Not measured

`evtest` against a live key press was not run; the handler line above shows the device is
still bound to the keyboard handler, which is what that check was for.
