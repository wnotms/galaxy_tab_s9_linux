# Test 181 — DPU/DSI display pipeline: instrumentation and baseline

**Status:** instrumentation in place and baselined on hardware; the
intermittent lockup itself was **not** reproduced.  Nothing was changed in the
kernel: the msm driver already ships the tracepoints this needs.

Device SM-X710 / gts9wifi, Debian 13 on `/dev/mmcblk1p1`, Type-C attached,
runs 2026-09-24 01:16Z – 02:0xZ.  Source HEAD at the start: `22630cc`.

## Why this shape

The failure mode under investigation (`enc35 frame done timeout` →
`vblank wait timed out` → `drm_fb_helper_damage_work` → workqueue lockup → RCU
stall, test 178) removes the machine's ability to run commands, so the trace has
to be armed before it happens and has to be written somewhere that survives a
forced restart.  Both are satisfied without a kernel change:

- `gts9-dpu-trace-arm.sh` arms 32 events (`dpu:*` kickoff / frame-done /
  pdone-timeout / TE / wait-timeout, the drm vblank events, the msm atomic
  commit events) plus an `irq==186 || irq==187` filter, and turns tracing on.
- `gts9-dpu-flight.sh` snapshots the ring buffer, the kernel-log tail and the
  display IRQ counters to the microSD every few seconds.
- `gts9-dpu-flight.service` starts the recorder from early boot (before
  `gts9-panel-recover.service`), which is what makes cold-boot capture work.

See `docs/DPU_TRACE.md` for the tracepoint inventory, the driver failure chain
these markers correspond to, and how to read a snapshot.

## What ran, and what it showed

| Experiment | Result | Capture |
|---|---|---|
| 10 + 20 framebuffer blank/unblank cycles with the full trace | 275 kickoffs = 275 frame-done callbacks, 0 pdone/frame-done timeouts, every wait `rc>0` | `r2-cycles10.log`, `r2-batch20.log` |
| One cycle with trace markers, IRQ counters before/after | msm-kms +86…91, dsi_isr +120…121 per cycle; atomic commits complete; vblank event delivered | `r2-onecycle.log`, `r2-window2.log` |
| 80 cycles with a console write between each (racing a commit against the modeset) | 1104 kickoffs, 0 `pdone_timeout`, 0 `frame_done_timeout`, 0 kickoff resets | `r3-race.log` |
| fbcon unbound (`vtcon1` found by name, not index) and 5 cycles | same per-cycle `dpu_encoder_helper_wait_for_irq … ctl_start_irq` message, 0 timeouts, rebind OK | `r3-fbconab.log` |
| Cold boots with the recovery cycle executed | no DPU error, no lockup, panel ends at `80 00 04` | `bootloop-v1.txt`, `bootloop.txt` |
| 30 backlight-only screen toggles (test 180) | 0 DPU/vblank/workqueue/RCU errors | `reference/boot-tests/test-180-…` |

## Findings

1. **The recurring DRM "error" is not the bug.**  Every blank/unblank cycle logs

   ```text
   [drm:dpu_encoder_helper_wait_for_irq] *ERROR* encoder is disabled id=35,
     callback=dpu_encoder_phys_cmd_ctl_start_irq, IRQ=[1, 9]
   ```

   which is the `DPU_ENC_DISABLED` guard returning `-EWOULDBLOCK` immediately
   (`dpu_encoder.c`), i.e. a caller asking a disabled encoder to wait for the
   ctl-start interrupt.  It appears once per cycle in every run, including runs
   with zero failures.
2. **fbcon is not what provokes it.**  With the framebuffer console unbound the
   same message still appears once per cycle, so the console damage worker is
   not a necessary trigger for the modeset-path anomaly.
3. **The healthy pipeline is tight.**  Kickoffs and frame-done callbacks match
   one for one and every `wait_event_timeout()` returns with `rc>0`; the
   kickoff deadline is 84 ms (`KICKOFF_TIMEOUT_MS`).
4. **The lockup was not reproduced** in ~10 cold boots or ~1300 modeset
   commits.  Test 178 saw it once in a comparable number of boots, so it is
   rare; the recorder is armed for every boot of the hunt so that the first
   occurrence is captured with `dpu_enc_phys_cmd_pdone_timeout` (or a kickoff
   with no frame-done) plus the IRQ counters.

## Files

```text
gts9-dpu-trace-arm.sh    arm/disarm the tracepoint set (device-side)
gts9-dpu-flight.sh       flight recorder (device-side, microSD snapshots)
gts9-dpu-flight.service  early-boot unit for the recorder
dpu-bootloop.sh          host-side cold-boot harness (reboot, wait, collect)
bootloop*.txt            per-boot results of the harness
host-captures/           raw COM17 captures for every experiment above
```

Rollback: `systemctl disable --now gts9-dpu-flight.service`, then remove
`/etc/systemd/system/gts9-dpu-flight.service`, `/usr/local/sbin/gts9-dpu-flight`
and `/usr/local/sbin/gts9-dpu-trace-arm`.  None of this is part of the shipped
overlay, and none of it changes kernel behaviour.
