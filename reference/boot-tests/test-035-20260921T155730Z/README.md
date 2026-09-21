# Test 035 — the display comes up (2026-09-21T15:57:30Z)

The fix for the GPU blocker is a parameter mainline already has:
`msm.separate_gpu_kms=1` makes the Adreno a separate render-only DRM device, so
the display master never waits for a component that needs firmware this initramfs
does not have (`add_gpu_components` is skipped when it is set).

It did not work at first, and the reason is worth keeping: the parameter was in
the image's cmdline but not in the kernel's.  The bootloader appends its own
several-kilobyte cmdline and the last token of ours was being dropped, so
`saperate_gpu_kms` never arrived.  Moving it to the front of our cmdline - right
after the console parameters - fixed that, and the kernel log then shows it in
place.

Artifacts: `vendor_boot 5d9ae64f…` (reordered cmdline), `boot 013ffa94…`,
`init_boot d43750a0…`.

## Result: the display pipeline is up

```
ls /sys/class/drm/                  card0  card0-DSI-1  card0-Writeback-1  version
cat /sys/class/drm/card0-DSI-1/status   connected
cat /sys/class/drm/card0-DSI-1/modes    2560x1600  2560x1600
cat /proc/fb                        0 msm-kmsdrmfb
cat /sys/class/graphics/fb0/name    msm-kmsdrmfb
```

The two modes are this panel's 120 Hz and 60 Hz sets, so the timings were decoded
correctly; the connector is connected, a DRM framebuffer exists, and fbcon now
has the surface the port has been missing since test 015.

## What still keeps the screen dark

The panel answers `ana38407 panel id: 00 00 00` instead of `80 00 04`:

```
panel-samsung-ana38407 ae94000.dsi.0: panel id 00 00 00, expected 80 00 04:
    the panel will stay dark until a suspend/resume re-initialises the DSI host
```

That is the SM-X910 driver's documented cold-boot quirk: the DDIC is left in a
state the freshly probed DSI host cannot use, and re-initialising host and PHY
recovers it.  The port's own note says replaying the init sequence, toggling reset
and dropping the panel supplies were all measured *not* to help - what differs on
resume is that the DSI host and PHY are initialised from scratch.

## The rebind experiment

Unbinding and rebinding `ae94000.dsi` from the console was meant to reproduce
that re-initialisation without a suspend.  It cost the boot: the console and the
USB gadget disappeared immediately afterwards and Windows reported the gadget
with a failed device-descriptor request (code 43), so the DSI host cannot be
rebound under a live DRM master.  The next attempt should use a real
suspend/resume, which is what the port validated.
