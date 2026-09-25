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

`sshd` was already running; only key auth was missing. `scripts/gts9-debug-channel.sh
install-key` installs the operator's public key into `/root/.ssh/authorized_keys`
over the console, and `scripts/gts9-ssh.sh` is the wrapper:

```sh
scripts/gts9-ssh.sh 'dmesg | tail -20'
scripts/gts9-ssh.sh -- scp file.bin /tmp/          # any ssh-family command
```

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

## Bringing it up on a fresh rootfs

```sh
# 1. the gadget side (repo -> device)
install -m 0755 rootfs-overlay/usr/libexec/gts9-usb-acm   /usr/libexec/
install -m 0644 rootfs-overlay/usr/lib/systemd/system/gts9-adbd.service \
                                                          /usr/lib/systemd/system/
printf 'ncm 169.254.42.1/16\n' > /etc/gts9-usb-net
/usr/libexec/gts9-enable-units && systemctl daemon-reload

# 2. the packages
scripts/fetch-adbd-packages.sh
scp .work/downloads/adbd-trixie/*.deb root@169.254.42.1:/tmp/
ssh root@169.254.42.1 'dpkg -i /tmp/libprotobuf32t64_*.deb /tmp/android-lib*.deb /tmp/adbd_*.deb'

# 3. the key
scripts/gts9-debug-channel.sh install-key

# 4. start
ssh root@169.254.42.1 'systemctl enable --now gts9-adbd.service'
```

Verified end to end across a reboot on 2026-09-25: the gadget came back with NCM,
`usb0` came back with its address, `gts9-adbd.service` came back active, and both
ssh and `adb connect` worked again without any host-side change.

## What this does not replace

The serial console is still the only channel that exists **before** `gts9-usb-acm`
runs, and the only one that survives a userspace that has stopped. Everything in
`docs/STALL_FAILURE_SHAPE.md` was found through it. Keep it.
