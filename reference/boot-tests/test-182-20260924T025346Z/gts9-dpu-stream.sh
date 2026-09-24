#!/bin/sh
# Stream the ftrace pipe to the microSD for the X710 stall hunt.
#
# The snapshot recorder (gts9-dpu-flight.sh) reads the whole ring every few
# seconds; each read formats the entire buffer, and the machine stalled before
# the second snapshot was ever written.  This one consumes trace_pipe as events
# happen, so the file already holds everything up to the moment of the stall.
#
#   gts9-dpu-stream.sh [output] [sync-seconds] [rotate-bytes]
set -u

OUT=${1:-/var/log/gts9-dpu-stream.txt}
SYNC_SECONDS=${2:-2}
ROTATE_BYTES=${3:-67108864}
PIPE=${GTS9_DPU_PIPE:-/sys/kernel/debug/tracing/trace_pipe}

# Keep the previous boot's stream (and its rotated chunk) for the stall case.
[ -f "$OUT.1" ] && mv -f "$OUT.1" "$OUT.1.prev"
[ -f "$OUT" ] && mv -f "$OUT" "$OUT.prev"

: > "$OUT"

(
	while :; do
		sleep "$SYNC_SECONDS"
		sync
		size=$(wc -c < "$OUT" 2>/dev/null || echo 0)
		if [ "$size" -gt "$ROTATE_BYTES" ]; then
			mv -f "$OUT" "$OUT.1" 2>/dev/null
			: > "$OUT"
		fi
	done
) &
SYNC_PID=$!

# cat blocks on trace_pipe until events arrive and writes them in order.
cat "$PIPE" >> "$OUT"
kill "$SYNC_PID" 2>/dev/null
exit 0
