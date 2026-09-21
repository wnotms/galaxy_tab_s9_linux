# Test 016 — does the TCSRCC fix bring up UFS? (2026-09-21T13:24:27Z)

Hypothesis (two questions, one boot):

1. The kernel now has `CONFIG_SM_TCSRCC_8550=y`, the clock controller that owns
   `TCSR_USB3_CLKREF_EN` / `TCSRR_UFS_CLKREF_EN`. The owner's July log showed
   `1fc0000.clock-controller waiting_for_supplier=1` and UFS/USB both stuck on
   `-517`; if TCSRCC was the missing supplier, UFS should now enumerate and
   expose a SCSI disk (`/dev/sda*`).
2. With a block device present, `/init` can finally leave a durable artifact:
   the full bring-up report (`/tmp/bringup-report.txt`) written to internal
   storage instead of vanishing with the power-off.

Artifacts (all built by `scripts/build-boot-bundle.sh`, validator passed —
see `bundle-validation.log`):

| image | sha256 | flashed this test |
| --- | --- | --- |
| `boot.img` | `457f276e89631d5efcfa99267ad72f9706c8cf348ed907110427db9005a234da` | no (unchanged from test 015) |
| `init_boot.img` | `a1ce238d0c3146d97c773699fe6fa0af1f7d02df68754d2ed0dc2361ebf55a4a` | **yes**, read back OK |
| `vendor_boot.img` | `c103c5ad79aa4e2f28df868ddf95265f1464ca5deac1f105c6cb50a49dadc35c` | **yes**, read back OK |

`dtbo` and `vbmeta` were not touched. Kernel release `7.2.0-rc3-gts9wifi-dirty`.

The change against test 015 is the cmdline: `gts9_proof_code=20` replaces the
plain proof, so the power-off delay itself carries the storage/USB state.

## Telemetry the owner has to read

`delay = 20 + 10*code`, with `code = 1*microSD (/dev/mmcblk*) + 2*UFS disk
(/dev/sd*) + 4*USB device controller (/sys/class/udc)`:

| measured power-off delay | meaning |
| --- | --- |
| ~20 s | no block device at all, no UDC |
| ~30 s | microSD block device only |
| **~40 s** | **UFS enumerated (SCSI disk present)** — the fix worked |
| ~50 s | microSD + UFS |
| ~60 s | UDC only, still no storage |
| ~70 s | microSD + UDC |
| **~80 s** | **UFS + UDC** |
| ~90 s | all three |

Only whole 10 s steps are meaningful; a ±3 s reading error is expected.

## Flash transcript

`flash.log` — push, on-device `sha256sum`, `dd` to `/dev/block/by-name/<part>`,
`sync`, read-back `sha256sum`. Both images matched their builder hashes on the
device after writing.

## Result

Pending: the owner has to start the boot and time the automatic power-off.
