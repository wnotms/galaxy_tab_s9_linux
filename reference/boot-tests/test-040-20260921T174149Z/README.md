# Test 040 — the panel displays: official X710 power-on/sync commands (2026-09-21T17:41Z)

The display works.  The console is readable on the panel at boot, and new output
appears live as the tablet writes it.  What fixed it is not the compression path
and not the DPU: it is the panel's own power-on and sync sequence, recovered from
Samsung's official open-source archive for this exact tablet
(`Kernel.tar.gz:vendor/qcom/opensource/display-drivers/msm/samsung/panel_data_file/GTS9_ANA38407_AMSA10FA01.dat`,
sha256 `7bdecb7a…`), which supplies the revision-D commands the port had been
guessing at with the SM-X910's values.

Artifacts: `boot 27752545…` (Image.gz `a304ebef…` + dtb `65bee980…`), `init_boot`
and `vendor_boot` unchanged from test 038 and deliberately not reflashed.  Source
`202b7c6`.  Report `48fb3e92…`, verified against the sidecar `/init` wrote.

## What the owner saw

- the boot command line **visible on the panel** while the tablet came up;
- a green-background, black-text marker written to `/dev/tty0` **readable**;
- three lines written two seconds apart — `LINE-1`, `LINE-2`, `LINE-3` — each
  **appearing as it was written**, which is the part that rules out a static
  or half-decoded image.

## The commands that made the difference

`docs/DISPLAY_X710_OFFICIAL_V1.md` lists them; the ones that matter here are the
DDIC's own refresh-mode registers, which the inherited sequence never wrote:

- `0x60 = 0`, `DD` offset `0x13 = 0`, `B9` offset `0x10 = 80 00 00 00` —
  explicit 120HS selection;
- the X710's `SLEW_BOOSTING_OFF` and the complete `PM_EN_DISP_ON_DELAY`,
  including the indirect register `0x1435`;
- the stock revision-C+ sleep-out delay of 50 ms;
- `B9` offset `0x0e = 0x15` removed from TSP sync (an X910 value).

## Evidence from this boot

```
[    5.665790] panel-samsung-ana38407 ae94000.dsi.0: ana38407 panel id: 00 00 00
[    7.261097] gts9-init: display: the panel is in its cold-boot state (id 00 00 00);
              cycling the framebuffer blank to re-initialise the DSI link
[    8.262658] panel-samsung-ana38407 ae94000.dsi.0: ana38407 panel id: 80 00 04
[    9.097809] gts9-init: display: the blank cycle re-initialised the link; the panel answered its id
```

`dmesg | grep -c "ctl start"` is **0**: with the official sequence in place the
command-mode start completes, which it never did in tests 037-039.  The panel
still cold-boots dark and still needs the framebuffer blank-cycle recovery, which
now takes 8 s instead of 120 s.

## What was ruled out along the way

- **DSC**: the official `DSC_SETTING` carries an 88-byte PPS, and the PPS this
  driver generates matches it field for field (DSC 1.1, 8 bpc, 8 bpp, 2560x1600,
  1280x100 slices, chunk 1280, the standard 8 bpp `rc_buf_thresh`).  The
  compression path was never the fault - test 039's no-DSC build could not even
  reach scanout, because uncompressed modes exceed the DSI OPP ceiling of
  358 MHz (`docs/DISPLAY_OFFLINE_AUDIT.md`).
- **The DPU kickoff**: `0005-drm-msm-dpu-start-command-mode-at-enable.patch` is
  retired to `kernel/patches/pending/`.  `msm_atomic_commit_tail()` reaches
  `dpu_kms_flush_commit()` -> `dpu_crtc_commit_kickoff()` after the modeset
  enables, so the normal path does submit the first frame; test 038's abort was
  a symptom of the panel never coming up, not of a missing kickoff.
- **The framebuffer and fbcon**: the `sys_fillrect` "not in virtual address
  space" warnings are `fb_warn_once` draws from before `msm_fbdev` assigned
  `screen_buffer`; a `/dev/fb0` write/read round trip returns what was written.

## Evidence in this directory

| file | what it holds |
|---|---|
| `bringup-report.txt` | the boot report, sha256-verified against its sidecar |
| `console-test040.log` | panel id 80 00 04 at 8.26 s on the new kernel |
| `console-marker.log` | the green/black marker written to `/dev/tty0` |
| `console-live.log` | `LINE-1/2/3` written two seconds apart, seen live |
| `pretest-and-flash.log` | flash transcript, `boot` only, hashes verified |
| `device-layout.txt`, `backup-verification.txt`, `pretest-*.txt` | pre-flash state and stock backups |
| `bundle-*`, `kernel-SHA256SUMS` | the images and their validated manifest |

The owner's observation is the authority for the screen; the console and the
report are the authority for kernel state.  Nothing in this directory is inferred
from the other: the report predates the marker and the liveness test.
