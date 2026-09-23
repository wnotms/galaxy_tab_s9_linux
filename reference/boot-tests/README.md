# Physical boot-test evidence

Each test gets `test-NNN-YYYYMMDDTHHMMSSZ/`. Commit and push its raw logs,
artifact manifests, flash/read-back transcript and result README on `test`
before the next experiment. Include unsuccessful and aborted tests; explicitly
record unavailable logs and the device's final state. Do not commit images or
partition backups. Recovery dmesg describes recovery, not the mainline attempt.

Set `CAPTURE_DIR` to the test directory when running
`scripts/capture-last-kmsg.sh` before a reboot. Its fallback directory `captures/`
is also tracked; associate any such capture with its test rather than leaving
unexplained files. `SHA256SUMS` hashes evidence files (excluding itself).

Historical tests 1–3 are described under `reference/stock/BOOT_TEST_*.md`;
test 4's original log remains in `.work/boot-logs`. New tests start at 005.

For the minimal Debian rootfs profile, record Type-C-connected and battery-only
cold boots in separate directories using `MINIMAL_ROOTFS_TEST_TEMPLATE.md`.
Keep the kernel, DTB, initramfs, cmdline and bundle hashes identical across the
pair; record whether `/dev/mmcblk1p1`, `switch-root` and Debian/systemd were
observed. A panel image is not a system-state result.
