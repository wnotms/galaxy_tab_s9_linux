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

## The one reproduction: a CPU wedge, not a frame-done timeout

A cold boot during the hunt recovered the panel normally and then stalled: the
console echoed but stopped executing, the panel kept a stuck cursor, the Pogo
keyboard was dead, and only a ~15 s PMIC hold recovered the tablet (`nowatchdog`
means nothing else will).  The kernel reported:

```text
rcu: INFO: rcu_preempt detected stalls on CPUs/tasks:
rcu:     5-...0: (0 ticks this GP) …
After 10 seconds, these CPUS still haven't responded to the NMI: 5
BUG: workqueue lockup - pool cpus=1 … stuck for 56s!
    in-flight: 27:fqdir_free_fn for 56s
workqueue pm: in-flight: 75:pm_runtime_work for 56s (and three more)
workqueue events: pending: drm_fb_helper_damage_work
```

Two things follow for this investigation:

- The primary event is a **CPU that stops answering NMIs**.  The stuck work
  items span unrelated subsystems (`fqdir_free_fn`, `pm_runtime_work`, with the
  DRM damage worker merely *pending*), which is what a global stall looks like.
- In this instance there is **no** `frame done timeout` and **no** `vblank wait
  timed out`, so the DPU path is not proven to be the trigger — it may be a
  victim of the same wedge.  Test 178's `enc35 frame done timeout` and this
  stall share the symptom, not necessarily the cause.

The last normal log line before the wedge was deferred-probe completion (PCIe
host bridge) at 14.3 s; the stall was detected at 36.3 s, so the trigger sits in
that quiet interval.  The recorder now preserves the previous boot's snapshot as
`/var/log/gts9-dpu-flight.txt.prev`, so the next occurrence keeps its trace
instead of only its journal.

## Reading a snapshot

```text
=== snapshot … uptime=… ===
--- trace tail ---            kickoff / frame-done / pdone-timeout / TE / IRQ entries
--- trace header ---          buffer size and the events that were armed
--- dmesg tail ---            DRM_ERROR lines and the panel ID
--- irq counts ---            msm-kms and dsi_isr counters at snapshot time
```

Captures are kept in `reference/boot-tests/test-181-20260924T011638Z/`.
