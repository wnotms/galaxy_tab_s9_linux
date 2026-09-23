# Test 165 — reboot Debian into TWRP

**Result: PASS.** At 2026-09-23 06:12:49 UTC, the Debian-side helper wrote and verified `boot-recovery` in the UFS `misc` BCB, issued a plain system reboot, and the tablet entered TWRP. No kernel, DTB, recovery, or other partition was flashed.

## Before the reboot

The tablet was running Debian 13 on Linux `7.2.0-rc3-gts9wifi-dirty`; PID 1 was systemd and `/` was `/dev/mmcblk1p1`. The COM17 capture also records the kernel command line and confirms the helper was not initially installed (`console-pre-retry.log`). The owner request and pre-test source revision are in `source.txt`.

The helper’s read-only check identified `/dev/sda10` by GPT label `misc`, confirmed it was not mounted and was not `/`, and found an empty BCB. Linux reports its size as 2048 512-byte sectors; the GPT report records 256 4096-byte sectors. Both describe the same 1 MiB partition. The helper’s check and the device’s block-size evidence are in `console-stage.log` and `console-layout.log`.

Two helper defects surfaced before the reboot and were fixed in separate pushed commits:

- `8e22823` accepts the actual `sda10` partition name.
- `f2236ff` compares the sysfs size in its 512-byte units.

The first attempted `--check` correctly refused to write because of the bad partition-name pattern. The subsequent check passed without a warning and reported `BCB command: (empty, boots mainline)`.

## Reboot and recovery confirmation

`console-reboot.log` records the exact invocation and confirms:

```text
gts9-debian-to-recovery: BCB written to /dev/sda10 and verified: boot-recovery
gts9-debian-to-recovery: rebooting with a plain restart; the recovery request is in the BCB, not in the kernel
```

The Windows ADB host then reported the tablet as `recovery`, product `twrp_gts9wifi`, model `SM_X710`. `ro.twrp.version` was `3.7.1_12-gts9wifi`, `ro.twrp.boot` was `1`, and `adb shell` ran as root. `/etc/recovery.fstab` and `/tmp/recovery.log` existed. See `adb-pre.txt`, `twrp-version.txt`, `twrp-confirmation.log`, and `twrp-observation.log`. The recovery ADB state stayed present throughout the 45-second observation; the complete interval from the reboot command to the final observation exceeded 150 seconds.

`recovery.log` and `recovery-dmesg.txt` are from TWRP’s recovery environment, not from the mainline Debian kernel. No panic or OOPS occurred, so no mainline `last_kmsg` or pstore capture was available or applicable. The initial generic ADB observer only recognized the `device` state and missed ADB’s `recovery` label; the direct confirmation and corrected `twrp-observation.log` are authoritative.

## Evidence inventory

- `console-*.log`: raw COM17 commands and replies, including the guarded failure before the helper fix and the successful read-only check.
- `adb-pre.txt`, `adb-observation.log`, `twrp-*.txt`, `twrp-observation.log`: host ADB state and TWRP confirmation.
- `recovery.log`, `recovery-dmesg.txt`: recovery-side logs, explicitly labelled as such.
- `adb-pull.log`: transcript for pulling the recovery log.
- `source.txt`: owner request and source revision.
- `SHA256SUMS`: hashes of the archived evidence files.

The helper was installed at `/usr/local/sbin/gts9-debian-to-recovery` on the Debian root filesystem for reuse. The tablet was left running in TWRP; it was not automatically rebooted back to Debian.
