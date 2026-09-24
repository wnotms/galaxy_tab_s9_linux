# Debian power-key behavior

The Qualcomm PMIC power key is both the tablet's physical power button and a
suspend wake source.  `systemd-logind`'s default action is `poweroff`, and an
earlier version of this overlay used `HandlePowerKey=suspend` so a short press
would suspend the tablet.

Both were wrong for bring-up work: suspending freezes the SoC, which also takes
the USB ACM gadget down, so the **ttyGS0 debug console disappears exactly when
it is most useful** (observed on hardware: pressing the power key made COM17
vanish until the next reboot).

## logind cannot blank the screen

`HandlePowerKey=blank` is not an accepted value.  systemd 257 rejects it and,
because an invalid value is simply ignored, falls back to its built-in default
`poweroff` — the opposite of what is wanted:

```text
systemd-logind[800]: /etc/systemd/logind.conf.d/60-gts9-power-key.conf:2:
  Failed to parse HandlePowerKey=blank, ignoring: Invalid argument
```

The accepted values are `ignore`, `poweroff`, `reboot`, `halt`, `kexec`,
`suspend`, `hibernate`, `hybrid-sleep`, `suspend-then-hibernate`, `sleep`,
`lock`, `factory-reset` and `secure-attention-key`.  The drop-in therefore sets
**`HandlePowerKey=ignore`** and a small helper owns the key instead.

## Current behavior

| Action | Result |
|---|---|
| Short press (< 1.2 s) | Backlight off; the next short press restores the remembered level |
| Long press (>= 1.2 s) | Ignored: the PMIC's own forced power-off stays the owner of a hold |
| `systemctl suspend` | Unchanged — the manual suspend interface |
| `shutdown` / `poweroff` | Unchanged — real power off (see `BOOT_POWER_DIAGNOSTICS.md`) |

The system keeps running through a screen toggle: USB console, tty1, network
and CPU all stay up.  Only the panel backlight changes.

## Why the backlight and not `fb0/blank`

Blanking `/sys/class/graphics/fb0/blank` is a full modeset on the DPU, and the
DPU has an intermittent failure in that path (enc35 frame done timeout →
`vblank wait timed out` → workqueue lockup → RCU stalls; see
`MINIMAL_ROOTFS_BOOT.md`).  A backlight write is a single DSI DCS brightness
command inside the panel driver — the same path a desktop brightness slider
uses — and touches neither the DPU encoder nor vblank.  Every run in
`reference/boot-tests/test-180-20260924T011002Z/` confirms `fb0/blank` stays 0.

The helper also never enters suspend, never powers off and never reboots, and
if the backlight node is missing it logs one line and does nothing — it never
falls back to `fb0/blank` or to suspend.

## Implementation

- `etc/systemd/logind.conf.d/60-gts9-power-key.conf` sets
  `HandlePowerKey=ignore`, so logind never suspends or powers the tablet off
  behind our back.
- `usr/lib/systemd/system/gts9-power-key.service` runs
  `/usr/libexec/gts9-power-key` and restarts it if it exits.
- `usr/libexec/gts9-power-key.c` is a freestanding aarch64 helper (no libc):
  - it finds the key **by capability** (`EVIOCGBIT` plus the sysfs
    `capabilities/key` bitmap), never by event number, and never grabs the
    device, so logind, the kernel's own handling and a future desktop session
    still see it;
  - it decides on key **release** and compares the input event timestamps with
    `LONG_PRESS_MICROSECONDS` (1.2 s), so a hold cannot blank the screen on the
    way down and cannot be "restored" when the button is released;
  - it keeps state in `/run/gts9-power-key/` (`last-brightness`,
    `display-off`), i.e. RAM only, so a short press does not write the microSD;
  - `_start` reads `argc`/`argv` from the initial stack: a freestanding entry
    point gets nothing in `x0` on arm64, and without that `--toggle` silently
    fell into the key-watch loop instead of toggling once.

The helper is shipped as C source and compiled for aarch64 by
`scripts/install-debian-rootfs.sh` (`GTS9_CC`/`GTS9_LD` overridable; a missing
toolchain warns and installs everything else), so the repository stores
sources, never prebuilt binaries.

## Installing and verifying

```sh
sudo ./scripts/install-debian-rootfs.sh /mnt/debian     # or --tar for TWRP
```

On the tablet, without pressing anything:

```sh
gts9-power-key --diag        # which event devices advertise KEY_POWER
gts9-power-key --toggle      # one screen-off/screen-on transition
gts9-power-key --stress 30   # 30 cycles, ~60 s, for the DPU watch
cat /sys/class/backlight/ae94000.dsi.0/bl_power     # 4 = off, 0 = on
cat /sys/class/graphics/fb0/blank                   # must stay 0
ls /run/gts9-power-key/                             # last-brightness, display-off
journalctl -k -g gts9-power-key
systemctl status gts9-power-key.service
```

Both transitions are logged to the kernel log
(`gts9-power-key: screen off (backlight off, system keeps running)` /
`screen on (backlight restored)` / `long press ignored (PMIC owns it)`), so a
press can be confirmed from the console even while the screen is dark.

Measured on hardware (test 180): 30/30 automated cycles with no DPU, vblank,
workqueue or RCU error, and the owner's physical short presses toggling while a
3 s hold was ignored.

## Reverting

To restore the previous suspend-on-short-press behavior, set
`HandlePowerKey=suspend` in the drop-in, remove
`/etc/systemd/system/multi-user.target.wants/gts9-power-key.service` (or run
`systemctl disable --now gts9-power-key.service`) and reboot.  To restore the
systemd default (`poweroff`), delete the drop-in instead.

This is Debian userspace policy; it does not alter the kernel key driver, the
PMIC wake configuration or the initramfs.
