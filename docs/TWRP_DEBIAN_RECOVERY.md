# TWRP offline Debian maintenance

TWRP is the official offline environment for this device. The minimal profile
can boot with a black panel and no USB console, and Samsung's bootloader
overwrites `sec_log`, so the running system is not always able to report what
happened. TWRP can always mount the Debian microSD root, read the persisted
boot record, repair userspace and deploy a new overlay.

Two rules frame everything below:

- **Absence of `sec_log`/`last_kmsg` evidence is not evidence that Linux did
  not boot.** The bootloader overwrites that ring. Do not conclude anything
  from it; read the record on the card instead.
- **Never format, never run a repairing `fsck`, never touch UFS.** TWRP block
  numbering is not guaranteed to match the running system.

## 1. Identify the Debian partition

Do not assume `/dev/mmcblk1p1`. Enumerate first:

```sh
adb shell
id
cat /proc/partitions
ls -l /dev/block/mmcblk*
ls -l /dev/mmcblk* 2>/dev/null
blkid 2>/dev/null
```

Identify the Debian ext4 root by filesystem type, label, UUID and partition
size. UFS devices (`/dev/sd*`) are internal storage and must never be mounted
or written as part of this workflow.

`scripts/twrp-mount-debian.sh` does that enumeration and the identification
for you. Push it once:

```sh
adb push scripts/twrp-mount-debian.sh /tmp/
adb shell sh /tmp/twrp-mount-debian.sh --list
```

`--list` prints every MMC partition with its filesystem type, label, UUID and
size. Nothing is mounted.

## 2. Mount read-only to inspect

```sh
adb shell sh /tmp/twrp-mount-debian.sh          # read-only, ro,noload
adb shell cat /mnt/debian/var/log/gts9-minimal-last-boot
adb shell sh /tmp/twrp-mount-debian.sh --umount
```

The script:

- only considers MMC partitions and refuses `/dev/sd*`,
- confirms ext4 through `blkid` (with an ext4 superblock-magic fallback),
- only accepts a candidate that actually contains Debian
  (`/etc/debian_version` or `ID=debian`), trying labelled and larger
  partitions first,
- mounts `-o ro,noload` by default, so inspecting cannot replay a journal or
  modify the filesystem,
- never formats, never creates a filesystem, and never runs `fsck`,
- refuses to mount over `/` or over an already-mounted mountpoint,
- prints the boot record if it is there.

Options for the less common cases:

| Option | Effect |
|---|---|
| `--device DEV` | Use one specific MMC partition (still checks ext4 and Debian) |
| `--uuid UUID` / `--label LABEL` | Select by filesystem UUID or label |
| `--rw` | Mount read-write; only for deliberate maintenance |
| `--force` | Skip the Debian-marker check, never the MMC/ext4 checks |
| `--umount` | Unmount `/mnt/debian` |

## 3. Read the last minimal boot

```sh
cat /mnt/debian/var/log/gts9-minimal-last-boot
```

The record has an initramfs block and a Debian block; see
`docs/MINIMAL_ROOTFS_BOOT.md` for the field list. Classification of the last
boot:

| Last evidence | What it proves | What to investigate |
|---|---|---|
| `stage=root-mounted`, `init-found`, `switch-root` and `debian_stage=multi-user` | minimal initramfs → TF → Debian succeeded; the black screen/no COM are a panel or USB userspace problem | `gts9-panel-recover`, `gts9-usb-acm`, the getty on ttyGS0 |
| `stage=switch-root`, no `debian_stage` | the handoff was prepared; systemd never reported in | `gts9-minimal-pid1`, `/sbin/init`, the `/dev /proc /sys /run` move, early systemd |
| `stage=root-mounted`/`init-found`, no `switch-root` | the card mounted and `/sbin/init` was found; the switch itself did not happen | virtual-fs move, `switch_root`, PID 1 trampoline |
| `stage=waiting-root` only | the card never appeared | `sdhc_2`, `vmmc`/`vqmmc`, card detect, RPMh, clock, pinctrl |
| no record at all | says nothing on its own: the mount may have failed, or the minimal `/init` never ran | retained UART/console output, `dmesg`/`last_kmsg` **if** it survived, TWRP's own audit |

