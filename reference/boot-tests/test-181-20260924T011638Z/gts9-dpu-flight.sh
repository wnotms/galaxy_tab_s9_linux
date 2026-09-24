#!/bin/sh
# DPU flight recorder for the X710.
#
# The intermittent failure this exists for leaves the tablet unable to run
# commands at all (workqueue lockup / RCU stall), so the interesting trace is
# not readable afterwards from the machine that produced it.  This loop
# snapshots the ftrace buffer and the kernel log tail to the microSD every few
# seconds; after a forced restart the last snapshot is still on disk.
#
#   gts9-dpu-flight.sh [output] [interval-seconds]
#
# Stop it by removing /run/gts9-dpu-flight.on (or killing the loop).
set -u

OUT=${1:-/var/log/gts9-dpu-flight.txt}
INTERVAL=${2:-3}
TRACE=${GTS9_DPU_TRACE:-/sys/kernel/debug/tracing/trace}
LINES=${GTS9_DPU_TRACE_LINES:-500}
DMESG_LINES=${GTS9_DPU_DMESG_LINES:-80}
FLAG=${GTS9_DPU_FLAG:-/run/gts9-dpu-flight.on}
COUNT=0

: > "$FLAG"
while [ -f "$FLAG" ]; do
	COUNT=$((COUNT + 1))
	{
		printf '=== snapshot %s uptime=%s ===\n' \
			"$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$(cut -d' ' -f1 /proc/uptime)"
		printf '--- trace tail ---\n'
		tail -n "$LINES" "$TRACE" 2>/dev/null
		printf '--- trace header ---\n'
		head -n 6 "$TRACE" 2>/dev/null
		printf '--- dmesg tail ---\n'
		dmesg 2>/dev/null | tail -n "$DMESG_LINES"
		printf '--- irq counts ---\n'
		grep -aE 'msm-kms|dsi_isr' /proc/interrupts 2>/dev/null
		printf '=== end snapshot %s ===\n' "$COUNT"
	} > "$OUT.tmp" 2>/dev/null
	sync
	mv -f "$OUT.tmp" "$OUT" 2>/dev/null
	sleep "$INTERVAL"
done
rm -f "$FLAG"
exit 0
