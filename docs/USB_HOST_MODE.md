# Can the X710 drive a 2.4 GHz mouse/keyboard through a dock?

**No — not with the current mainline port.** The USB controller is locked to the
peripheral (device) role because the chip that would switch it to host mode has no
mainline driver. This is a hard blocker, not a configuration oversight, and it is
the same blocker that makes the tablet a USB *device* for the debug channel.

Short answer for the practical question: **a 2.4 GHz dongle will not work.** Use
Bluetooth instead — which is exactly what the Bluetooth round just brought up, and
a Bluetooth mouse or keyboard is supported today (`CONFIG_BT_HIDP=y`).

## Why

The X710 exposes exactly **one** external data port: the USB Type-C connector. The
SM8550 SoC in this tablet has exactly **one** USB controller:

```
$ grep -nE "usb_[0-9]: usb@" arch/arm64/boot/dts/qcom/sm8550.dtsi
4521:		usb_1: usb@a600000 {
```

There is no second controller (`usb_2` does not exist on SM8550), so there is no
alternative path for a dock's USB-A ports to attach to. A dock's USB ports are a
*hub* — they need a host controller behind them, and the only one is occupied.

That controller is DWC3, which is dual-role capable, and the kernel is built for it:

| symbol | value |
|---|---|
| `CONFIG_USB_DWC3` | `y` |
| `CONFIG_USB_DWC3_QCOM` | `y` |
| `CONFIG_USB_DWC3_DUAL_ROLE` | `y` |
| `CONFIG_TYPEC` / `CONFIG_TYPEC_UCSI` | `y` |
| `CONFIG_USB_ROLE_SWITCH` | `y` |
| `CONFIG_USB_HID` / `CONFIG_USB_HIDDEV` | `y` |
| `CONFIG_USB_XHCI_HCD` | `y` |

So the *software* is ready. What is missing is the thing that decides which role
the port takes. The board DTS says so explicitly
(`kernel/dts/sm8550-samsung-gts9wifi.dts`, `&usb_1`):

> Force the peripheral role. The Type-C port is managed by an **SM5714 PD
> controller that has no mainline driver**, so there is no role switch and no
> extcon to move dwc3 out of its OTG default: the core probes, exposes a UDC, and
> never enables the port.

and the setting itself:

```dts
&usb_1 {
	dr_mode = "peripheral";
	status = "okay";
};
```

## Measured on the tablet, not inferred

```
1. live DT dr_mode:        peripheral
2. role switch present:    0 entries      (/sys/class/usb_role/ is empty)
3. typec port manager:     0 entries      (/sys/class/typec/ is empty)
4. real host controllers:  1 platform usb (a600000.usb) — and it is a UDC
5. xhci loaded:            0 modules
```

The one entry that *looks* like a USB bus is not hardware:

```
$ readlink -f /sys/bus/usb/devices/usb1
/sys/devices/platform/dummy_hcd.0/usb1
$ cat /sys/bus/usb/devices/usb1/product
Dummy host controller
```

`dummy_hcd` is a software stub used for gadget development. It has no physical
port, so nothing plugged into the tablet can appear on it.

Finally, there is no mainline SM5714 driver at all:

```
$ find drivers -iname "*sm5714*"
(nothing)
```

Mainline has `extcon-sm5502.c`, a different SiliconMitus part, which is not this
one. The DTS node exists and the I2C device is instantiated, but **no driver binds
to it** — checked directly, because the device appearing on the bus can look like
a working driver:

```
$ cat /sys/bus/i2c/devices/3-0033/of_node/compatible
siliconmitus,sm5714-usbpd
$ readlink /sys/bus/i2c/devices/3-0033/driver
(empty)
$ [ -e /sys/bus/i2c/devices/3-0033/driver ] && echo YES || echo NO
NO-DANGLING
```

The same node also appears in the boot log only as a device-tree dependency
*cycle* involving the redriver and `usb@a600000`, which is another sign that the
role-switch topology is declared but not driven.

## The whole answer in six lines

```
live DT dr_mode          peripheral
/sys/class/usb_role/     0 entries        <- no role switch
/sys/class/typec/        0 entries        <- no port manager
usb1                     dummy_hcd        <- software stub, no physical port
SM5714 usbpd driver      NO-DANGLING      <- node exists, nothing binds
sm8550.dtsi usb@ nodes   1                <- and no second controller to use
```

Raw output: `reference/boot-tests/test-223-usb-host-mode/evidence.txt`.

## Could this be made to work?

Yes, but as a separate project, and it is not a small one. In rough order of effort:

1. **Write an SM5714 Type-C/PD driver** (or extend an existing TCPM driver) so the
   port reports its role and the kernel can flip `dr_mode`. This is the real fix
   and it is a substantial driver: TCPM integration, PD message handling, and the
   `otg-det` GPIO. Other Samsung devices using SiliconMitus parts have downstream
   drivers that would be the reference, but they are written against vendor
   frameworks (extcon + a custom charger class), not upstream TCPM.
2. **Force the role from the DTS** — change `dr_mode = "peripheral"` to `"host"` or
   `"otg"` and see whether the port comes up as a host. This is a one-line change
   and would be the obvious first experiment, but it trades away the USB gadget
   (NCM/ACM/adb), which is the tablet's **only** debug and login channel while
   there is no serial console. Losing it means losing remote access to the tablet.
   It would also likely fail without VBUS/CC handling, since nothing would be
   managing the port's power role.
3. **A dock that does not need host mode** — none exists for this purpose. A dock's
   USB-A ports are downstream of a hub, which requires a host upstream.

Because (2) risks the only way to reach the tablet, it must not be attempted
without a recovery path that does not depend on that port (TWRP over the same
port would also be gone; the recovery route would be pulling the microSD or the
POGO/console path if one can be re-established first).

## What to use instead

**Bluetooth HID.** It is already working:

| what | state |
|---|---|
| controller, firmware, address | verified on the tablet |
| scan | verified |
| pair | verified — a real bond with a stored link key |
| survives reboot | verified |
| **HID profile** | `CONFIG_BT_HIDP=y` is set |

see `docs/BLUETOOTH_QCA6490_BRINGUP.md`. A Bluetooth mouse or keyboard is the one
functional test still outstanding there, and it is the recommended peer.

The POGO keyboard is a separate, non-Bluetooth path (`samsung,x710-pogo-keyboard`
over an STM32 at QUP2 SE7) and is unrelated to this question.
