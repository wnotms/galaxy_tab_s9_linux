# Test 171 — correlate the retained panel marker with Debian over COM17

**Result:** while the owner reported that the panel still showed the two
initramfs early-console lines, a read-only COM17 login established that the
current Linux boot had reached Debian 13. `/` was mounted read-write from
`/dev/mmcblk1p1` as ext4, and `serial-getty@ttyGS0` was active. The static panel
text therefore did not mean this boot was still waiting in initramfs; the panel
was retaining earlier framebuffer contents. Why tty1 did not replace those
contents was not investigated here.

## Evidence

- Current boot ID: `9e66d41f-e612-4ab7-9ab9-3a0a4218b865`.
- Kernel: `7.2.0-rc3-gts9wifi-dirty`, AArch64.
- `/proc/cmdline` contains `gts9_rootfs=/dev/mmcblk1p1`.
- `findmnt /` and `df -h /` both identify `/dev/mmcblk1p1`; it is `ext4 rw`.
- `systemctl is-active serial-getty@ttyGS0.service` returned `active`.
- `/var/log/gts9-last-boot-stage` was absent, so no persisted initramfs stage
  record was available for this boot.
- `/var/log/gts9-last-poweroff-stage` contains boot ID
  `fbdf54c1-3232-4127-b399-f4d4f98d0974`, different from the current ID. It is
  stale for this boot and cannot establish this boot's shutdown path.
- The unprivileged `journalctl` query returned an ACL error and no entries; no
  journal conclusion is drawn from that query.

The owner had reconnected Type-C before this boot, so this is evidence for the
Type-C-triggered startup only. It does not test battery-only cold boot. It also
does not provide a trace of the kernel's PSCI `SYSTEM_OFF` call.

## Method and files

COM17 was opened at 115200 8N1. The first read-only attempt found no prompt and
sent no credentials. A later attempt sent an empty return to request the
getty prompt, authenticated using the owner's mode-600 local credential file,
ran read-only commands, and logged out. No password was saved in the capture or
repository. No sudo command, filesystem write, reboot, poweroff, or flash was
performed. PowerShell's decoded serial text, including terminal control
sequences, is kept in the two session transcripts; a raw USB byte capture was
not available.

- `com17-readonly-login.txt`: first open, no login prompt, no input.
- `com17-prompt-retry.txt`: prompt acquisition and initial read-only Debian
  identity / stage checks.
- `com17-rootfs-readonly.txt`: boot ID, cmdline, mounted root, and stage-file
  check.
- `owner-observation.txt`: panel state as reported by the owner.
- `source.txt`: source commit and method summary.
