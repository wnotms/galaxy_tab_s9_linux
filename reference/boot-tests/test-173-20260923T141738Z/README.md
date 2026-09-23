# Test 173 — corrected early-boot trace candidate

**Status:** built, host-validated, and flashed to `init_boot` only. Device
read-back SHA-256 matched, and a Type-C-attached reboot reached Debian. The
corrected boot-stage trace appeared in the captured kernel log and persisted
stage file. This candidate fixes the test-172 initramfs trace-option parsing order so
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

`flash-write-readback.txt` records the single-partition write. The previous
`init_boot` hash matched test-172 before the write; the new full-partition hash
matches test-173. No `boot`, `vendor_boot`, `dtbo`, `vbmeta`, or other
partition was written.

## Test intent

The next no-Type-C start should print the
opt-in `GTS9_BOOT_STAGE`/`GTS9_BOOT_FAIL` milestones on the panel console.
Use the visible stage to distinguish initramfs, microSD enumeration, root
mount, switch_root, and userspace progress. The source of the earlier cursor
stall and the device's shutdown behavior remain unresolved.

## Type-C-attached boot observation

After `reboot system` from TWRP, Debian booted with kernel
`7.2.0-rc3-gts9wifi-dirty`; `/` was `/dev/mmcblk1p1` ext4. The persisted
history reached `switch-root`, `systemd-basic`, and `tty1-getty-active`. The
kernel log included `kernel-userspace`, `framebuffer-control-available`,
`waiting-mmc`, `mmc-found`, `mounting-root`, `root-mounted`, and `init-found`.
The SDHCI host and card appeared at about 0.45 s and 0.63 s respectively;
root mount and init discovery followed at about 2.38 s and 2.42 s. UDC state
was `configured` during the read-only audit.

The initramfs portion of the persistent report still has `uptime_seconds`,
`boot_id`, and sysfs-derived MMC host/device fields as `unknown`/`none`, even
though its MMC log and later systemd stage records are populated. Those fields
need a separate diagnostic-quality review; they do not change the observed
stage history. The audit omitted the persisted cmdline.
