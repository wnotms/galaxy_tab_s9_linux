# Boot test 2 — SM-X710 mainline attempt with the early console (2026-09-21)

Second physical attempt, after moving the persistent console to
`early_initcall` and forcing its region from the kernel command line. The
result is still a boot loop, but this round produced the first real evidence
about **where** the failure is.

## Artifacts flashed

Written with `adb` from TWRP 3.7.1_12-gts9wifi, one partition at a time, with a
read-back hash comparison after the write. `vbmeta` was again **not** touched.

| Partition | SHA-256 written (= read back) |
|---|---|
| `boot` | `0816bfb78f8ea7ad4fff22b38822fb260a8eba8ba5cac35c34e00f83586364f2` |
| `init_boot` | `26dd7517e1dbe65155a866d6fdb50c08f71268de6d009563a6edf23a8d179522` |
| `vendor_boot` | `42566e78c1512183e8db773277699d1194940aef17ff02ce6154fe7b6af38937` |
| `dtbo` | `c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3` |

Kernel: `Image.gz`
`5e7c56f5bce85404125569a332a81b04c6bf6f63d64e156d8428048f32bfad26`, board DTB
`1c105090a0c087334435e19fb9f99047ac32865994baf372511846a0a367083c`, built from
commit `18c4c4b` with `KERNEL_CLEAN=1 BUILD_MODULES=0`. The bundle passed
`scripts/validate-boot-bundle.sh` before flashing and the vendor cmdline now
carries `gts9_sec_log=0x880200000,0x200000`.

## Evidence capture

`scripts/capture-last-kmsg.sh` was started **before** the reboot and waited for
the tablet to disappear and come back, so the ring was pulled the moment TWRP's
`/proc/last_kmsg` was readable — no time for recovery to overwrite it:

`/home/ms/Samsung/.../.work/boot-logs/last_kmsg-test2-20260921T110956Z.txt`,
2,097,136 bytes, SHA-256
`05d6e4b45cb2233321a69e73fffbe7d6994dea4f24c5bf3568d38d5e50e9958a`.

Markers, all zero:

```text
Linux version                     0
gts9wifi-sec-log: (early console) 0
GTS9 MAINLINE INITRAMFS REACHED   0
gts9-init                         0
Kernel panic                      0
```

The ring holds the stock Android kernel's log from an earlier boot (uptime
72 s) followed by the XBL/ABL log of the most recent attempt. TWRP's own
kernel does not write to the ring, so the absence of our kernel's log is not an
overwrite artefact this time.

## What the bootloader log proves

The ABL section of the same dump answers several questions that were open after
boot test 1. Four attempts are recorded, each with **our** command line:

```text
[ ABL ] Cmdline: root=LABEL=GTS9_ROOT rootwait rw console=ttyMSM0,115200n8
        loglevel=7 ignore_loglevel earlycon gts9_sec_log=0x880200000,0x200000
        firmware_class.path=/lib/firmware  msm_drm.dsi_display0=GTS9_ANA38407_AMSA10FA01: msm_drm.lcd_id=8
```

- **The boot image is accepted and entered.** ABL reads our `boot`/`vendor_boot`
  and builds the kernel command line from our bundle (it appends its own panel
  parameters).
- **Our DTB is the one selected:**
  `Best match DTB tags 519/00010008/0x00000004/20000/2014A/20049/20045/(offset)0xFA118018/(size)0x0002AD1B`
  — `0x2AD1B` is 175,387 bytes, exactly the size of
  `sm8550-samsung-gts9wifi.dtb`, and `0x00010008/0x00000004` is our
  `qcom,board-id`.
- **Our deliberately invalid dtbo is seen as intended:**
  `Dtbo hdr magic mismatch 0, with D7B7AB1E`, followed by
  `(Booting) AUTHENTICATE fail but allow Dtbo binary: dtbo` and a warranty-bit
  warning. Overlay application completes with a harmless
  `Error finding dtbo-version property at Dtb`.
- **The memory map handed over** is identical to the one a successful stock
  boot receives (`Final RAM Partitions` plus nine `Add Base:` ranges, e.g.
  `0x80000000 + 0xE00000`, `0x811D0000 + 0x56E30000`, …).
- `avb_device_locked = 0`, `unlock_count = 2`, `reboot_reason = 0x9`.

So the failure is **not** in image acceptance, DTB selection, dtbo handling or
the command line. ABL performs the same hand-off sequence it performs for the
stock kernel — and then nothing from our kernel reaches the ring.

## Why "nothing in the ring" is now meaningful

The console registers at `early_initcall`, the first initcall level, with
`CON_PRINTBUFFER`, so it captures everything from the first arm64 banner line
onward. For the ring to stay empty, the kernel must be dying **before** that
point: in the EFI stub or decompression, in early assembly, or during
`setup_arch` before the device tree is unflattened. It never reached a Linux
driver.

One structural note discovered while investigating: `arch/arm64` has no
appended-DTB support at all (no `APPENDED_DTB` symbol in `arch/arm64/Kconfig`,
`head.S` or `setup.c`). The arm64 kernel uses only the FDT pointer passed in
`x0`, so the DTB appended to `Image.gz` can only matter if ABL itself chooses
to pass that pointer.

## Device state afterwards

No restore was needed to reach recovery: the recovery partition and the
bootloader were never touched, so the tablet came straight back into TWRP. The
four test-2 images are still flashed (`boot`, `init_boot`, `vendor_boot`,
`dtbo`), and `vbmeta` is still the stock one. The verified stock backups remain
in `/home/ms/Samsung/gts9-stock-backup/` and can be written back at any point
with the commands in `docs/FIRST_BOOT_TEST.md` section 5.1.

Boot test 3 therefore only has to rewrite the partitions whose images changed
(`boot`, `vendor_boot`); `init_boot` and `dtbo` are byte-identical to what is
already there.

## Outcome and next step

Boot loop again with no kernel output, so the two explanations from boot test 1
are still open — but the space has narrowed to "the kernel image is entered and
dies extremely early" versus "the kernel is never entered at all". Boot test 3
separates exactly those two with a proof-of-life marker written from
`parse_early_param()` inside `setup_arch`, which runs before memory init, DT
unflattening, and any console. See `docs/PERSISTENT_CONSOLE.md`.