`debian_boot_id_match=no` means the record on the card is from an earlier
boot than the Debian that wrote it; treat the initramfs block as historical.

## 4. Deploy a new userspace overlay

Build the tarball on the host:

```sh
./scripts/install-debian-rootfs.sh --tar out/gts9-debian-overlay.tar
adb push out/gts9-debian-overlay.tar /tmp/
```

Then, in TWRP, with the Debian root mounted read-write:

```sh
adb shell sh /tmp/twrp-mount-debian.sh --rw
adb shell
cd /mnt/debian && tar -xpf /tmp/gts9-debian-overlay.tar
sync
cd /
sh /tmp/twrp-mount-debian.sh --umount
```

The tarball contains relative paths only, so extraction cannot escape
`/mnt/debian`. It carries the units, the helpers, the enablement symlinks, the
kernel modules under `lib/modules/<release>` and firmware under
`lib/firmware/`; `depmod` has already been run against the tree.

Pushing individual files with `adb push` is acceptable for a one-off debug
change, but it is not the reproducible deployment path: use the tarball.

## 5. Repair the userspace offline

Direct file edits are the first choice; a chroot is not needed to copy units,
change configuration or read logs.

```sh
adb shell sh /tmp/twrp-mount-debian.sh --rw
adb shell
ls /mnt/debian/usr/lib/systemd/system/gts9-*.service
ls /mnt/debian/etc/systemd/system/*.wants/
```

If a new unit breaks the boot, remove its enablement symlink first - that is
the offline equivalent of `systemctl disable`, and it is enough to get Debian
running again:

```sh
rm -f /mnt/debian/etc/systemd/system/multi-user.target.wants/gts9-usb-acm.service
```

Then fix the unit or the helper, `sync`, and unmount. Every gts9 unit is a
plain `WantedBy=` oneshot with its own `ConditionPathExists`, so each one can
be disabled on its own without touching the others.

Common locations:

| Path | Content |
|---|---|
| `/mnt/debian/etc/systemd/system/` | enablement symlinks, drop-ins (`serial-getty@ttyGS0.service.d/`) |
| `/mnt/debian/usr/lib/systemd/system/` | the `gts9-*` units |
| `/mnt/debian/usr/libexec/` | `gts9-record-debian-stage`, `gts9-usb-acm`, `gts9-panel-recover` |
| `/mnt/debian/lib/modules/<release>/` | kernel modules |
| `/mnt/debian/lib/firmware/` | firmware blobs |
| `/mnt/debian/var/log/gts9-minimal-last-boot` | the persistent boot record |

## 6. Chroot only when a Debian binary must run

TWRP's userspace is arm64 like Debian, but `/proc`, `/sys`, `/dev`, SELinux,
mount namespaces, systemd and DNS are not the Debian environment. Use a chroot
only when an actual Debian program has to execute (for example `depmod` or
`update-initramfs`); never for copying files, changing configuration or
reading logs.

```sh
sh /tmp/twrp-mount-debian.sh --rw
mount --bind /dev  /mnt/debian/dev
mount --bind /proc /mnt/debian/proc
mount --bind /sys  /mnt/debian/sys
chroot /mnt/debian /bin/bash
# ... work ...
exit
umount /mnt/debian/sys
umount /mnt/debian/proc
umount /mnt/debian/dev
sync
sh /tmp/twrp-mount-debian.sh --umount
```

Unmount the bind mounts in reverse order, and always unmount `/mnt/debian`
before rebooting.

## 7. Safety checklist

- Confirm the partition with `blkid` before every write; never assume
  `/dev/mmcblk1p1`.
- Never run `mkfs`, never `fsck -y`, never `wipefs`, never `sgdisk`, never
  `dd of=` on a partition.
- Prefer `ro` for reading; use `--rw` only while changing something.
- `sync` before unmounting, and unmount before rebooting.
- Keep the captured record (and any `dmesg`/UART output) with the test that
  produced it; do not overwrite earlier evidence.
