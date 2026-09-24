#!/bin/sh
# Arm the X710 DPU/DRM tracepoints.  No kernel change is needed: the msm
# driver already defines the dpu_* events, including the exact failure
# markers this investigation needs (dpu_enc_frame_done_timeout,
# dpu_enc_wait_event_timeout) and the kickoff/vblank/frame-done events that
# answer "where did the pipeline stop".
#
#   gts9-dpu-trace-arm.sh          # arm
#   gts9-dpu-trace-arm.sh stop     # disarm
set -u

T=${GTS9_TRACE_ROOT:-/sys/kernel/debug/tracing}
EVENTS="
sched:sched_switch
sched:sched_wakeup
workqueue:workqueue_queue_work
workqueue:workqueue_execute_start
power:device_pm_callback_start
power:device_pm_callback_end
dpu:dpu_enc_kickoff
dpu:dpu_enc_prepare_kickoff
dpu:dpu_enc_enable
dpu:dpu_enc_disable
dpu:dpu_enc_mode_set
dpu:dpu_enc_frame_done_cb
dpu:dpu_enc_frame_done_cb_not_busy
dpu:dpu_enc_frame_done_timeout
dpu:dpu_enc_irq_wait_success
dpu:dpu_enc_wait_event_timeout
dpu:dpu_enc_trigger_start
dpu:dpu_enc_trigger_flush
dpu:dpu_enc_phys_cmd_connect_te
dpu:dpu_enc_underrun_cb
dpu:dpu_enc_vblank_cb
dpu:dpu_crtc_frame_event_cb
dpu:dpu_crtc_frame_event_done
dpu:dpu_enc_phys_cmd_irq_enable
dpu:dpu_enc_phys_cmd_irq_disable
dpu:dpu_enc_phys_cmd_pp_tx_done
dpu:dpu_enc_phys_cmd_pdone_timeout
dpu:dpu_crtc_vblank
dpu:dpu_crtc_vblank_cb
dpu:dpu_crtc_complete_commit
dpu:dpu_crtc_complete_flip
dpu:dpu_crtc_enable
dpu:dpu_crtc_disable
dpu:dpu_kms_commit
dpu:dpu_kms_wait_for_commit_done
drm:drm_vblank_event
drm:drm_vblank_event_delivered
drm:drm_vblank_event_queued
"

echo 0 > "$T/tracing_on"
echo > "$T/trace"
# 16 MiB so the ring still holds the seconds before a stall.
echo 16384 > "$T/buffer_size_kb" 2>/dev/null || true

armed=0
for e in $EVENTS; do
	f="$T/events/$(echo "$e" | tr ':' '/')/enable"
	if [ -w "$f" ]; then
		echo 1 > "$f" 2>/dev/null && armed=$((armed + 1))
	fi
done

# Raw IRQ counts stay useful but only for the two display lines.
if [ -w "$T/events/irq/irq_handler_entry/filter" ]; then
	echo 'irq==186 || irq==187' > "$T/events/irq/irq_handler_entry/filter"
	echo 1 > "$T/events/irq/irq_handler_entry/enable" 2>/dev/null
fi

# The frame-event workers are SCHED_FIFO kthreads named crtc_event:<id>; the
# sched events are filtered to them so a stall shows when they stop running.
if [ -w "$T/events/sched/sched_switch/filter" ]; then
	echo 'prev_comm ~ "crtc_event*" || next_comm ~ "crtc_event*"' > "$T/events/sched/sched_switch/filter" 2>/dev/null
	echo 'comm ~ "crtc_event*"' > "$T/events/sched/sched_wakeup/filter" 2>/dev/null
fi

# The lockup detectors are off because the vendor command line carries
# nowatchdog; turn the soft one back on so a spinning CPU can still print a
# stack before the machine becomes unreadable.
[ -w /proc/sys/kernel/watchdog ] && echo 1 > /proc/sys/kernel/watchdog 2>/dev/null

echo 1 > "$T/tracing_on"
printf 'gts9-dpu-trace: %s events armed, tracing_on=%s, buffer=%s kB\n' \
	"$armed" "$(cat "$T/tracing_on")" "$(cat "$T/buffer_size_kb")"

if [ "${1:-}" = stop ]; then
	echo 0 > "$T/tracing_on"
	echo 'gts9-dpu-trace: tracing off'
fi
