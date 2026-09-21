# Test 036 — the panel recovers: id 80 00 04 and the cell id read back (2026-09-21T16:23:xxZ)

With the DRM pipeline up (test 035), the panel was still in its cold-boot state:
the DDIC answers `00 00 00` instead of `80 00 04` and the screen stays dark.  The
SM-X910 driver documents that only a *from-scratch* re-initialisation of the DSI
host and PHY fixes it, so this run reproduced that with a suspend/resume, and
enabled the wakeup sources that make one safe: the PMIC power key
(`&pon_pwrkey`, shipped disabled in mainline) and `wakeup-source` on the volume
keys and the USB controller.

Artifacts: `boot 3add1ae9…`, `init_boot d40517a9…`, `vendor_boot 2eb8b021…`.

## Result: the recovery works exactly as documented

```
[    5.415311] panel-samsung-ana38407 ae94000.dsi.0: ana38407 panel id: 00 00 00
[    5.545095] panel-samsung-ana38407 ae94000.dsi.0: panel id 00 00 00, expected 80 00 04
[    7.789273] panel-samsung-ana38407 ae94000.dsi.0: ana38407 panel id: 80 00 04
[    7.790375] panel-samsung-ana38407 ae94000.dsi.0: ana38407 cell id: cb1405150d17120bee0c8c
```

After the resume the DDIC answers its real id *and* returns its 22-character cell
id, so the DSI link, the 4nm PHY, the ported panel driver and the DPU are all
talking to the panel correctly.

`card0-DSI-1/status` is `connected`, `/proc/fb` is `0 msm-kmsdrmfb`, and the
framebuffer is the right shape: `virtual_size 2560,1600`, `stride 10240`,
`bits_per_pixel 32`.

## What the owner saw

The screen lit up **garbled** when it resumed and then went dark again.  The dark
part is explained: `fb0/blank` was `4` (FB_BLANK_POWERDOWN) from console
blanking.  Unblanking it (`blank = 0`) and writing to `/dev/tty0` did not put a
readable image on the panel, so the remaining fault is in the pixel path - the
DPU/DSC encode or the DDIC's own timing registers, which are still programmed
with the SM-X910's values because the DCS sequence here is DDIC-level and this
tablet's stock DTBO carries no init sequence of its own.

## Not safe: a suspend with no wake source

Reaching this state cost two detours worth recording.  `echo freeze > /sys/power/state`
never woke and left the tablet stranded (no wakeup source is armed by default on
this board); pressing the power key after `echo mem` did wake it once the PMK8550
pwrkey node was enabled, but the first attempt did not, so /init no longer
suspends: it uses a DPMS off/on cycle instead, which makes the DSI host
runtime-suspend and re-init without any chance of stranding the tablet.
