# Tracing the X710 DPU panel-recovery hang

The intermittent failure this document instruments leaves the tablet unable to
run commands at all (workqueue lockup, RCU stalls), so it can only be diagnosed
with tracing that is already armed *before* it happens and that persists its
buffer somewhere the machine can still reach afterwards.

No kernel change is needed for this: the msm driver already defines the
tracepoints that matter, and they are switchable at runtime.

## What is available on the device

```text
/sys/kernel/debug/tracing/events/dpu/      dpu_enc_kickoff, dpu_enc_frame_done_cb,
                                           dpu_enc_frame_done_timeout,
                                           dpu_enc_phys_cmd_pdone_timeout,
                                           dpu_enc_wait_event_timeout,
                                           dpu_enc_trigger_start/flush,
                                           dpu_enc_phys_cmd_connect_te, ...
/sys/kernel/debug/tracing/events/drm/      drm_vblank_event, ..._queued, ..._delivered
/sys/kernel/debug/tracing/events/drm_msm_atomic/
                                           msm_atomic_commit_tail_start/finish,
                                           msm_atomic_flush_commit, ...
/sys/kernel/debug/tracing/events/irq/      irq_handler_entry/exit, filterable
```

`msm-kms` (IRQ 186) carries the DPU interrupts and `dsi_isr` (IRQ 187) the DSI
ones; both are on the `msm_mdss` bank, so an IRQ filter of
`irq==186 || irq==187` keeps the trace bounded.

Arming is one script:

```sh
gts9-dpu-trace-arm.sh          # 32 events + the IRQ filter, tracing_on=1
gts9-dpu-trace-arm.sh stop     # tracing off
```

## Why a flight recorder

A hang takes away the shell that would read the trace buffer.  The recorder
snapshots the ring and the kernel-log tail to the microSD every few seconds, so
the last snapshot survives a forced restart:

```sh
gts9-dpu-flight.sh /var/log/gts9-dpu-flight.txt 5
```

`gts9-dpu-flight.service` runs it from early boot (before
`gts9-panel-recover.service`), which is what makes a cold-boot capture possible.
Enable it only while investigating: it writes the microSD continuously.

## The failure chain in the driver

Read from the tree (`drivers/gpu/drm/msm/disp/dpu1/`), which is what the trace
markers below correspond to:

1. An atomic commit kicks the command-mode encoder off and then waits for the
   pingpong-done interrupt:
   `dpu_encoder_phys_cmd_wait_for_commit_done()` →
   `_dpu_encoder_phys_cmd_wait_for_idle()` →
   `dpu_encoder_helper_wait_for_irq(INTR_IDX_PINGPONG, …)` with
   `KICKOFF_TIMEOUT_MS = 84`.
   `dpu_enc_wait_event_timeout` is traced on every `wait_event_timeout()`
   return, with the `rc` in the payload: `rc > 0` means the event arrived,
   `rc == 0` means the deadline was hit.
2. If the wait times out but the IRQ status register *does* show the interrupt,
   the driver calls the handler itself and continues (benign fallback).  Only
   when the status register is also empty does it return `-ETIMEDOUT`.
3. `-ETIMEDOUT` → `_dpu_encoder_phys_cmd_handle_ppdone_timeout()`:
   trace `dpu_enc_phys_cmd_pdone_timeout`, `DRM_ERROR("… kickoff timeout …")`,
   `msm_disp_snapshot_state()`, and `enable_state = DPU_ENC_ERR_NEEDS_HW_RESET`.
   `PP_TIMEOUT_MAX_TRIALS = 10` consecutive reports turn the frame event into
   `DPU_ENCODER_FRAME_EVENT_PANEL_DEAD`.
4. Separately, a frame-done timer (`dpu_encoder_frame_done_timeout()`) logs
   `DPU_ERROR_ENC_RATELIMITED("frame done timeout")` — the message test 178
   captured — takes a display snapshot and sends
   `DPU_ENCODER_FRAME_EVENT_ERROR`.  Trace: `dpu_enc_frame_done_timeout`.
5. The recovery is inside the *next* commit: `prepare_for_kickoff` sees
   `DPU_ENC_ERR_NEEDS_HW_RESET` and resets every physical encoder.  Trace:
   `dpu_enc_prepare_kickoff_reset`.
6. The commit that is waiting is the one `drm_fb_helper_damage_work` issued for
   the framebuffer console.  If it never completes (no flip done, no vblank),
   the worker blocks and the machine reports a workqueue lockup and RCU stalls:
   the observed hang is the *consequence*, the missing pingpong-done interrupt
   is the cause.

## The one recurring anomaly, and why it is not the bug

Every framebuffer `blank`/`unblank` cycle prints:

```text
[drm:dpu_encoder_helper_wait_for_irq] *ERROR* encoder is disabled id=35,
  callback=dpu_encoder_phys_cmd_ctl_start_irq, IRQ=[1, 9]
```

