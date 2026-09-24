#!/usr/bin/env bash
# test-184: observer-effect A/B for the X710 stall hunt.
#
# The three instrumentation pieces are independent switches now:
#
#	A  watchdog detectors only            gts9_watchdog_debug=1
#	B  + kernel-log mirror                gts9_kmsg_mirror=1
#	C  + DPU ftrace stream                gts9_dpu_flight=1
#	D  all three
#
# This runner reboots the tablet, then reads back what that boot cost and what
# it saw:
#
#	the watchdog helper's real start->exit time (ms)
#	the helper's one-line summary
#	whether the ACM console getty came up by itself
#	stall / panic / rpmh markers in the journal
#
# It uses the shell port for the reboot and the kernel console port to capture
# whatever the boot prints.  Warm resets are labelled as such: a real cold boot
# needs the operator, and the early-deferred-probe window this project cares
# about is not the same thing.
#
#   reference/boot-tests/test-184-*/observer-ab.sh [rounds] [profile-label]
set -uo pipefail

REPO=/home/ms/Samsung/galaxy_tab_s9_linux
D=$(cd "$(dirname "$0")" && pwd)
OUT=$D/observer-ab.txt
ROUNDS_DIR=$D/rounds
CR=$REPO/scripts/console-run.ps1
CW=$REPO/scripts/console-watch.ps1
PS=powershell.exe
N=${1:-5}
LABEL=${2:-A}
SHELL_PORT=${GTS9_SHELL_PORT:-COM17}
CONSOLE_PORT=${GTS9_CONSOLE_PORT:-COM19}
WINROOT='C:\gts9-work\test184'
WINLOCAL=/mnt/c/gts9-work/test184

mkdir -p "$ROUNDS_DIR" "$WINLOCAL"

say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$OUT"; }
field() { grep -a -m1 -- "$2" "$1" 2>/dev/null | sed "s/.*$2//" | tr -d '\r'; }
count() { local n; n=$(grep -a -c -E "$1" "$2" 2>/dev/null); printf '%s' "${n:-0}"; }

probe() {
	local tag=$1
	local out=$ROUNDS_DIR/probe-$tag.txt
	local raw=$ROUNDS_DIR/probe-$tag-raw.txt
	timeout 300 "$PS" -NoProfile -ExecutionPolicy Bypass -File "$CR" \
		-Out "C:\\gts9-work\\test184\\probe-$tag.log" -Port "$SHELL_PORT" \
		-WaitReadySeconds 180 -ReadSeconds 22 \
		-Commands 'echo AB;BID=$(cat /proc/sys/kernel/random/boot_id);echo boot_id=$BID;echo uptime=$(cut -d" " -f1 /proc/uptime);echo getty=$(systemctl is-active gts9-acm-getty.service);echo msm0=$(systemctl is-enabled serial-getty@ttyMSM0.service 2>&1);echo failed=$(systemctl --failed --no-pager --plain | grep -c "loaded failed");systemctl show gts9-watchdog-debug -p Result -p ExecMainStartTimestampMonotonic -p ExecMainExitTimestampMonotonic | tr "\n" " ";echo;journalctl -b -o short-monotonic --no-pager 2>/dev/null | grep -a "gts9-watchdog-debug:" | head -1;journalctl -b -k -o short-monotonic --no-pager 2>/dev/null | grep -a -c -E "soft lockup|hung_task|workqueue: stall|Kernel panic|rpmh_write_batch|frame done timeout"' \
		>"$raw" 2>&1
	grep -aE "RECV  (AB|boot_id=|uptime=|getty=|msm0=|failed=|Result=|[0-9]+$|gts9-watchdog-debug:)|shell never answered|could not open" "$raw" >"$out"
	cat "$out"
}

say "test-184 observer A/B: rounds=$N profile=$LABEL"

for i in $(seq 1 "$N"); do
	say "=== round $i ($LABEL) ==="
	# Kernel console capture runs in parallel with the reboot command.
	timeout 200 "$PS" -NoProfile -ExecutionPolicy Bypass -File "$CW" \
		-Out "$WINROOT\\console-$LABEL-$i.log" -Seconds 60 -Port "$CONSOLE_PORT" \
		>"$ROUNDS_DIR/console-$LABEL-$i-watch.txt" 2>&1 &
	conpid=$!
	sleep 2
	timeout 200 "$PS" -NoProfile -ExecutionPolicy Bypass -File "$CW" \
		-Out "$WINROOT\\shell-$LABEL-$i.log" -Seconds 40 -Port "$SHELL_PORT" \
		-Command 'systemctl reboot' -CommandAtSeconds 6 \
		2>&1 | grep -aE "SENT|PRESENCE usb" | tail -2 | tee -a "$OUT"
	wait "$conpid" 2>/dev/null || true

	# Kernel log for this boot (captured live on the console port).
	klog=$ROUNDS_DIR/kernel-$LABEL-$i.log
	cp "$WINLOCAL/console-$LABEL-$i.log" "$klog" 2>/dev/null || true

	sleep 20
	txt=$(probe "$LABEL-$i")
	printf '%s\n' "$txt" | grep -aE "boot_id=|uptime=|getty=|msm0=|failed=|Result=|gts9-watchdog-debug:" | sed 's/^/  /' | tee -a "$OUT"

	{
		echo "round=$i"
		echo "profile=$LABEL"
		echo "boot_type=warm-reset"
		echo "boot_id=$(field "$ROUNDS_DIR/probe-$LABEL-$i.txt" 'boot_id=')"
		echo "helper_exit_ms=$(field "$ROUNDS_DIR/probe-$LABEL-$i.txt" 'ExecMainExitTimestampMonotonic=')"
		echo "helper_start_ms=$(field "$ROUNDS_DIR/probe-$LABEL-$i.txt" 'ExecMainStartTimestampMonotonic=')"
		echo "kernel_markers=$(grep -a -o -E '[0-9]+$' "$ROUNDS_DIR/probe-$LABEL-$i.txt" | tail -1)"
		echo "console_lines=$(count 'RECV' "$klog")"
		echo "console_stall_markers=$(count 'soft lockup|hung_task|workqueue: stall|Kernel panic|rpmh_write_batch|frame done timeout' "$klog")"
		echo "getty_timeout=$(count 'dev-ttyGS0.device|dev-ttyMSM0.device' "$klog")"
	} >"$ROUNDS_DIR/round-$LABEL-$i.txt"
	grep -aE "getty_timeout|console_stall_markers|boot_id=" "$ROUNDS_DIR/round-$LABEL-$i.txt" | sed 's/^/  /' | tee -a "$OUT"
done

say "observer A/B done: profile=$LABEL rounds=$N"
{
	echo "profile=$LABEL"
	echo "rounds=$N"
	echo "boot_type=warm-reset"
	echo "getty_timeouts=$(cat "$ROUNDS_DIR"/round-$LABEL-*.txt 2>/dev/null | grep -a '^getty_timeout=' | cut -d= -f2 | paste -sd+ | bc 2>/dev/null || echo 0)"
	echo "console_stall_markers=$(cat "$ROUNDS_DIR"/round-$LABEL-*.txt 2>/dev/null | grep -a '^console_stall_markers=' | cut -d= -f2 | paste -sd+ | bc 2>/dev/null || echo 0)"
} >"$D/observer-ab-$LABEL-summary.txt"
cat "$D/observer-ab-$LABEL-summary.txt"
