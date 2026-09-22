# Test 044 — early synchronous framebuffer recovery reduces dark interval

Source de7bd2b. Boot and init_boot flashed with verified readback; vendor_boot,
dtbo, vbmeta unchanged. Kernel panel commands restored to test040 baseline.
Validated bundle, off-device backups, source/artifact hashes and raw logs saved.
Recovery plan: restore pretest boot/init_boot through TWRP.

First ID fails at 5.297 s; /init requests the cycle at 5.912 s, receives
80 00 04 at 6.267 s, and logs recovery complete at 6.417 s. Compare test040:
zero ID 5.666 s, recovery start 7.261 s, valid ID 8.263 s, completion 9.098 s.
The zero-ID-to-valid-ID interval fell from 2.597 s to 0.969 s. Kernel boot
variation contributes to the absolute timestamp difference. This is an
accelerated workaround, not a fix for the first DSI transaction failure.
Visual confirmation requested from owner; pending when this record was made.

USB console/report retrieval stayed functional; report SHA256 verified.
Final state TWRP via BCB. Raw last_kmsg and pstore availability are recorded,
not mistaken for mainline evidence. No recovery/vbmeta writes.
