# Debian power-key behavior

The Qualcomm PMIC power key is both the tablet's physical power button and a
suspend wake source. `systemd-logind`'s default action is `poweroff`, and the
first version of this overlay used `HandlePowerKey=suspend` so a short press
would suspend the tablet.

Both were wrong for bring-up work: suspending freezes the SoC, which also
takes the USB ACM gadget down, so the **ttyGS0 debug console disappears
exactly when it is most useful** (observed on hardware: pressing the power key
made COM17 vanish until the next reboot).

## Current behavior: a short press only blanks the panel

| Action | Result |
|---|---|
| Short press | Backlight off / backlight restored (remembered level) |
| Long press | Unchanged: the PMIC's own forced power-off path |
| USB console | **Never affected** - the system keeps running |

The backlight (`/sys/class/backlight/ae94000.dsi.0/bl_power` plus the
remembered `brightness`) is used rather than
`/sys/class/graphics/fb0/blank` **on purpose**: blanking fb0 is a full modeset
on the DPU, and test 178 caught that path hanging the tablet twice (enc35
frame done timeout, vblank wait timeout, workqueue lockup, two CPUs that stop
answering NMIs). A backlight write is a single DSI DCS brightness command
inside the panel driver - the same path a desktop brightness slider uses - and
touches neither the DPU encoder nor vblank.

Two pieces implement that:

- `etc/systemd/logind.conf.d/60-gts9-power-key.conf` sets
  `HandlePowerKey=ignore`, so logind never suspends or powers the tablet off
  behind our back.
- `usr/lib/systemd/system/gts9-power-key.service` runs
  `/usr/libexec/gts9-power-key`, a small freestanding helper that finds the
  PMIC input device (`pmic_pwrkey`), waits for `EV_KEY`/`KEY_POWER`, and
  toggles the panel's blank file. It never suspends, powers off or reboots,
  and systemd restarts it if the input device goes away.

The helper is shipped as C source (`usr/libexec/gts9-power-key.c`) and compiled
for aarch64 by `scripts/install-debian-rootfs.sh`, so the repository stores
sources, never prebuilt binaries. Without `clang`/`ld.lld` the installer warns
and installs everything else.

## Installing and reverting

```sh
sudo ./scripts/install-debian-rootfs.sh /mnt/debian     # or --tar for TWRP
```

Verify on the tablet without pressing anything:

```sh
gts9-power-key --toggle        # screen off, USB console unchanged
cat /sys/class/backlight/ae94000.dsi.0/bl_power
gts9-power-key --toggle        # screen on again
systemctl status gts9-power-key.service
journalctl -u gts9-power-key -b
```

Both transitions are logged to the kernel log
(`gts9-power-key: screen off (backlight off, system keeps running)`), so a
short press can be confirmed from the console even while the screen is dark.

To restore the previous suspend-on-short-press behavior, set
`HandlePowerKey=suspend` in the drop-in, remove
`/etc/systemd/system/multi-user.target.wants/gts9-power-key.service` (or run
`systemctl disable --now gts9-power-key.service`) and reboot. To restore the
systemd default (`poweroff`), delete the drop-in instead.

This is Debian userspace policy; it does not alter the kernel key driver, the
PMIC wake configuration or the initramfs.
