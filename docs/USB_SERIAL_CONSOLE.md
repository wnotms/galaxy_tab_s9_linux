# USB serial console on Debian

This note records the verified console mapping for the SM-X710 mainline boot so later
bring-up work does not confuse the physical Qualcomm UART with the USB gadget serial port.

## Interface mapping

| Linux device | Transport | Purpose |
| --- | --- | --- |
| `/dev/tty1` | framebuffer VT + EF-DX710 keyboard | local tablet login |
| `/dev/ttyGS0` | USB ConfigFS ACM gadget | Windows USB COM login |
| `/dev/ttyMSM0` | Qualcomm GENI UART | physical UART / kernel console |

The kernel cmdline intentionally contains:

```
console=ttyMSM0,115200n8
```

That selects the Qualcomm UART as a kernel console. It does **not** mean that a Windows COM
device created by the USB-C gadget maps to `ttyMSM0`.

## Why the Windows COM port was present but silent after switch_root

`boot/bringup-init.sh` creates the ConfigFS ACM gadget before the Debian rootfs handoff.
The gadget therefore exists and `/dev/ttyGS0` survives when `/dev` and `/sys` are moved
into the new root.

On a successful Debian boot, however, the handoff does:

```
exec switch_root /newroot /sbin/init
```

before the later initramfs code that would start a BusyBox shell on `/dev/ttyGS0`.
Consequently Windows can enumerate and open the COM port while no userspace process in
Debian is reading or writing the tty.

This is expected ownership after a successful handoff: the initramfs should not leave its
BusyBox shell alive inside the Debian system.

## Debian fix

Enable systemd's serial getty on the USB gadget tty:

```
sudo systemctl enable --now serial-getty@ttyGS0.service
```

Verified on the tablet: Windows serial access works after this service is enabled. Because
the unit is enabled, subsequent Debian boots should start it automatically whenever
`/dev/ttyGS0` is present.

Useful checks:

```
ls -l /dev/ttyGS0
systemctl is-enabled serial-getty@ttyGS0.service
systemctl status serial-getty@ttyGS0.service --no-pager
cat /sys/kernel/config/usb_gadget/gts9/UDC
```

If the service is active but Windows sees no device, debug the ConfigFS gadget/UDC path.
If Windows sees the COM port but it is silent, first check which process, if any, owns
`/dev/ttyGS0`.

## ttyMSM0 remains separate

A `serial-getty@ttyMSM0.service` may also be enabled when a userspace login is wanted on
the physical Qualcomm UART, but that service does not provide the Windows USB ACM console.

Do not replace `ttyGS0` with `ttyMSM0` in USB-console documentation, tests or scripts.
