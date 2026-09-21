# Test 037 — the panel is initialised and lit, but the pixel path never starts (2026-09-21T16:30Z)

Recovery was moved out of the suspend path: a DPMS off/on cycle re-initialises the
DSI host and PHY just as a resume does, without the risk of stranding the tablet,
and the console is unblanked (`consoleblank=0`) so the panel stays lit.  The
report now carries the post-recovery dmesg, the DRM state, the panel backlight
and the framebuffer, so one boot answers "is the pipeline up?".

Artifacts: `init_boot 8f47bfc4…`, `vendor_boot c1749463…`, kernel
`23e521b3…` (Image.gz) / `65bee980…` (dtb), source `3be94ee`.

## The pipeline is up, from the kernel's point of view

```
Console: switching to colour frame buffer device 320x100
/proc/consoles:  tty0   -WU (E   p  )    4:1
/sys/class/vtconsole/vtcon1/ (M) frame buffer device bind=1
crtc[103]: crtc-0   enable=1 active=1  mode: "2560x1600" 120 561443 …
plane[43]: plane-0  crtc=crtc-0 fb=105  allocated by = [fbcon]
            format=XR24   size=2560x1600   pitch=10240
            sspp[0]=sspp_8 src=1280x1600+0+0   sspp[1]=sspp_8 src=1280x1600+1280+0
/sys/class/backlight/ae94000.dsi.0: brightness=2047 max_brightness=2047
```

So fbcon is bound and drawing into the very framebuffer the DPU has committed,
the CRTC is active, the plane is split into the two 1280-wide rectangles a
two-slice DSC panel needs, and the DDIC is at full brightness.  The panel itself
answers after the recovery (`panel id: 80 00 04`, `cell id: cb1405150d17120bee0c8c`)
and dmesg has **no DSI error after it**.

## What the owner saw, twice

`屏幕亮起但是花屏，一段时间后熄灭` — the panel lights up garbled, the brightness
rises (the driver's `0x51` write landing), then it blanks itself.  `花屏，变亮，熄灭`
again after a forced panel re-initialisation followed by a kickoff attempt.

That sequence is the DDIC's *own* power-on RAM at brightness, followed by its
no-data timeout: **not one frame is ever scanned out**.  Solid fills written to
`/dev/fb0`, ANSI colour clears on `/dev/tty0` and a green field with a marker all
produced no change at all — fb0/blank was `0` throughout, so those writes were
no-ops to begin with (`fb_blank` only acts on a state change).

## The fault is on the enable path, not the disable path

The blank/unblank cycle re-initialises the panel (the id is read again), and
counting `dpu_encoder_helper_wait_for_irq` failures around each half isolates it:

```
before=2
after-blank=2      crtc still enable=1
after-unblank=3    [drm:dpu_encoder_helper_wait_for_irq] *ERROR* encoder is disabled
                     id=35, callback=dpu_encoder_phys_cmd_ctl_start_irq, IRQ=[1, 9]
```

`dpu_encoder_phys_cmd_wait_for_commit_done()` only waits for the CTL start when
`is_started()` is false, and the wait then bails out with `-EWOULDBLOCK` because
the physical encoder is still `DPU_ENC_DISABLED` at that point.

## Root cause: the first frame of every enable is never started

The DRM atomic commit order is disables → planes → enables, so the atomic flush
that kicks off a command-mode frame runs **before** `dpu_crtc_enable()` has
enabled the physical encoder.  `_dpu_encoder_kickoff_phys()` skips encoders whose
`enable_state` is `DPU_ENC_DISABLED`, so the flush *and* the CTL start are lost,
and `dpu_encoder_phys_cmd_enable()` only programs the interface — it never starts
it.  Nothing else does either: fbcon writes straight into the scanout buffer
without committing, and a forced no-op commit (a fbcon unbind/rebind, which does
reach `fb_set_par`) does not survive the atomic core's unchanged-state check.

This is invisible on a system with a compositor — the SM-X910 port of the same
DDIC works because its compositor's next page flip kicks the engine — and fatal
on a fbcon-only system, which is exactly what the initramfs is.

## Consequence

`kernel/patches/0005-drm-msm-dpu-start-command-mode-at-enable.patch` flushes and
starts the CTL at the end of `dpu_encoder_phys_cmd_enable()`, next to the
register programming that has just made the interface ready.  Validation is test
038.

## Evidence in this directory

| file | what it holds |
|---|---|
| `console-test037.log` | the boot console: recovery, panel id, DRM report sections |
| `console-dpustate.log` | the DRM debugfs state: active CRTC, fbcon plane, two DSC rectangles |
| `console-backlight.log` | backlight 2047/2047 and a clean post-recovery dmesg |
| `console-isoerr.log` | the blank/unblank isolation of the `ctl_start_irq` failure |
| `console-blankcycle.log`, `console-greentest.log`, `console-2step.log` | the forced re-initialisation and kickoff attempts |
| `console-vtcon.log` | the fbcon rebind that reaches `fb_set_par` but not the kickoff |
| `pretest-and-flash.log`, `kernel-sha256.txt` | flash transcript with hashes |
