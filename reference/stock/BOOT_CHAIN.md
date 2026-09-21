# Stock SM-X710 boot chain record

Real device evidence for the tablet's boot chain **before** the first mainline
boot test, collected as described in `docs/FIRST_BOOT_TEST.md` (sections 3-4).

The stock partition images are **not** in this repository. Only sizes, hashes,
identifiers and dates are recorded here.

## Device and firmware

| Field | Value |
|---|---|
| model / codename | SM-X710 / `gts9wifi` |
| stock firmware bootloader version (`ro.boot.bootloader`) | `X710ZCU5CYH4` |
| environment used for the audit | TWRP `3.7.1_12-gts9wifi` (recovery, not Android) |
| TWRP build identifier (`ro.build.display.id`) | `twrp_gts9wifi-eng 16.1.0 SP2A.220405.004 eng.ms.20260917.094451 test-keys` |
| TWRP fingerprint (`ro.build.fingerprint`) | `samsung/twrp_gts9wifi/gts9wifi:16.1.0/SP2A.220405.004/eng.ms.20260917.094451:eng/test-keys` |
| verified boot state (`ro.boot.verifiedbootstate`) | `orange` (bootloader unlocked) |
| verity mode (`ro.boot.veritymode`) | `enforcing` |
| acquisition date | 2026-09-21 18:42 (+08:00) |
| Android `/system/build.prop` | not readable from TWRP, so the stock Android build id was not captured; the bootloader version above is the firmware identifier used for this record |

## Partition sizes and hashes

Sizes are from `blockdev --getsize64 /dev/block/by-name/<name>`. Hashes are of
the pulled backups, each cross-checked against a `sha256sum` of the partition
run **on the device**: every pair matched, so the copies are faithful.

| Partition | Device node | Size (bytes) | SHA-256 of backup |
|---|---|---:|---|
| `boot` | `/dev/block/sda21` | 100663296 | `66b9746b31ead824ee148dec81eebe683b12e9171aee9e8f7624616057c58985` |
| `init_boot` | `/dev/block/sda22` | 8388608 | `2971eb317c71d828af4d75532fa48b6f0b71ebda9ed117020e2dd7c5688dd4da` |
| `vendor_boot` | `/dev/block/sda24` | 100663296 | `5931bd19033555d27c093b9a14bd74a4f4c23315eb0dc0d6cdebe1a1a4a06ab2` |
| `dtbo` | `/dev/block/sda30` | 16777216 | `ebf3ec4a1418fc2510671f32026d38932360c9cb6c5f1007e9783a115239ec7b` |
| `vbmeta` | `/dev/block/sde15` | 131072 | `9844859b45716a2a098c96cd38b15bb378e784dab34843d1edcd2704236d36e4` |

All five sizes are **identical** to the values `scripts/build-boot-bundle.sh`
pads its images to, so no script change was needed. Note that `vbmeta` lives on
a different LUN (`sde15`) from the rest (`sda*`), which matches the sibling
SM-X910 observation that only the bootloader can write it.

## Backup location

| Field | Value |
|---|---|
| off-device copy | `/home/ms/Samsung/gts9-stock-backup/` (outside this repository) |
| manifest | `SHA256SUMS` in that directory, verified against the files |
| on-device copy | none: TWRP's `/` is a RAM disk and no microSD was mounted |
| second copy | owner's responsibility: a backup with one copy is not a backup |

## Layout audit (read-only, on device)

`scripts/check-device-layout.sh` was copied to the tablet and run from TWRP via
`adb`; it exited 0 with no `MISMATCH` and no `MISSING`:

```text
=== SM-X710 boot-chain partition layout (read-only) ===
ro.product.device: gts9wifi
ro.build.display.id: twrp_gts9wifi-eng 16.1.0 SP2A.220405.004 eng.ms.20260917.094451 test-keys
ro.build.fingerprint: samsung/twrp_gts9wifi/gts9wifi:16.1.0/SP2A.220405.004/eng.ms.20260917.094451:eng/test-keys

===== boot =====
  path    : /dev/block/sda21
  size    : 100663296 bytes
  expected: 100663296 bytes (repository bundle padding)
  status  : MATCH

===== init_boot =====
  path    : /dev/block/sda22
  size    : 8388608 bytes
  expected: 8388608 bytes (repository bundle padding)
  status  : MATCH

===== vendor_boot =====
  path    : /dev/block/sda24
  size    : 100663296 bytes
  expected: 100663296 bytes (repository bundle padding)
  status  : MATCH

===== dtbo =====
  path    : /dev/block/sda30
  size    : 16777216 bytes
  expected: 16777216 bytes (repository bundle padding)
  status  : MATCH

===== vbmeta =====
  path    : /dev/block/sde15
  size    : 131072 bytes
  expected: 131072 bytes (repository bundle padding)
  status  : MATCH

=== summary ===
partitions checked : 5
size mismatches    : 0
missing/unreadable : 0
```

This confirms the sibling-derived partition sizes on the real X710. It is a
prerequisite for flashing, not permission: the flash itself is a manual step
and `vbmeta` is not part of it.

## Notes

- `vbmeta` is recorded for completeness but is **not** rewritten by the boot
  test. See `docs/FIRST_BOOT_TEST.md` section 5.2.
- Read commands used (read-only, for reproduction):

```sh
adb shell 'for p in boot init_boot vendor_boot dtbo vbmeta; do
    echo "===== $p ====="
    readlink -f /dev/block/by-name/$p
    blockdev --getsize64 /dev/block/by-name/$p
done'
```

- Backup commands used: per partition, `sha256sum` on the device plus
  `adb exec-out 'dd if=/dev/block/by-name/<p> bs=1M'` into
  `/home/ms/Samsung/gts9-stock-backup/<p>.img`, then compared.
