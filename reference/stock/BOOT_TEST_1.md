# Boot test 1 — SM-X710 mainline attempt (2026-09-21)

First physical boot attempt of a kernel built by this repository. Recorded
exactly as it happened, including the parts that did not work.

Result in one line: **the tablet boot-looped, produced no kernel output in the
persistent console, and was restored from the verified stock backup.**

## Artifacts flashed

Written with `adb` from TWRP 3.7.1_12-gts9wifi, one partition at a time, with a
read-back hash comparison after the write. `vbmeta` was deliberately **not**
touched.

| Partition | Size | SHA-256 written (= read back) |
|---|---:|---|
| `boot` | 100663296 | `f50969ff85194e37033a554dc57d4a4815c07cb35db6043273f07f3a31ae0196` |
| `init_boot` | 8388608 | `26dd7517e1dbe65155a866d6fdb50c08f71268de6d009563a6edf23a8d179522` |
| `vendor_boot` | 100663296 | `fee1b61db82d80476174ac89240b6ef25fa3a562de2e6768e5edcb9b8893f538` |
| `dtbo` | 16777216 | `c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3` |

Kernel side: `Image.gz`
`ddf356a0fa29a24ca59c00ab17a1daa0c51832ee8e7a9ee40779adeca95ba410`, board DTB
`1c105090a0c087334435e19fb9f99047ac32865994baf372511846a0a367083c`, release
`7.2.0-rc3-gts9wifi-dirty`, upstream `a13c140cc289c0b7b3770bce5b3ad42ab35074aa`.
The bundle passed `scripts/validate-boot-bundle.sh` before flashing, and every
pushed image matched its bundle hash on the device.

## Observed behaviour

1. `adb reboot` from TWRP: the tablet left recovery, adb disappeared (expected:
   the bring-up initramfs has no `adbd` and no panel driver).
2. The tablet then **restarted repeatedly** — an infinite boot loop.
3. Holding the recovery combo brought TWRP back, so the bootloader and recovery
   remained intact throughout.

## Evidence collected

`/proc/last_kmsg` was dumped immediately on returning to TWRP (before doing
anything else) — 2,097,136 bytes, SHA-256
`d54dcff3f93e2d864a87cce1af746f4d931e7c6ed24ca6c6111a30e9b0bf922e`. The full
dump is kept outside the repository at
`/home/ms/Samsung/gts9-boot-test-1/last_kmsg.txt`.

What it contains: the **stock Android kernel's** log from an earlier successful
boot (`sec_bat_monitor_work`, `fts_touch`, `msm_watchdog_data`,
`panel0-backlight`, uptime up to ~485 s) followed by the XBL/ABL log of the
most recent boot (3,684 `[ XBL ]` and 3,639 `[ ABL ]` lines, ending at
`UEFI End`).

What it does **not** contain — searched explicitly, all zero hits:

```text
Linux version                     0
Booting Linux                     0
[    0.000000]                    0
7.2.0-rc3                         0
gts9-init                         0
GTS9 MAINLINE INITRAMFS REACHED   0
Kernel panic                      0
Unable to handle kernel paging    0
initramfs                         0
```

The ABL boot-loader-data block from that last reset:

```text
[BLDP] kernel_state = 0xFAF
[BLDP] avb_device_locked = 0
[BLDP] unlock_count = 2
[BLDP] build_version[] = X710ZCU5CYH4
[BLDP] bootloader_mode = 2
[BLDP] reboot_reason = 0x9
[BLDP] wp_state = 0x1
[BLDP] wb_reason = 0x303
[BLDP] image_status[] = 11 22 12 22 21 10
```

`avb_device_locked = 0` confirms AVB was not enforcing an unsigned image, which
is consistent with TWRP itself booting. The BLDP field semantics are Samsung
internal and are **not** interpreted here.

## Classification

Neither A nor B nor C strictly:

- there is no `Linux version ...` line, so the kernel never reached the point
  where it could write the persistent ring (case C-like);
- but the tablet reset instead of stopping, and the reset reason was recorded
  by ABL as `0x9`.

Two families of explanation remain, and the current instrumentation cannot tell
them apart:

1. the kernel never started (ABL rejected or failed to hand off the image);
2. the kernel started and died **before** the persistent console registered —
   the driver is a `builtin_platform_driver`, so it only registers at
   `device_initcall` time, which is far too late for an early bring-up failure.

## Recovery performed

The four flashed partitions were written back from the verified stock backup
(`/home/ms/Samsung/gts9-stock-backup/`) and the read-back hashes matched the
backup hashes exactly:

```text
boot        66b9746b31ead824ee148dec81eebe683b12e9171aee9e8f7624616057c58985  OK
init_boot   2971eb317c71d828af4d75532fa48b6f0b71ebda9ed117020e2dd7c5688dd4da  OK
vendor_boot 5931bd19033555d27c093b9a14bd74a4f4c23315eb0dc0d6cdebe1a1a4a06ab2  OK
dtbo        ebf3ec4a1418fc2510671f32026d38932360c9cb6c5f1007e9783a115239ec7b  OK
```

`vbmeta` was never written. The recovery route in `docs/FIRST_BOOT_TEST.md`
section 5 worked as written.

## Next step taken from this result

The failure is not diagnosable with a console that registers at
`device_initcall` time, so the persistent console was moved to the earliest
practical point (`early_initcall`, with a command-line override so it does not
depend on the device tree reaching Linux). See
`docs/PERSISTENT_CONSOLE.md`. Boot test 2 is what decides between the two
explanations above: if the ring is still empty after that change, the kernel is
not starting at all and the investigation moves to the boot image hand-off
rather than to kernel code.