That is the `phys_enc->enable_state == DPU_ENC_DISABLED` guard at the top of
`dpu_encoder_helper_wait_for_irq()`: a caller asks a *disabled* encoder to wait
for the ctl-start interrupt, and the function returns `-EWOULDBLOCK`
immediately.  It is noise, not a timeout — which is why it also appears in runs
with zero failures, and why it must not be read as the hang.

Measured with fbcon unbound (`echo 0 > /sys/class/vtconsole/vtcon1/bind`, the
console identified by its `name`, not by index): the message still appears once
per cycle, so the framebuffer console's damage worker is **not** what triggers
it.

## Measurements so far

| Run | Result |
|---|---|
| 20 framebuffer blank/unblank cycles | 275 kickoffs, 275 frame-done callbacks, 0 timeouts, all waits `rc>0` |
| 80 cycles with a console write between them (racing a commit against the modeset) | 1104 kickoffs, 0 `pdone_timeout`, 0 `frame_done_timeout`, 0 kickoff resets |
| 5 cycles with fbcon unbound | same per-cycle DRM message, 0 timeouts |
| Cold boots with the recovery cycle executed (`panel id: 00 00 00` → cycle 1 → `80 00 04`) | no DRM error; **one stall reproduced** (see below) |
| 30 backlight-only screen toggles (test 180) | 0 DPU/vblank/workqueue/RCU errors |

## What four reproductions showed (tests 181 and 182)

Four cold boots stalled, all of them starting in the same **~13.3-14.3 s
window after boot** (the deferred-probe / late-init burst).  Three wedged a CPU;
one broke the DPU first and took the machine down through the display path.

| | stall 1 | stall 2 | stall 3 (PCIe0 off) | stall 4 (PCIe0 off) |
|---|---|---|---|---|
| NMI-unresponsive CPU | 5 | 7 | 5 | (RCU stall reported) |
| last normal log | PCIe probe 14.05 s | PCIe probe 14.05 s | sync_state dump 13.54 s | DPU overflow 13.263 s |
| `pm_runtime_work` stuck | 4 | 3 | 3 | - |
| other stuck work | `fqdir_free_fn` | `toggle_allocation_gate` | `fqdir_free_fn`, `pogo_watch_work` | `drm_fb_helper_damage_work` pending |

A fifth experiment (test 182) disabled the PCIe0 controller on the theory that
the host-bridge probe was the trigger; the stall came back unchanged with no
PCIe code running at all, so that theory is dead — the probe had only been the
last thing that logged before the quiet window.

### The DPU chain, from a full `trace_pipe` capture

The streaming recorder (`gts9-dpu-stream.sh`) captured 4.7 MB / 48,864 lines
for the stall-4 boot.  Read against `dpu_crtc.c`:

```text
[    5.284091] last dpu_crtc_frame_event_done        (frame_pending reached 0)
[   13.262979] crtc103 event 1 overflow              <- first dropped frame event
[  109.852601] dpu_enc_kickoff                       <- last kickoff
[  109.867301] dpu_enc_frame_done_cb + crtc frame event (last completed frame)
[  109.87 ...] no kickoff, no frame-done, no crtc frame event
[  172.6  ...] irq=186 msm-kms + dpu_crtc_vblank_cb every ~8 ms, to the end
```

- `dpu_crtc_frame_event_cb()` takes an entry from a fixed-size
  `frame_event_list` and queues it on the CRTC's kthread worker; with no entry
  free it **drops** the event and logs the rate-limited `overflow` message.
- `dpu_crtc_frame_event_work()` decrements `frame_pending` and, for a DONE
  event, `complete_all(&dpu_crtc->frame_done_comp)` — the completion the commit
  path waits on.
- Dropping a DONE event therefore loses that completion: the next commit waits
  forever, `drm_fb_helper_damage_work` stops draining, and the workqueue/RCU
  reports follow.  The vblank IRQs never stop, which is why the panel keeps the
  last frame instead of going dark.

Counts over that boot: kickoff 65, frame-done 66, crtc frame event 66,
`frame_event_done` 29, `frame_event_more_pending` 0, `frame_done_timeout` 0,
`pdone_timeout` 0.

Still open: *why* the per-CRTC event kthread stops draining at ~13.3 s.  That is
the same window in which the other three stalls wedge a CPU, so the next hunt
should trace that thread's scheduling and the `deferred_probe_work_func` burst
rather than the display path.

## Reading a snapshot

```text
=== snapshot … uptime=… ===
--- trace tail ---            kickoff / frame-done / pdone-timeout / TE / IRQ entries
--- trace header ---          buffer size and the events that were armed
--- dmesg tail ---            DRM_ERROR lines and the panel ID
--- irq counts ---            msm-kms and dsi_isr counters at snapshot time
```

Captures are kept in `reference/boot-tests/test-181-20260924T011638Z/`.
