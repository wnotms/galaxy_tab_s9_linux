# USB serial console on Debian

> **Superseded 2026-09-26.** Both serial debug consoles are removed and the tablet
> is reached over **ssh** on the USB network link — see
> [the fast debug channel](FAST_DEBUG_CHANNEL.md) and
> [test-211](../reference/boot-tests/test-211-no-serial-consoles/README.md).
>
> The mapping below is kept because it is the hardware-verified record the removal
> was based on, and because `ttyMSM0` and the two ACM ports still exist as devices —
> they are simply no longer consoles and no longer have a login on them. Read the
> table as "what these ports are", not as "what this port runs today":
>
> | device | today |
> |---|---|
> | `/dev/tty1` | **the only console** (`console=tty0`), panel VT + `getty@tty1` |
> | `/dev/ttyGS0`, `/dev/ttyGS1` | ACM ports, created by `gts9-usb-acm`, **no console and no getty**; `CONFIG_U_SERIAL_CONSOLE` is unset, so the configfs `console` attribute does not exist |
> | `/dev/ttyMSM0` | the SoC UART is still registered, but `CONFIG_SERIAL_QCOM_GENI_CONSOLE` is unset and no `console=` names it |
>
> `gts9-acm-getty.service` is deleted and masked. Do not re-add a getty or a
> `console=ttyGS*`: the gadget port's `n_tty_write()` blocks once its 8 KiB buffer
> fills with nobody draining the host side, which is the boot stall
> [documented here](BOOT_CONSOLE_BLOCK.md), and the autologin getty was the 90 s
> poweroff ([shutdown delay](SHUTDOWN_DELAY.md)).

This note records the verified console mapping for the SM-X710 mainline boot so later
bring-up work does not confuse the physical Qualcomm UART with the USB gadget serial port.

## Interface mapping

| Linux device | Transport | Purpose |
| --- | --- | --- |
| `/dev/tty1` | framebuffer VT + EF-DX710 keyboard | local tablet login |
| `/dev/ttyGS0` | USB ConfigFS ACM gadget, first interface | **userspace root shell** (`gts9-acm-getty.service`, autologin root) |
| `/dev/ttyGS1` | USB ConfigFS ACM gadget, second interface | **kernel printk console** (`console=ttyGS1`) |
| `/dev/ttyMSM0` | Qualcomm GENI UART | physical UART; kernel console (`console=ttyMSM0,115200n8`, `earlycon`), no userspace getty |

The mapping above is the current, hardware-verified one (2026-09-24,
`reference/boot-tests/test-183-*` and `test-184-*`). Read it as three separate
things that are easy to confuse:

* `ttyMSM0` is the **SoC's physical GENI UART**. `console=ttyMSM0,115200n8` and
  `earlycon` keep it as a *kernel* console for bring-up. Nothing is attached to
  it on this tablet, so it does **not** want a userspace getty:
  `systemctl-getty-generator` used to create `serial-getty@ttyMSM0.service` from
  the `console=` argument, and while `/dev/ttyMSM0` did not exist yet the boot
  waited for `dev-ttyMSM0.device` and hit its 90 s timeout. That one instance is
  now masked (`gts9-enable-units`); the kernel console and `earlycon` are
  untouched.
* `ttyGS0` is the **USB ACM userspace channel**: the Windows COM port that gives
  a root shell. It is served by `gts9-acm-getty.service`, not by the generic
  `serial-getty@ttyGS0.service` — the generic instance waits for
  `dev-ttyGS0.device`, which is created later by `gts9-usb-acm.service`, so it
  timed out and failed; with no process holding the tty open the gadget has no
  OUT requests and host writes time out as well, which looks like a dead tablet.
  `gts9-acm-getty.service` is ordered `After=gts9-usb-acm.service` and runs
  `agetty --autologin root` directly on `ttyGS0`.
* `ttyGS1` is the **second ACM interface** and carries `printk`
  (`CONFIG_U_SERIAL_CONSOLE=y`, `console=ttyGS1` in the command line). A gadget
  serial console takes its port's IN endpoint, so a port cannot be both the
  kernel console and a login shell — that is why the two roles are split across
  two interfaces. The host sees two COM ports; both are needed, and the kernel
  console is where live kernel messages (and anything printed before a panic)
  arrive.

`gts9-kmsg-console` (the userspace mirror of `/dev/kmsg`) is a third, optional
piece: it exists for boots whose command line has no ttyGS console, is gated by
`gts9_kmsg_mirror=1`, and steps aside by itself when the kernel already owns a
ttyGS console.

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
sudo systemctl enable --now gts9-acm-getty.service
```

Verified on the tablet: Windows serial access works after this service is enabled. Because
the unit is enabled, subsequent Debian boots should start it automatically whenever
`/dev/ttyGS0` is present.

Useful checks:

```
ls -l /dev/ttyGS0 /dev/ttyGS1
systemctl is-enabled gts9-acm-getty.service
systemctl status gts9-acm-getty.service --no-pager
# the generic instance must stay disabled, and the ttyMSM0 one masked:
systemctl is-enabled serial-getty@ttyGS0.service serial-getty@ttyMSM0.service
cat /sys/kernel/config/usb_gadget/gts9/UDC
```

If the service is active but Windows sees no device, debug the ConfigFS gadget/UDC path.
If Windows sees the COM port but it is silent, first check which process, if any, owns
`/dev/ttyGS0`.

## ttyMSM0 remains separate

**It is masked on this tablet** (`serial-getty@ttyMSM0.service -> /dev/null`): the
UART has no userspace login attached and the device node appears late. Do not
remove that mask to "restore" the getty, and do not remove `console=ttyMSM0` or
`earlycon` to hide the timeout.

Historically a `serial-getty@ttyMSM0.service` could be enabled when a userspace login is wanted on
the physical Qualcomm UART, but that service does not provide the Windows USB ACM console.

Do not replace `ttyGS0` with `ttyMSM0` in USB-console documentation, tests or
scripts, and do not treat `ttyGS1` as a second shell: it is the kernel console.
