# Owner-supplied kmsg from an earlier mainline kernel (12 July 2026 build)

`last_kmsg-owner-july-kernel.txt` (211,845 bytes) was supplied by the owner from
a tablet boot with an **earlier** build of this port — different lineage from the
current tree, with extra `GTS9WIFI:` instrumentation and a different initramfs.
It is the first evidence in this repository that the mainline kernel actually
runs on the SM-X710, and it re-frames several earlier conclusions.

Kernel identity, from the log itself:

```text
Linux version 7.2.0-rc3-gts9wifi-bringup (gts9wifi@builder)
  (Ubuntu clang version 21.1.8, Ubuntu LLD 21.1.8)
  #1 SMP PREEMPT Sun, 12 Jul 2026 14:16:39 -0700
```

## What it proves

1. **The kernel is entered and boots.** The instrumentation reports, in order:

   ```text
   GTS9WIFI: flat_dt compatible=yes range=validated
   GTS9WIFI: setup_arch after_fdt / after_memblock / after_paging / after_unflatten / after_bootmem
   GTS9WIFI: console_initcall reached
   [    0.000000] Booting Linux on physical CPU 0x0000000000 [0x411fd461]
   [    0.000000] Linux version 7.2.0-rc3-gts9wifi-bringup …
   ```

2. **The device tree is accepted and its memory ranges validate** — the panic
   paths in `setup_machine_fdt()` that the earlier investigation suspected are
   not what is happening.

3. **It is a direct boot, not EFI:** `efi: UEFI not found`. Every
   appended-DTB/EFI-stub theory from tests 3–4 is therefore moot, and ABL passes
   its own DTB pointer as the boot protocol requires.

4. **Userspace runs.** A diagnostic initramfs prints its own banner and mounts
   the pseudo-filesystems:

   ```text
   [    0.062479] GTS9WIFI: mount table target=/tmp entry=tmpfs /tmp tmpfs rw,relatime 0 0
   [    0.062494] Galaxy Tab S9 mainline diagnostic initramfs (experimental)
   [    0.063711] GTS9WIFI: configfs mounted path=/sys/kernel/config
   [    0.068374] GTS9WIFI: USB gadget configured
   ```

   So `ABL -> Linux -> /init` has already been achieved on this tablet, and the
   "stuck at the Samsung logo" state observed after the PID-1/panic repair is
   consistent with a running initramfs waiting on a console that does not exist,
   not with an early kernel death.

5. **Samsung's bootloader appends `console=null`** to our command line:

   ```text
   Kernel command line: rdinit=/init console=null loglevel=8 … console=null nokaslr watchdog.stop_on_reboot=0 … nowatchdog …
   ```

   which is why the reference port carries an `ignore_console_null` patch and why
   this repository imported it.

## Why the USB gadget never appeared in test 008

The log contains the platform-probe diagnostics that explain it:

```text
probe of 88e3000.phy returned -517 after 2 usecs
probe of 1fc0000.clock-controller returned -517 after 0 usecs
[    0.095193] probe of a600000.usb returned -517 after 3 usecs
GTS9WIFI: platform_supplier consumer=a600000.usb … name=1fc0000.clock-controller driver=<none> waiting_for_supplier=1
GTS9WIFI: platform_supplier consumer=a600000.usb … name=88e3000.phy driver=<none> waiting_for_supplier=1 status=okay
GTS9WIFI: manual_dwc3_bind dev=a600000.usb rc=1 bound=<none> …
GTS9WIFI: platform_driver dwc3 bound=<none>
GTS9WIFI: platform_driver dwc3-qcom bound=<none>
```

`-517` is `-EPROBE_DEFER`: `a600000.usb` (the DWC3 controller) never probes
because the eUSB2 PHY (`88e3000.phy`) and a clock controller
(`1fc0000.clock-controller`) are themselves deferred. Until that chain resolves
there is no UDC, configfs cannot bind a gadget, and the host sees nothing — no
matter whether the initramfs reached userspace. Test 008's silence is therefore
expected and is **not** evidence about kernel entry.

## Other findings worth acting on

- `WARNING: 'bootconfig' found on the kernel command line but CONFIG_BOOT_CONFIG
  is not set.` — either enable `CONFIG_BOOT_CONFIG` or stop passing `bootconfig`.
- `WARNING: x1-x3 nonzero in violation of boot protocol` — ABL leaves junk in
  x1–x3; harmless but recorded.
- `OF: reserved mem: failed to reserve memory for node 'uh-heap@b0200000' … size
  0 MiB` and `'uh-guest@b1000000' … size 54 MiB` — **that build's** DTB had
  wrong/short sizes for these nodes. The current tree is not affected: its DTB
  carries `uh-heap 0x40000` and `uh-guest 0x3000000` (verified by decompiling
  `out/kernel-gts9wifi/sm8550-samsung-gts9wifi.dtb`). A failed reservation is
  dangerous here, because the board notes say a protected carveout that ends up
  in the allocator can make the secure firmware reset the SoC — worth keeping an
  eye on in future DTS revisions.
- UFS is present and healthy at the bootloader level (`UFS INQUIRY ID: SAMSUNG
  KLUEG4RHHD-B0G1`, 256 GB); the mainline side still has to be validated.
- The captured mainline log only covers up to ~0.12 s of uptime; the rest of the
  2 MiB ring holds bootloader text, exactly as measured in test 007.

## Consequences for the current work

- The earlier conclusion "the kernel never reaches `setup_arch`" (test 003) was
  an artefact of the unreliable ring and is retracted.
- Confirming userspace **on the current build** does not need the ring or USB:
  the initramfs can power the tablet off after a delay
  (`gts9_userspace_proof=<seconds>`), which a hung kernel cannot fake. That is
  test 009.
- The USB rescue path (M2) has a concrete blocker list now: eUSB2 PHY
  `88e3000.phy` and clock controller `1fc0000.clock-controller` must probe
  before `a600000.usb` can.
