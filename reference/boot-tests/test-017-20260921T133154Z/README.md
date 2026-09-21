# Test 017 — UFS, and a report that survives the power-off (2026-09-21T13:31:54Z)

Two questions, one boot:

1. `CONFIG_SM_TCSRCC_8550=y` is now in the kernel. The owner's July log showed
   `1fc0000.clock-controller waiting_for_supplier=1` with UFS and USB both
   stuck on `-517`, so if TCSRCC was the missing supplier, UFS should enumerate
   and expose a SCSI disk (`/dev/sda*`). This is the same question test 016 was
   flashed to answer.
2. The report `/init` collects can now be persisted on internal storage in
   `cache`, identified by its GPT label and cross-checked against the kernel's
   own geometry (`boot/bringup-init.sh`, commit `3e045a5`). Test 016 could only
   have written it to removable storage, which this board does not have.

Artifacts, all built by `scripts/build-boot-bundle.sh` and validator-clean
(`bundle-validation.log`):

| image | sha256 | flashed this test |
| --- | --- | --- |
| `boot.img` | `457f276e89631d5efcfa99267ad72f9706c8cf348ed907110427db9005a234da` | no, unchanged from test 015/016 |
| `init_boot.img` | `12ac5bfffecc899b096958761c0e61ed3d35f6f1c1eded68a9da5250db9f148b` | **yes**, read back OK |
| `vendor_boot.img` | `c103c5ad79aa4e2f28df868ddf95265f1464ca5deac1f105c6cb50a49dadc35c` | no, already on the device from test 016 |

`dtbo` and `vbmeta` untouched. Kernel release `7.2.0-rc3-gts9wifi-dirty`,
kernel source commit `cde46e5`, upstream `a13c140c`.

## What this test can prove, and how

`init_boot` carries `gts9_proof_code=20` (from the cmdline in `vendor_boot`),
so the power-off delay encodes the storage/USB state:

`delay = 20 + 10*code`, `code = 1*microSD (/dev/mmcblk*) + 2*UFS (/dev/sd*) +
4*USB device controller (/sys/class/udc)`

| measured power-off delay | meaning |
| --- | --- |
| ~20 s | nothing enumerated: no block device at all, no UDC |
| ~30 s | microSD only |
| **~40 s** | **UFS enumerated — the TCSRCC fix worked** |
| ~50 s | microSD + UFS |
| ~60 s | UDC only, still no storage |
| ~70 s | microSD + UDC |
| **~80 s** | **UFS + UDC** |
| ~90 s | all three |

Only whole 10 s steps are meaningful; a ±3 s reading error is expected.

## Reading the report back

If `cache` mounted read-write, the report is a file; if not, it is a raw
`GTS9RPT1` block at offset 0. Both are read the same way, from TWRP:

```sh
ADB=/mnt/d/android/platform-tools/adb.exe \
    ./scripts/read-bringup-report.sh --out reference/boot-tests/test-017-.../bringup-report.txt
```

The script verifies the body against the SHA-256 `/init` recorded on the
tablet and writes nothing when it does not match.

## Cache partition, before the boot

```
b217662c51b33a9e88f994c05c11ee5c9de0f0ac0c0b3df8e34dc9878c5030f8  first 4096 bytes
 00 96 00 00 00 58 02 00 00 00 00 00 d1 42 02 00   <- ext4 superblock at 0x400
```

So a change to that hash afterwards is this boot's report and nothing else.

## Result

Pending: the owner has to start the boot and time the automatic power-off.
