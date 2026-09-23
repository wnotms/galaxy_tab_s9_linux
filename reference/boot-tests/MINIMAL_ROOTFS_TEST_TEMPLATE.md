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

## Persistent record

The authoritative evidence is `/var/log/gts9-minimal-last-boot` on the Debian
root filesystem. Read it live from a running Debian, or offline from TWRP:

```sh
adb shell
blkid                                     # identify the Debian ext4 partition
mkdir -p /mnt/debian
mount -t ext4 -o ro <confirmed-partition> /mnt/debian
cat /mnt/debian/var/log/gts9-minimal-last-boot
umount /mnt/debian
```

- Record read from (live Debian / TWRP offline):
- `stage=`:
- `stage_history=`:
- `failure=`:
- `mmc_devices=`:
- `debian_stage=` / `debian_stage_history=` (if Debian was entered):
- Record absent (`yes`/`no`); if absent, list the alternative evidence used:

A record whose `stage` stops at `root-mounted` proves the mount and nothing
about switch_root; one that stops at `switch-root` proves the handoff was
prepared but not that systemd ran. Do not record a stage that was not read
back from this file or from a retained kernel/serial log.

## Rootfs and system state

- `/dev/mmcblk1p1` appeared:
- ext4 mount succeeded:
- `/` source and filesystem (`findmnt /`):
- PID 1 (`cat /proc/1/comm`):
- systemd state (`systemctl is-system-running`):
- serial/getty evidence:
- panel state (record separately; it is not a boot-state verdict):

## Test order

Run the two phases with the same flashed images and the same cmdline; Type-C is
the only intended variable.

### Phase A - Type-C attached

Boot with `gts9_minimal_rootfs=1` and Type-C connected. Even a black screen is
expected to become a Debian boot: the panel and the USB console are now Debian
services. Wait for the full boot, then, if Windows shows the COM port, log in
automatically as root and record:

```sh
id
uname -a
findmnt /
systemctl --failed
systemctl status gts9-usb-acm.service
systemctl status gts9-panel-recover.service
cat /var/log/gts9-minimal-last-boot
```

If there is still no COM port or panel output, go to TWRP, mount the Debian
root read-only and read the same record (see `docs/TWRP_DEBIAN_RECOVERY.md`).
Record only the markers that were actually read back.

### Phase B - battery-only

Only after Phase A proves `debian_stage=systemd-entered` (the rootfs chain
does not depend on Type-C): power the tablet off completely, disconnect
Type-C, power on, wait through the full boot, and - if there is no visible
output - enter TWRP and read the persistent stage record.

Result: if `systemd-entered` and `multi-user` are present, Type-C is not a
rootfs dependency and the remaining problem is USB attach or panel recovery.
If the record stops at `waiting-root`, investigate SDHCI/`sdhc_2`, `vmmc`,
`vqmmc`, card detect, RPMh, clock and pinctrl before touching any regulator.

## Logs and files

- Kernel log source and filename:
- UART / serial transcript:
- `dmesg` or journal filename:
- `last_kmsg` / pstore filename, or why unavailable:
- Commands run in Phase A over the USB console (transcript):
- TWRP mount and read of the record (transcript):
- `SHA256SUMS` for evidence files:
- `sec_log`/`last_kmsg` absence: `expected` (bootloader overwrote it) / other:

## Result

- Outcome:
- Repeated with the same artifacts:
- Notes / unresolved evidence:
