# Test 175 — battery-only cold boot after test-173 `init_boot`

**Date:** 2026-09-23 UTC

**Result:** stalled after `init-found`; no successful Debian login in this trial.

## Setup

- The device was running test-173 on Linux `7.2.0-rc3-gts9wifi-dirty` with
  `/dev/mmcblk1p1` mounted as the Debian root filesystem.
- The test-173 `init_boot.img` was the only partition written for this
  candidate. Its host and device readback SHA-256 is recorded in test-173.
- A serial command requested `systemctl poweroff`; the command returned status
  0. After the host lost COM17, Type-C was disconnected and the tablet was
  powered on from battery.

## Observation

The screen photo (`screen-stage-report.jpg`) shows successful reports for the
framebuffer, Pogo keyboard and input devices, followed by these boot stages:

```text
GTS9_BOOT_STAGE=waiting-mmc
GTS9_BOOT_STAGE=mmc-found
GTS9_BOOT_STAGE=mounting-root
GTS9_BOOT_STAGE=root-mounted
GTS9_BOOT_STAGE=init-found
```

The cursor stopped updating while `init-found` was the last visible stage.
The photo contains no `switch-root`, `systemd-basic`, `tty1-getty-active`, or
`GTS9_BOOT_FAIL` marker. Reconnecting Type-C did not advance the screen. Windows
reported “Unknown USB Device / Device Descriptor Request Failed”, and COM17 was
unavailable, so no post-failure serial log could be collected.

## What this establishes

For this battery-start attempt, the trace confirms that the microSD was
enumerated, the root filesystem mounted, and `/sbin/init` was found. The missing
`switch-root` screen marker does not prove that execution stopped before the
handoff: that marker is recorded after the initramfs moves `/dev`, `/proc`,
`/sys`, and `/run`, while the separate framebuffer trace writer checks
`/dev/tty0`, whose availability can change after `/dev` is moved. The available
evidence does not determine whether execution stopped during the handoff or
later, including during early systemd startup.

This differs from test-174: reconnecting Type-C did not restore visible boot
progress in this attempt. The USB descriptor failure also prevented further
serial diagnosis. No regulator, PMIC, USB PHY, SD, or display configuration was
changed during this test.
