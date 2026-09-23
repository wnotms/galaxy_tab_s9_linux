# Test 172 — poweroff and early-boot diagnostic candidate

**Status:** diagnostic candidate flashed to `boot`, `init_boot`, and
`vendor_boot`; two Type-C-attached boots reached Debian. One later reboot from
TWRP and a separate startup attempt stopped at a blinking cursor. A forced
restart recovered Debian. The latter startup's cable state was not captured
reliably enough to classify it as a battery-only cold boot.

The user authorized this candidate and real poweroff test. The flash scope was
limited to `boot`, `init_boot`, and `vendor_boot`; `vbmeta` and `dtbo` were not
written. Candidate source commit:
`7d04768985c8ba8fc5b5ed847a3d31679fc34447`. Repository revision before test:
`d5e7d51a7d6d2b54179ff947bec9b86aac1e15b0`.

## Flash verification

TWRP identified the device as SM-X710 / `gts9wifi`; partition identities and
capacities were checked before writing. Fresh backups matched the host copies.
Each candidate partition was written separately, then read back and SHA-256
matched. The exact hashes and write output are in `flash-write-readback.txt`.
No image or full partition backup is stored in Git; the host staging directory
is `/home/ms/Samsung/gts9-flash-tests/test-172-20260923T131339Z`.

## Observations

- With Type-C connected, the candidate boot reached Debian 13 on
  `/dev/mmcblk1p1`, systemd PID 1, and the tty1 getty. See
  `com17-candidate-boot.txt` and `com17-diagnostics.txt`.
- An authorized `systemctl poweroff` reached the systemd poweroff marker. The
  tablet then automatically started again with Type-C attached. The owner
  reports this also happens on Samsung software, so it does not establish a
  Linux poweroff failure. The captured TWRP `last_kmsg` did not contain the
  candidate's Linux poweroff markers; the final PSCI call remains unobserved.
- After a later `adb reboot system` from TWRP, the owner reported a black
  screen with a slowly blinking cursor and no EF-DX710 Pogo input. Type-C was
  connected; Windows continued to enumerate COM17 without a PnP error, but
  opening the port failed and ADB showed no device. No boot stage was
  recovered for this attempt. The screen briefly showed the initramfs early
  display-console marker, but no explicit boot-stage or Debian prompt.
- In a later startup attempt, the owner again reported the blinking cursor and
  no Pogo input. Holding Power+Volume Down forced a restart into Debian. The
  post-restart read-only audit found `/dev/mmcblk1p1` mounted as `/`, systemd
  and tty1 active, UDC `a600000.usb` configured, and the Pogo input device
  registered. The owner then confirmed typing and Caps Lock both worked.
  This confirms recovery after a forced restart, but does not identify where
  the preceding boot stopped.

The candidate's opt-in stage messages did not appear because `/init` parsed
`/proc/cmdline` before mounting `/proc`. That diagnostic ordering bug is
corrected in the separate test-173 host-built candidate; test-172 artifacts
and evidence remain unchanged.

The early-boot console tracing and the poweroff trace are diagnostic only; no
power, regulator, USB PHY, panel sequence, or Pogo protocol settings were
changed by this candidate. Do not infer the stuck point from the cursor alone.

## Still required

1. Repeat the battery-only cold-start test with Type-C disconnected after
   installing the corrected trace candidate, and capture the visible
   `GTS9_BOOT_STAGE`/`GTS9_BOOT_FAIL` result, or explicitly record that the
   device does not start on battery.
2. Continue to keep the observations separate: a TWRP-to-candidate reboot
   with Type-C attached is not a battery-only cold boot.
