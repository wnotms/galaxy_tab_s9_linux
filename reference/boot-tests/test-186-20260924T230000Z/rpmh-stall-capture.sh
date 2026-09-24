#!/usr/bin/env bash
# test-186: capture one real 13-14 s stall with the RPMh timeout diagnostic on.
#
# Profile (the only new variable versus test-184 profile A is the diagnostic):
#
#	gts9_watchdog_debug=1     detectors armed
#	gts9_rpmh_debug=1         RPMh timeout dump (0021 patch, default-off)
#	console=ttyGS1            kernel console captured on COM19
#	gts9_kmsg_mirror          OFF
#	gts9_dpu_flight           OFF
#	Pogo / PCIe / regulators / PMIC / panel-recovery timing: untouched
#
# Why the console port is enough: the RPMh dump is printed by
# rpmh_write_batch() *before* anything panics, while the system still schedules,
# so unlike a panic report it does reach the host.  The watchdog may still panic
# later; the capture then also shows the reboot and the next boot.
#
# SAFETY: no flashing, no partition or BCB writes.  Boots are issued as
# `systemctl reboot` over the shell console and only with
# GTS9_ALLOW_POWER=1; otherwise the script runs the preflight and exits.
#
#   reference/boot-tests/test-186-*/rpmh-stall-capture.sh 5
#   GTS9_ALLOW_POWER=1 reference/boot-tests/test-186-*/rpmh-stall-capture.sh 5
set -uo pipefail

REPO=/home/ms/Samsung/galaxy_tab_s9_linux
D=$(cd "$(dirname "$0")" && pwd)
OUT=$D/rpmh-capture.txt
ROUNDS_DIR=$D/rounds
CR=$REPO/scripts/console-run.ps1
CW=$REPO/scripts/console-watch.ps1
PS=powershell.exe
N=${1:-5}
SHELL_PORT=${GTS9_SHELL_PORT:-COM17}
CONSOLE_PORT=${GTS9_CONSOLE_PORT:-COM19}
ALLOW=${GTS9_ALLOW_POWER:-0}
WINDOW=${GTS9_WINDOW:-150}
WINROOT='C:\gts9-work\test186'
WINLOCAL=/mnt/c/gts9-work/test186

mkdir -p "$ROUNDS_DIR" "$WINLOCAL"

say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$OUT"; }
field() { grep -a -m1 -- "$2" "$1" 2>/dev/null | sed "s/.*$2//" | tr -d '\r'; }
count() { local n; n=$(grep -a -c -E "$1" "$2" 2>/dev/null); printf '%s' "${n:-0}"; }

preflight() {
	local out=$ROUNDS_DIR/preflight.txt raw=$ROUNDS_DIR/preflight-raw.txt
	timeout 300 "$PS" -NoProfile -ExecutionPolicy Bypass -File "$CR" \
		-Out "$WINROOT\\preflight.log" -Port "$SHELL_PORT" \
		-WaitReadySeconds 150 -ReadSeconds 25 \
		-Commands 'echo PF;BID=$(cat /proc/sys/kernel/random/boot_id);echo boot_id=$BID;cut -d" " -f1 /proc/uptime;echo rpmh_debug=$(cat /proc/cmdline | tr " " "\n" | grep -c "gts9_rpmh_debug=1");echo heavy=$(cat /proc/cmdline | tr " " "\n" | grep -c -E "gts9_kmsg_mirror|gts9_dpu_flight");echo wd=$(cat /proc/sys/kernel/watchdog) slp=$(cat /proc/sys/kernel/softlockup_panic) htp=$(cat /proc/sys/kernel/hung_task_panic) wq=$(cat /sys/module/workqueue/parameters/panic_on_stall_time);echo flight=$(systemctl is-active gts9-dpu-flight.service) mirror=$(systemctl is-active gts9-kmsg-console.service);echo console=$(cat /sys/class/tty/console/active);echo failed=$(systemctl --failed --no-pager --plain | grep -c "loaded failed")' \
		>"$raw" 2>&1
	grep -aE "RECV  (PF|boot_id=|rpmh_debug=|heavy=|wd=|flight=|console=|failed=|[0-9]+\.[0-9]+)|shell never answered|could not open" "$raw" >"$out"
	cat "$out"
}

probe() {
	local tag=$1 out=$ROUNDS_DIR/probe-$tag.txt raw=$ROUNDS_DIR/probe-$tag-raw.txt
	timeout 400 "$PS" -NoProfile -ExecutionPolicy Bypass -File "$CR" \
		-Out "$WINROOT\\probe-$tag.log" -Port "$SHELL_PORT" \
		-WaitReadySeconds 240 -ReadSeconds 30 \
		-Commands 'echo PB;echo boot_id=$(cat /proc/sys/kernel/random/boot_id);cut -d" " -f1 /proc/uptime;echo "--- prev boot rpmh/anomaly lines";journalctl -b -1 -k -o short-monotonic --no-pager 2>/dev/null | grep -a -E "gts9-rpmh|soft lockup|workqueue: .*stall|rcu:.*detected stall|frame done timeout|mmc.*[Tt]imeout|rpmh_write_batch" | head -60;echo "--- prev boot tail";journalctl -b -1 -o short-monotonic --no-pager 2>/dev/null | tail -6' \
		>"$raw" 2>&1
	grep -aE "RECV  (PB|boot_id=|[0-9]+\.[0-9]+|--- |\[ *[0-9]+\.|gts9-rpmh)|shell never answered|could not open" "$raw" >"$out"
	cat "$out"
}

