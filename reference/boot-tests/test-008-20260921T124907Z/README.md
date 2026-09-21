# Test 008 — live channel attempt: USB gadget in the initramfs (2026-09-21T12:49:07Z)

Source commit `43d7878` (`source.txt`). Single change against test 007: the
bring-up initramfs builds a USB CDC-ACM gadget through configfs, streams
`/dev/kmsg` onto `/dev/ttyGS0` and hands a shell to the same port. Hypothesis:
if the mainline kernel reaches userspace, the host sees the port; the ring
cannot answer that question (test 007).

## What was flashed

Only `init_boot` (`flash.log`): `ab89f78b…` → `fc65e8da2703fb28068225047f17e1c46d4116ea8986adebb1d09a08248b42c7`
(`initramfs-bringup.img 1e894d1c…`). `boot`, `vendor_boot`, `dtbo`, `vbmeta`
unchanged; `BOOT BUNDLE VALIDATION PASSED`.

The first flash in this test used VID/PID `18d1:d001`, which is what recovery's
own adb enumerates as — the Windows-side monitor matched it *before* the reboot
and produced a false positive. The gadget was corrected to `0525:a4a7`
(Linux-USB gadget serial) and re-flashed; the monitor now waits for the recovery
interface to disappear first. The superseded hash is in `flash.log`.

## Observation

Boot requested at 2026-09-21T12:50:31Z (`observation.txt`). Both independent
channels were armed before it:

| Channel | Result |
|---|---|
| Windows USB monitor (`usb-monitor.log`) | recovery USB disappeared, then **no `VID_0525&PID_A4A7` device appeared** within the observation window |
| Ring capture (`last_kmsg-test008-…txt`) | unchanged from test 007: bootloader text only, one recovery-kernel banner, no mainline string |

## Interpretation

Two explanations survive, and this test cannot separate them:

1. the kernel never reaches the initramfs script, so no gadget is created;
2. the kernel does reach userspace, but mainline `dwc3`/QMP-PHY for this board
   is not functional yet, so configfs finds no UDC and `/init` logs the warning
   and continues on the (invisible) console.

The script fails soft by design, so case 2 would look exactly like case 1 from
the host side. The warning it would print goes to `/dev/kmsg`, i.e. into the
channel that test 007 proved unreliable.

## Next step

Use a signal that depends on nothing at all: if the initramfs script runs, it
can **power the tablet off by itself** after a configurable delay
(`gts9_userspace_proof=<seconds>` on the command line, PSCI `SYSTEM_OFF`). A
hung or panicking kernel cannot do that, and with `panic=0` it cannot fake it
either. "Tablet turned itself off ~60 s after the logo" is then unambiguous
proof that `ABL -> Linux -> BusyBox /init` completed — which is precisely the
acceptance chain for this phase.
