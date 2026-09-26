# The fast debug channel: USB networking, ssh and adb

Until 2026-09-25 the only way into the X710 was the USB serial console, and it
moves about **3 KB/s**. That is not a baud-rate problem — see below — and it made
every investigation slow. The same USB cable now carries a network link, and over
it **ssh at 31.8 MB/s** and **adb at 70.5 MB/s**.

## Raising the console baud does nothing, and that was measured

`COM17`/`COM19` are USB **CDC-ACM gadget** ports, not a UART. The gadget
negotiates `high-speed` (`/sys/class/udc/a600000.usb/current_speed`), and the bytes
travel in USB bulk transfers; the host's line coding is nominal. Measured with the
same 131072-byte payload:

| host baud | elapsed |
|---|---|
| 115200 | 40 s |
| 921600 | 40 s |

Identical to the second. `scripts/console-run.sh` takes `-Baud` so this can be
re-checked rather than believed.

Two more things about that console are worth knowing, because both cost time:

* **A large write to `/dev/ttyGS1` blocks the shell** if nothing is draining the
  port. Writing 128 KiB to it while reading `COM17` wedged the shell until `COM19`
  was opened and drained. `gts9-acm-getty` is not the only thing on that cable.
* The host's reader logs a line when the port closes; before this round it wrote a
  full PowerShell stack trace **per loop iteration**, turning captures into
  megabytes of noise. That is fixed in `console-run.ps1`.

## What was added

A **CDC-NCM** function on the same gadget, so the composite device keeps its
identity and the COM port numbers do not move:

```
USB\VID_0525&PID_A4A7\GTS9WIFI-0001     USB Composite Device
USB\VID_0525&PID_A4A7&MI_00  ->  COM17
USB\VID_0525&PID_A4A7&MI_02  ->  COM19
USB\VID_0525&PID_A4A7&MI_04  ->  "UsbNcm Host Device", 426 Mbps
```

Windows binds its own in-box NCM driver, so **no INF, no admin rights and no
kernel change were needed** — `CONFIG_USB_CONFIGFS_NCM=y` was already set.

The function is **opt-in and console-safe**. With no `/etc/gts9-usb-net` the gadget
is exactly the ACM-only console it always was. With it:

```
ncm 169.254.42.1/16
```

`gts9-usb-acm` adds `ncm.usb0` to its own configuration before binding the UDC —
not a second gadget, because a UDC binds one gadget at a time and Debian's adbd
package wants to create its own. If the function cannot be created, or the bind
fails, the function is dropped and the ACM console comes up as before.

Address choice matters. Windows gives the adapter an APIPA address
(`169.254.221.224/16`) with no configuration, so the device is put in the **same
/16**. That needs no `New-NetIPAddress`, and therefore no elevation, and WSL2
reaches it through the Windows host:

```
$ ping -c1 169.254.42.1
64 bytes from 169.254.42.1: icmp_seq=1 ttl=64 time=2.12 ms
```

## ssh

`sshd` was already running; only key auth was missing, and
`scripts/gts9-ssh.sh` is the wrapper:

```sh
scripts/gts9-ssh.sh 'dmesg | tail -20'
scripts/gts9-ssh.sh -- scp file.bin /tmp/          # any ssh-family command
```

### Installing the key — `install-key` no longer works, and this is the gap to close

`scripts/gts9-debug-channel.sh install-key` used to write the public key into
`/root/.ssh/authorized_keys` **over the COM17 serial console**, by sending a
`mkdir -p /root/.ssh && echo '<pubkey>' >> …` line to the shell there.

That path is dead. COM17 is a working serial port but nothing runs a shell on it
any more — the autologin getty was deleted and the kernel console was removed
(both were the cause of the boot and shutdown stalls; see
[the boot console block](BOOT_CONSOLE_BLOCK.md) and
[shutdown delay](SHUTDOWN_DELAY.md)). The command still runs and still fails
silently, because `console-run.sh` finds no shell to answer its heartbeat.

So **a freshly installed rootfs has no way to receive a key**, and since the
serial console used to be the fallback, this is the one capability the removal
actually took away. It needs replacing, and there are two candidate routes:

* **write the key into the rootfs at install time** — `install-debian-rootfs.sh`
  gains an `--ssh-key` option that installs it to `/root/.ssh/authorized_keys` in
  the target tree. This is what the Fedora port for this board does
  (`rootfs/build-rootfs.sh`: `install -Dm600 -o 1000 -g 1000 …authorized_keys`),
  and it needs no channel on the device at all.
* **allow a password login for the first boot** and use `ssh-copy-id`. Simpler,
  but it requires a known root password on a device that ships with none.

Until one of them is implemented, a rootfs deployed by this repository can only be
reached by an operator who already had a key on it, or through TWRP.

Measured: `dd if=/dev/zero bs=1M count=128 | ssh … 'cat > /dev/null'` →
**31.8 MB/s**.

## adb

`adbd` is a real Debian package and `adbd 34.0.5-12` is in **trixie**, the release
the tablet runs. `scripts/fetch-adbd-packages.sh` downloads the daemon and its five
missing dependencies with pinned SHA256s; they are installed with `dpkg -i`.

`adbd` runs over its **TCP transport**, not the USB FunctionFS one, and that is
deliberate: the FunctionFS route needs `ffs.adb` inside the gts9 gadget *and* a
Windows driver bound to `VID_0525&PID_a4a7`, whereas TCP needs neither. So
`gts9-adbd.service` runs `adbd` on its own and the network path comes from the NCM
function. It deliberately does **not** use the helper Debian ships
(`adbd-usb-gadget`), which creates its own gadget and cannot bind while the console
owns the controller.

