# Minimal rootfs physical boot test

Copy this file into a new `reference/boot-tests/test-NNN-YYYYMMDDTHHMMSSZ/`
directory for every physical run. Keep Type-C connected/battery-only runs as
separate records. Do not overwrite prior evidence.

## Candidate

- Repository commit:
- Kernel source commit:
- Kernel image SHA-256:
- DTB SHA-256:
- Initramfs SHA-256:
- Boot bundle SHA-256 manifest:
- Exact cmdline (`cat /proc/cmdline` or flashed profile):
- Profile: `gts9_minimal_rootfs=1`
- Device state: `Type-C connected` / `battery-only, fully powered off`
- Power-on action and observation:
- Owner observation:

## Boot stages

Record the marker and elapsed time where available. Write `not observed` when
there is no evidence; do not infer a stage from the panel image.

| Marker | Observed | Time / evidence source |
|---|---|---|
| `GTS9_MINIMAL_STAGE=kernel-userspace` | | |
| `GTS9_MINIMAL_STAGE=waiting-root` | | |
| `/dev/mmcblk1p1` present | | |
| `GTS9_MINIMAL_STAGE=root-found` | | |
| `GTS9_MINIMAL_STAGE=mounting-root` | | |
| `GTS9_MINIMAL_STAGE=root-mounted` | | |
| `GTS9_MINIMAL_STAGE=init-found` | | |
| `GTS9_MINIMAL_STAGE=switch-root` | | |
| Debian/systemd PID 1 confirmed | | |
| Debian login confirmed | | |

Failure marker, if any:

Last observed stage:

## Rootfs and system state

- `/dev/mmcblk1p1` appeared:
- ext4 mount succeeded:
- `/` source and filesystem (`findmnt /`):
- PID 1 (`cat /proc/1/comm`):
- systemd state (`systemctl is-system-running`):
- serial/getty evidence:
- panel state (record separately; it is not a boot-state verdict):

## Logs and files

- Kernel log source and filename:
- UART / serial transcript:
- `dmesg` or journal filename:
- `last_kmsg` / pstore filename, or why unavailable:
- `SHA256SUMS` for evidence files:

## Result

- Outcome:
- Repeated with the same artifacts:
- Notes / unresolved evidence:
