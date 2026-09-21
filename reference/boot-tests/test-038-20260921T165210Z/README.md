# Test 038 — the command-mode engine starts, but its start never completes (2026-09-21T16:52Z)

This run validates `0005-drm-msm-dpu-start-command-mode-at-enable.patch` and
replaces the panel recovery, and it is the run that finally gets pixels to the
panel: the owner reports the console text **partially visible** as a few faint
white lines.  What is left is the decode, not the transfer.

Artifacts: `boot 58eea518…` (kernel `5e3c36b2…` Image.gz + `65bee980…` dtb),
`init_boot 417cf070…` (initramfs `90b3e4ba…`), `vendor_boot c1749463…` unchanged
from test 037 and deliberately not reflashed.  Source `f8b8263`, report
`7a0b2d27…` verified against the sidecar `/init` wrote.

## The recovery works, and the connector's dpms was the wrong knob

`display_recover` now cycles `fb0/blank` instead of writing `card0-DSI-1/dpms`,
which fails on this board ("could not turn the connector off") so the panel was
never re-initialised - the report shows it in the act:

```
[    9.199744] gts9-init: display: the panel is in its cold-boot state (id 00 00 00);
              cycling the framebuffer blank to re-initialise the DSI link
[   11.442154] panel-samsung-ana38407 ae94000.dsi.0: ana38407 panel id: 80 00 04
[   11.444786] panel-samsung-ana38407 ae94000.dsi.0: ana38407 cell id: cb1405150d17120bee0c8c
[   16.234151] gts9-init: display: the blank cycle re-initialised the link; the panel answered its id
[   17.877002] gts9-init: display: framebuffer unblanked (blank=0)
```

The panel is initialised and the DDIC answers in 11 s, versus the 120 s the
suspend/resume took, and nothing has to suspend.

## The patch removes the failure it was written for

The "encoder is disabled" abort that test 037 isolated is gone:

```
ctl-start-errors=0        # dmesg | grep -c wait_for_irq
```

so the flush and start now happen with the encoder enabled.  The comment in the
patch says exactly what the old failure was: `_dpu_encoder_kickoff_phys()` skipped
the still-disabled encoder during the commit's atomic flush, and nothing started
the CTL afterwards.

## What remains: the start never completes

The commit now waits for the CTL start interrupt and times out:

```
[drm:_dpu_encoder_phys_cmd_wait_for_ctl_start:676] [dpu error]enc35 intf1 ctl start interrupt wait failed
[drm:dpu_kms_wait_for_commit_done:527] [dpu error]wait for commit done returned -22
msm_dpu ae01000.display-controller: [drm] vblank wait timed out on crtc 0
```

The vblank timeouts matter as much as the error: in command mode DRM's vblank
comes from the tearcheck's read-pointer interrupt, so it never firing means the
interface never consumed a frame.  The plane, CRTC and mode are all consistent
in the same traces (`fb 105`, `htotal 2692`, `vtotal 1738`, `clock 561443`), and
the tearcheck's own `DPU_DEBUG_CMDENC` messages never appear, so the failure is
below the DRM bookkeeping.

With the mode-set framing in place, the owner's observation is the useful part:
**the four faint white lines are the console text**, arriving but not decoding.
Frames reach the DDIC now; the picture does not survive the compression path.

## The framebuffer is fine (a red herring worth recording)

The report contains two early warnings -

```
fb0: sys_imageblit: framebuffer is not in virtual address space.
fb0: sys_fillrect: framebuffer is not in virtual address space.
```

\- which look fatal but are not: they are `fb_warn_once` draws from before
`msm_fbdev_driver_fbdev_probe()` had assigned `fbi->screen_buffer`.  A direct
round trip on the live console proves the mapping:

```
printf "HELLO" | dd of=/dev/fb0 bs=1 seek=100000
dd if=/dev/fb0 bs=1 skip=100000 count=6 | od -An -c
   H   E   L   L   O  \0
```

So fbcon's writes do land in the scanout buffer, and every test that wrote
colours, ANSI clears or a 500-row white band into it was writing to the right
place.

## Evidence in this directory

| file | what it holds |
|---|---|
| `bringup-report.txt` | the boot report, sha256-verified against the .sha256 sidecar |
| `console-test038.log`, `console-panelstate.log` | the fix's effect: no "encoder is disabled" abort |
| `console-fbtest.log` | the /dev/fb0 write/read round trip |
| `console-band.log`, `console-band2.log` | the white band and the repeated enable cycles |
| `console-drmdebug*.log`, `console-trace*.log` | DRM debug: atomic_begin, kickoff, commit-done wait |
| `pretest-and-flash.log`, `kernel-sha256.txt`, `bundle-*.txt/log` | flash transcript with hashes |
