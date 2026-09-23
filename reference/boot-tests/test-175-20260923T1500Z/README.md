# Test 175 — battery-only cold boot after test-173 `init_boot`

**Date:** 2026-09-23 UTC

**Result:** no Debian login became visible; later boot state is unknown.

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

The cursor stopped updating while `init-found` was the last visible stage. The
photo contains no `switch-root` or `GTS9_BOOT_FAIL` marker. Reconnecting Type-C
did not advance the screen. Windows reported “Unknown USB Device / Device
Descriptor Request Failed”, and COM17 was unavailable, so no post-failure
serial or systemd-stage log could be collected.

## What this establishes

For this battery-start attempt, the trace confirms that the microSD was
enumerated, the root filesystem mounted, and `/sbin/init` was found. The missing
`switch-root` screen marker is expected with the current trace implementation:
`boot_rootfs()` moves the `/dev` mount before recording that stage, while
`trace_boot_console()` reopens `/dev/tty0` for every marker. After the move,
`/dev/tty0` is no longer available at the initramfs path. Thus the photo does
not show whether the handoff succeeded, whether the display stopped updating,
or whether systemd started and hung early. A persistent boot-stage record,
kernel log, or working serial capture is needed to locate that point.

This differs from test-174: reconnecting Type-C did not restore visible boot
progress in this attempt. The USB descriptor failure also prevented further
serial diagnosis. No regulator, PMIC, USB PHY, SD, or display configuration was
changed during this test.
