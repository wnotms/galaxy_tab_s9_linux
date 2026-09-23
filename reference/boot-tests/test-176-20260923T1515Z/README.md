# Test 176 — handoff trace candidate

**Status:** host-built and validated; not flashed.

## Change

The `gts9_boot_trace_console=1` path now keeps its `/dev/tty0` file descriptor
open while initramfs moves `/dev` into the Debian root, so the `switch-root`
marker can still reach the framebuffer. The descriptor is closed when
`switch_root` starts Debian. The default command line does not enable this
diagnostic path, and no boot timing or hardware sequence changed.

## Candidate

Artifact directory:

```text
/home/ms/Samsung/gts9-flash-tests/test-176-20260923T1515Z
```

Only `init_boot.img` differs from the test-173 bundle. Its SHA-256 is:

```text
05f762ee09136445c3a2a7a2bfa0670e62f2be1aeb6f62e4c4487205d4ff138a
```

`boot.img`, `vendor_boot.img`, `dtbo.img`, and `vbmeta.img` are byte-identical
to test-173. The regular test-173 `init_boot.img` SHA-256 was
`b555751605630f6a83da3d7edd7cc25413a87d98a3d7afaf83618258d390567f`.

The candidate uses test-173's exact boot/kernel image because the current local
kernel build has a different `Image.gz` hash. The bundle validator therefore
ran with `--no-kernel-compare`; it passed image sizes, Android v4 layout, board
DTB selectors, vendor cmdline and bootconfig, initramfs contents, AVB footers,
and the SHA-256 manifest. A separate byte comparison confirms all four
non-`init_boot` partitions match test-173 exactly.

## Host checks

- `python3 -m unittest discover -s tests`: 49 tests passed. The Pogo test
  fixture reports two existing unused-function compiler warnings.
- `sh -n boot/bringup-init.sh`: passed.
- `scripts/build-bringup-initramfs.sh`: passed; image size 1,210,314 bytes,
  below the 7,340,032-byte budget.
- `scripts/validate-boot-bundle.sh`: passed with the test-173 kernel image
  preserved as described above.

No device partition was written. This is a new `init_boot.img` hash and has not
been approved or tested on hardware.
