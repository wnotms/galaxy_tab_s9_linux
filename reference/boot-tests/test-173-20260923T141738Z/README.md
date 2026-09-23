# Test 173 — corrected early-boot trace candidate

**Status:** built and host-validated; not flashed. This candidate fixes the
test-172 initramfs trace-option parsing order so
`gts9_boot_trace_console=1` is read only after `/proc` is mounted. No kernel,
DTB, hardware sequence, rootfs path, or poweroff handler was changed.

Source revision: `79e30d8288a769e075f95d3535bb749e7d3951ae`, plus the local
`boot/bringup-init.sh` and `tests/test_rootfs_boot.py` diagnostic-order fix.
Kernel release: `7.2.0-rc3-gts9wifi-dirty`.

## Image scope

- `boot.img` is byte-identical to the installed test-172 candidate:
  `822ca9dcf404de83e79f085a5509ec761bf0234359a5fae166c5d1c849e1df86`.
- `vendor_boot.img` is byte-identical to test-172:
  `09bd4bea84d5a0477652002f6e4cd66091b4536f1cd7eb3d5d1a5bf45b2eb61b`.
- Only `init_boot.img` needs to change for this test. Candidate SHA-256:
  `b555751605630f6a83da3d7edd7cc25413a87d98a3d7afaf83618258d390567f`.
- The new initramfs SHA-256 is
  `cf14fd5edc2a96661d2fd285516e1ac03e8610184751e20887c5ef19dd48c932`.

The full bundle passed `scripts/validate-boot-bundle.sh` using the exact
test-172 cmdline and built kernel. Build artifacts and validation output are
kept outside Git at:
`/home/ms/Samsung/gts9-flash-tests/test-173-20260923T141738Z`.

No partition was written. If later flashed, limit the write to `init_boot`,
read it back, and compare its full hash. Do not flash `dtbo`, `vbmeta`, or any
other partition for this diagnostic test.

## Test intent

After a future authorized install, the next no-Type-C start should print the
opt-in `GTS9_BOOT_STAGE`/`GTS9_BOOT_FAIL` milestones on the panel console.
Use the visible stage to distinguish initramfs, microSD enumeration, root
mount, switch_root, and userspace progress. The source of the earlier cursor
stall and the device's shutdown behavior remain unresolved.
