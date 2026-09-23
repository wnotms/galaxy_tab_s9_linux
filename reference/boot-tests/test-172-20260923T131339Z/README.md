# Test 172 — flash poweroff-trace candidate

**Status:** prepared; no device partition has been changed yet.

This test is authorized by the owner's current request to flash the local diagnostic candidate and test it. It is limited to `boot`, `init_boot`, and `vendor_boot`. Do not flash `vbmeta`, `dtbo`, recovery, userdata, or any other partition.

The candidate contains opt-in early-boot console tracing and kernel poweroff tracing. It is intended to establish which boot stage is reached after the previously stuck Type-C/battery-only attempt and whether the poweroff path reaches its trace points. The unresolved cold-boot and shutdown symptoms are diagnostic targets only; this test does not presume a cause.

Candidate source commit: `7d04768985c8ba8fc5b5ed847a3d31679fc34447`.
Repository revision before test: `d5e7d51a7d6d2b54179ff947bec9b86aac1e15b0`.

`bundle-validation.txt` records a successful read-only validation (`BOOT BUNDLE VALIDATION PASSED`). `bundle-SHA256SUMS` and `BUNDLE_INFO` record bundle metadata. No image or partition backup is stored in git. Host staging copy: `/home/ms/Samsung/gts9-flash-tests/test-172-20260923T131339Z`.

## Required before writing

- Enter TWRP from Debian over COM17 and save the serial transcript.
- Confirm TWRP identity is SM-X710 and inspect boot-chain partition sizes; save `getprop`, layout output, and recovery dmesg.
- Make fresh host-side backups of the current `boot`, `init_boot`, and `vendor_boot` partitions; hash and compare them before any write.
- Push only the three candidate images. Write each partition separately and read it back; compare the full partition hash to the candidate image hash.
- Start `last_kmsg` capture before rebooting into the candidate. Observe the boot for at least 60 seconds; record the physical screen/boot result and post-boot serial state.

Current state: no TWRP identity/layout, backup, flash, boot result, or shutdown trace has been captured. These fields will be updated with the actual transcript; absent evidence will be marked explicitly.
