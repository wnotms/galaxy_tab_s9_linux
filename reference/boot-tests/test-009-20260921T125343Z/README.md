# Test 009 — userspace proof, aborted before it could fire (2026-09-21T12:53:43Z)

Same artifacts as test 010 (`init_boot eb11162f…`, `vendor_boot 7c1520aa…`): the
initramfs carries the `gts9_userspace_proof=60` mechanism, which powers the
tablet off 60 s after `/init` runs.

## Why it is recorded as aborted

Boot requested 2026-09-21T12:54:07Z; the ring capture completed at 12:54:46Z,
**39 seconds later**, because recovery was re-entered before the proof delay
expired. The device was therefore reset out of the mainline kernel before the
60 s timer could fire, and the test says nothing about userspace.

The instruction that caused it was mine, not the owner's: it told the owner to
press the recovery combination after ~60 s instead of waiting for the tablet to
act by itself. Corrected for test 010.

## Evidence in this directory

| File | Content |
|---|---|
| `source.txt` | commits and the hypothesis |
| `bundle-sha256.txt`, `BUNDLE_INFO`, `bundle-validation.log` | artifacts, `BOOT BUNDLE VALIDATION PASSED` |
| `pretest-device.txt` | the five partitions before the run |
| `pretest-last_kmsg.txt` | ring before the run |
| `flash.log` | init_boot + vendor_boot push, write and read-back hashes |
| `last_kmsg-test009-…txt`, `capture.log` | ring after the aborted attempt: bootloader text only, `Linux version` once (recovery's own 5.15.94), no mainline string. Expected — test 007 proved the ring cannot retain mainline output. |
| `observation.txt` | reboot request and timeline |

No conclusion is drawn from the ring in this test.
