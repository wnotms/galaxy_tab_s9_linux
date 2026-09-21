# Stock SM-X710 boot chain record

This file records the state of the tablet's boot chain **before** the first
mainline boot test. Fill it in from TWRP after running the backup steps in
`docs/FIRST_BOOT_TEST.md` (section 4).

Do not commit the stock partition images themselves. They are large, they are
Samsung's, and they do not belong in this repository. Only sizes, hashes,
identifiers and dates go here.

## Device and firmware

| Field | Value |
|---|---|
| model / codename | SM-X710 / `gts9wifi` |
| Android build identifier (`ro.build.display.id`) | _not recorded yet_ |
| Android fingerprint (`ro.build.fingerprint`) | _not recorded yet_ |
| `ro.product.device` | _not recorded yet_ |
| verified boot state (`ro.boot.verifiedbootstate`) | _not recorded yet_ |
| TWRP version | _not recorded yet_ |
| acquisition date (UTC) | _not recorded yet_ |
| collected by | _not recorded yet_ |

## Partition sizes and hashes

Sizes are from `blockdev --getsize64 /dev/block/by-name/<name>`; hashes are of
the backup copies, which must equal the hashes of the partitions themselves.

| Partition | Size (bytes) | SHA-256 of backup |
|---|---:|---|
| `boot` | _pending_ | _pending_ |
| `init_boot` | _pending_ | _pending_ |
| `vendor_boot` | _pending_ | _pending_ |
| `dtbo` | _pending_ | _pending_ |
| `vbmeta` | _pending_ | _pending_ |

The repository currently pads its images to the sibling SM-X910 values
(`boot` 100663296, `init_boot` 8388608, `vendor_boot` 100663296, `dtbo`
16777216, `vbmeta` 131072) until `scripts/check-device-layout.sh` confirms the
real X710 values on the device. Record the real values here when they are
known, and update the three scripts if they differ.

## Backup location

| Field | Value |
|---|---|
| on-device path | `/external_sd/gts9-stock/` |
| off-device copy | _pending: a backup that exists only on the tablet is not a backup_ |
| `SHA256SUMS` verified | _pending_ |

## Notes

- `vbmeta` is recorded for completeness but is **not** rewritten by the boot
  test. See `docs/FIRST_BOOT_TEST.md` section 5.2.
- Command line used for the backup:

```sh
mkdir -p /external_sd/gts9-stock
for p in boot init_boot vendor_boot dtbo vbmeta; do
    dd if=/dev/block/by-name/$p of=/external_sd/gts9-stock/$p.img bs=4M
done
sha256sum /external_sd/gts9-stock/*.img | tee /external_sd/gts9-stock/SHA256SUMS
```

- Read-only layout audit output (`/external_sd/gts9-layout.txt`) belongs with
  the first test record, not in this file.