# first_anomaly LOG - earliest monotonic timestamp among the known signatures.
first_anomaly() {
	local log=$1 name ts best="" bestname="none"
	for name in "gts9-rpmh: TIMEOUT" "soft lockup" "workqueue: .*stall" "rcu:.*detected stall" "frame done timeout" "mmc.*[Tt]imeout"; do
		ts=$(grep -a -m1 -E "$name" "$log" 2>/dev/null | grep -a -o -E "^\[ *[0-9]+\.[0-9]+\]" | tr -dc '0-9.')
		[ -n "$ts" ] || continue
		if [ -z "$best" ] || [ "$(printf '%s\n%s\n' "$ts" "$best" | sort -g | head -1)" = "$ts" ]; then
			best=$ts
			bestname=$name
		fi
	done
	printf '%s at %s' "$bestname" "${best:-n/a}"
}

say "test-186 RPMh stall capture: rounds=$N allow_power=$ALLOW window=${WINDOW}s"

pre=$(preflight)
printf '%s\n' "$pre" | grep -aE "boot_id=|rpmh_debug=|heavy=|wd=|flight=|console=|failed=" | sed 's/^/  /' | tee -a "$OUT"
grep -aq "rpmh_debug=1" "$ROUNDS_DIR/preflight.txt" || say "WARNING: gts9_rpmh_debug=1 is not on the command line; the diagnostic is inert"
grep -aq "heavy=0" "$ROUNDS_DIR/preflight.txt" || say "WARNING: heavy instrumentation still on the command line"

if [ "$ALLOW" != "1" ]; then
	say "dry run: set GTS9_ALLOW_POWER=1 to actually boot the tablet"
	say "would run $N rounds: reboot on $SHELL_PORT, capture $CONSOLE_PORT for ${WINDOW}s, then read journal -b -1"
	exit 0
fi

boot_id=$(field "$ROUNDS_DIR/preflight.txt" 'boot_id=')
[ -n "$boot_id" ] || { say "FATAL: no shell on $SHELL_PORT"; exit 1; }

for i in $(seq 1 "$N"); do
	say "=== round $i (boot_id before=$boot_id) ==="
	# Console capture spans the shutdown, the boot and the 13-14 s window.
	timeout $((WINDOW + 200)) "$PS" -NoProfile -ExecutionPolicy Bypass -File "$CW" \
		-Out "$WINROOT\\console-$i.log" -Seconds "$WINDOW" -Port "$CONSOLE_PORT" \
		>"$ROUNDS_DIR/console-$i-watch.txt" 2>&1 &
	conpid=$!
	sleep 2
	timeout 300 "$PS" -NoProfile -ExecutionPolicy Bypass -File "$CW" \
		-Out "$WINROOT\\shell-$i.log" -Seconds 60 -Port "$SHELL_PORT" \
		-Command 'systemctl reboot' -CommandAtSeconds 6 \
		2>&1 | grep -aE "SENT|PRESENCE usb" | tail -3 | tee -a "$OUT"
	wait "$conpid" 2>/dev/null || true

	klog=$ROUNDS_DIR/console-$i.log
	cp "$WINLOCAL/console-$i.log" "$klog" 2>/dev/null || say "WARNING: no console capture for round $i"

	# The RPMh dump block, if any.
	grep -a -n -A40 "gts9-rpmh: TIMEOUT" "$klog" 2>/dev/null | head -60 >"$ROUNDS_DIR/round-$i-rpmh-dump.txt"

	txt=$(probe "$i")
	printf '%s\n' "$txt" | grep -aE "boot_id=|gts9-rpmh|lockup|stall|timeout" | head -12 | sed 's/^/  /' | tee -a "$OUT"
	new_id=$(field "$ROUNDS_DIR/probe-$i.txt" 'boot_id=')

	verdict=not-reproduced
	grep -aq "gts9-rpmh: TIMEOUT" "$klog" 2>/dev/null && verdict=rpmh-timeout-captured
	grep -aq "soft lockup" "$klog" 2>/dev/null && verdict=${verdict}-plus-soft-lockup

	{
		echo "round=$i"
		echo "boot_id_before=$boot_id"
		echo "boot_id_after=${new_id:-none}"
		echo "first_anomaly=$(first_anomaly "$klog")"
		echo "rpmh_timeouts=$(count 'gts9-rpmh: TIMEOUT' "$klog")"
		echo "rpmh_late_completions=$(count 'gts9-rpmh: LATE COMPLETION' "$klog")"
		echo "ring_summary=$(grep -a -m1 'gts9-rpmh: ring_summary' "$klog" 2>/dev/null)"
		echo "holder_line=$(grep -a -m1 'gts9-rpmh: holder_tcs' "$klog" 2>/dev/null)"
		echo "irq_line=$(grep -a -m1 'gts9-rpmh: irq_status' "$klog" 2>/dev/null)"
		echo "soft_lockups=$(count 'soft lockup' "$klog")"
		echo "dpu_timeouts=$(count 'frame done timeout' "$klog")"
		echo "mmc_timeouts=$(count 'mmc.*[Tt]imeout' "$klog")"
		echo "console_log=$klog"
		echo "verdict=$verdict"
	} >"$ROUNDS_DIR/round-$i.txt"
	grep -aE "first_anomaly|rpmh_timeouts|verdict|ring_summary|holder_line|irq_line" "$ROUNDS_DIR/round-$i.txt" | sed 's/^/  /' | tee -a "$OUT"

	[ -n "$new_id" ] && boot_id=$new_id
	if grep -aq "shell never answered" "$ROUNDS_DIR/probe-$i-raw.txt" 2>/dev/null; then
		say "round $i: the tablet did not come back; stopping (operator action needed)"
		break
	fi
done

say "test-186 done: $(grep -a -h '^verdict=' "$ROUNDS_DIR"/round-*.txt 2>/dev/null | sort | uniq -c | tr '\n' ' ')"