```
$ adb connect 169.254.42.1:5555
connected to 169.254.42.1:5555
$ adb shell id
uid=0(root) gid=0(root) groups=0(root)
$ adb push 64MiB.bin /tmp/
64 MiB in 0.907s = 70.5 MB/s
```

`adbd` logs `Failed to get adbd socket` and `socket unavailable, disabling user
prompts` on a non-Android system. Both are expected — there is no Android framework
to ask — and neither stops it working.

### Mask Debian's own `adbd.service` — installing the package enables it

This is not optional, and getting it wrong cost a device wedge. Installing `adbd`
leaves Debian's `adbd.service` **enabled**, and it is not the unit above:

```
$ systemctl status adbd.service
   Active: failed
   Process: ExecStartPre=.../adbd-usb-gadget setup     (code=exited, status=0/SUCCESS)
   Process: ExecStart=.../adbd                         (code=killed, signal=TERM)
   Process: ExecStartPost=.../adbd-usb-gadget activate (code=exited, status=1/FAILURE)
   Process: ExecStopPost=.../adbd-usb-gadget reset     (code=exited, status=32)
```

`setup` succeeds, and that is the problem: it creates a **second** gadget at
`/sys/kernel/config/usb_gadget/g1`, mounts FunctionFS at `/dev/usb-ffs/adb`, and
runs a second `adbd`. `activate` then fails, because the UDC binds one gadget at a
time and `gts9` owns it — and `reset` cannot fully undo the work, so a stray `g1`
gadget is left in configfs. Every boot therefore churned the USB gadget and left
`systemctl --failed` non-empty.

So:

```sh
systemctl disable adbd.service          # remove the multi-user.target.wants link
ln -sf /dev/null /etc/systemd/system/adbd.service   # and mask it
systemctl daemon-reload
```

`gts9-adbd.service` is unaffected — it does not use the gadget helper at all, which
is exactly why it works while the packaged one cannot.

If a stray gadget is already there:

```sh
G=/sys/kernel/config/usb_gadget/g1
echo "" > $G/UDC; umount /dev/usb-ffs/adb; rmdir /dev/usb-ffs/adb
rm -f $G/configs/c.1/ffs.adb
rmdir $G/configs/c.1/strings/0x409 $G/configs/c.1 $G/functions/ffs.adb \
      $G/strings/0x409 $G
```

## Bringing it up on a fresh rootfs

```sh
# 1. the gadget side (repo -> device)
install -m 0755 rootfs-overlay/usr/libexec/gts9-usb-acm   /usr/libexec/
install -m 0644 rootfs-overlay/usr/lib/systemd/system/gts9-adbd.service \
                                                          /usr/lib/systemd/system/
install -m 0644 rootfs-overlay/etc/gts9-usb-net           /etc/gts9-usb-net
/usr/libexec/gts9-enable-units && systemctl daemon-reload

# 2. the packages
scripts/fetch-adbd-packages.sh
scp .work/downloads/adbd-trixie/*.deb root@169.254.42.1:/tmp/
ssh root@169.254.42.1 'dpkg -i /tmp/libprotobuf32t64_*.deb /tmp/android-lib*.deb /tmp/adbd_*.deb'

# 3. the key - NOT `install-key`, which relied on the serial console that no
#    longer has a shell on it.  Put the key into the rootfs before first boot:
#      ./scripts/install-debian-rootfs.sh --ssh-key ~/.ssh/id_ed25519.pub /mnt/debian
#    (or, once implemented, use that option's device-side equivalent)

# 4. mask the unit the package enabled, then start ours
ssh root@169.254.42.1 'systemctl disable adbd.service; \
    ln -sf /dev/null /etc/systemd/system/adbd.service; systemctl daemon-reload; \
    systemctl enable --now gts9-adbd.service'
```

Step 3 is the one that changed with the console removal, and it is the step to get
right: a rootfs deployed without a key can only be reached by an operator who
already had one on it, or through TWRP.

Verified end to end across a reboot on 2026-09-25: the gadget came back with NCM,
`usb0` came back with its address, `gts9-adbd.service` came back active, and both
ssh and `adb connect` worked again without any host-side change.

## What this does not replace

Nothing, any more. This section used to say "the serial console is still the only
channel that exists before `gts9-usb-acm` runs, and the only one that survives a
userspace that has stopped. Keep it." That is no longer true, by decision: both
serial consoles were removed because they caused the boot and shutdown stalls
([why](BOOT_CONSOLE_BLOCK.md)), and the USB network function is now the only
channel off a running system.

What that costs, stated plainly so it is not rediscovered the hard way:

* **Before `gts9-usb-acm` runs there is no channel at all.** The initramfs has no
  network, so a boot that dies before Debian's userspace is only observable on the
  panel. The persistent record `/var/log/gts9-minimal-last-boot` and the Samsung
  `sec_log` ring are what cover that window, and TWRP is the recovery path.
* **A userspace that has stopped cannot be interrogated.** There is no port to
  attach a terminal to. `docs/STALL_FAILURE_SHAPE.md`'s evidence was all gathered
  through the serial console and cannot be gathered the same way again.
* `gts9-kmsg-console` remains as an opt-in userspace mirror of `/dev/kmsg` for the
  live case (`gts9_kmsg_mirror=1`), but it is a userspace process: it is gone the
  moment userspace stops, which is exactly when it would be most useful.
