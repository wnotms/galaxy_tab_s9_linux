#!/usr/bin/env bash
# test-183: unattended X710 stall -> panic -> reboot -> evidence rounds.
#
# One round is:
#
#	boot -> arm -> (stall) -> software watchdog -> panic -> panic=10 reboot
#	     -> next boot collects the previous boot's evidence -> repeat
#
# The loop never touches the tablet.  It listens on COM17 (the same cable that
# carries the console, the userspace log and, through gts9-kmsg-console, the
# live kernel log), classifies what it saw, and then reads the evidence
# directory the tablet builds for itself at the next boot.  A round counts as a
# recovery when the tablet's boot_id changed without anyone issuing a reboot:
# that is the condition that used to require a 15-30 s power hold.
#
# Requirements on the tablet side (installed by the test-183 record):
#
#   * boot/cmdline.watchdog-debug.example.txt on vendor_boot:
#     panic=10 softlockup_panic=1 workqueue.panic_on_stall_time=45
#     gts9_watchdog_debug=1
#   * gts9-watchdog-debug.service      - arms the software detectors
#   * gts9-prev-boot-evidence.service  - archives the previous boot every boot
#   * gts9-kmsg-console.service        - mirrors /dev/kmsg onto the console
#   * gts9-dpu-flight.service          - the DPU trace stream (the stall bait)
#
#   reference/boot-tests/test-183-*/gts9-stall-loop.sh [rounds] [window-seconds]
set -uo pipefail

REPO=/home/ms/Samsung/galaxy_tab_s9_linux
D=$(cd "$(dirname "$0")" && pwd)
OUT=$D/stall-loop.txt
ROUNDS_DIR=$D/rounds
CR=$REPO/scripts/console-run.ps1
CW=$REPO/scripts/console-watch.ps1
PS=powershell.exe
N=${1:-6}
WINDOW=${2:-180}
WINROOT='C:\gts9-work\test183'
WINLOCAL=/mnt/c/gts9-work/test183

mkdir -p "$ROUNDS_DIR" "$WINLOCAL"

say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$OUT"; }

# count PATTERN FILE - always exactly one number, never two.
count() {
	local n
	n=$(grep -a -c -E "$1" "$2" 2>/dev/null)
	printf '%s' "${n:-0}"
}

# classify LOG ROUND
# Reads the console capture, writes round-N.txt, prints the interesting lines.
classify() {
	local log=$1
	local round=$2
	local out=$ROUNDS_DIR/round-$round.txt
	{
		echo "round=$round"
		echo "captured_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
		echo "console_log=$log"
		echo "marker_boot=$(count 'Booting Linux on physical CPU' "$log")"
		echo "marker_soft_lockup=$(count 'BUG: soft lockup' "$log")"
		echo "marker_soft_lockup_report=$(count 'watchdog: BUG: soft lockup' "$log")"
		echo "marker_panic=$(count 'Kernel panic' "$log")"
		echo "marker_wq_stall=$(count 'workqueue: .*stall' "$log")"
		echo "marker_wq_panic=$(count 'workqueue: .*exceed' "$log")"
		echo "marker_hung_task=$(count 'hung_task: blocked tasks' "$log")"
		echo "marker_rcu_stall=$(count 'rcu:.*detected stall' "$log")"
		echo "marker_dpu_timeout=$(count 'frame done timeout' "$log")"
		echo "marker_rpmh_warn=$(count 'rpmh_write_batch' "$log")"
		echo "marker_restart=$(count 'reboot: Restarting system|Rebooting in' "$log")"
		echo "marker_usb_gap=$(count 'PRESENCE usb' "$log")"
		echo "watchdog_report=$(grep -a -m1 'watchdog: BUG' "$log" 2>/dev/null)"
		echo "wq_line=$(grep -a -m1 'workqueue: .*stall' "$log" 2>/dev/null)"
		echo "panic_line=$(grep -a -m1 'Kernel panic' "$log" 2>/dev/null)"
		echo "rpmh_line=$(grep -a -m1 'rpmh_write_batch' "$log" 2>/dev/null)"
		echo "evidence_line=$(grep -a -m1 'gts9-prev-boot-evidence:' "$log" 2>/dev/null)"
	} >"$out" 2>&1
	cat "$out"
}

# device_probe ROUND
# The tablet-side view: profile, evidence directory, verdict.  The console is
# released for a moment first - the watcher has just closed it and COM17 is not
# always free instantly.  The raw console-run output is kept, because "could
# not open" and "shell never answered" are results too.
device_probe() {
	local round=$1
	local out=$ROUNDS_DIR/round-$round-device.txt
	local raw=$ROUNDS_DIR/round-$round-probe-raw.txt
	sleep 6
	timeout 420 "$PS" -NoProfile -ExecutionPolicy Bypass -File "$CR" \
		-Out "C:\\gts9-work\\test183\\round-$round-probe.log" \
		-WaitReadySeconds 180 -ReadSeconds 25 \
		-Commands 'echo PROBE;echo boot_id=$(cat /proc/sys/kernel/random/boot_id);echo chunk=$(date -u +%Y-%m-%dT%H:%M:%SZ);cut -d" " -f1 /proc/uptime;echo running=$(systemctl is-system-running);echo flight=$(systemctl is-active gts9-dpu-flight.service);echo wd=$(cat /proc/sys/kernel/watchdog) slp=$(cat /proc/sys/kernel/softlockup_panic) htp=$(cat /proc/sys/kernel/hung_task_panic);echo wq=$(cat /sys/module/workqueue/parameters/panic_on_stall_time);echo pstore=$(ls /sys/fs/pstore/ 2>/dev/null | tr "\n" " ");BID=$(cat /proc/sys/kernel/random/boot_id);D=$(ls -1d /var/log/gts9-boot-evidence/*-$(echo $BID | cut -c1-8)/ 2>/dev/null | head -1);echo "--- $D";cat "$D/verdict.txt" 2>/dev/null | head -22;echo ---failed;systemctl --failed --no-pager --plain | head -4' \
		>"$raw" 2>&1
	grep -aE "RECV  (PROBE|boot_id=|chunk=|[0-9]+\.[0-9]+|running=|flight=|wd=|wq=|pstore=|---|collected_utc=|previous_boot=|prev_kernel_lines=|marker_|pstore_|watchdog_|softlockup_panic=|hung_task_panic=|wq_panic)|shell never answered|could not open|console run done" "$raw" >"$out"
	cat "$out"
}

field() { grep -a -m1 -- "$2" "$1" 2>/dev/null | sed "s/.*$2//" | tr -d '\r'; }

say "test-183 stall loop: rounds=$N window=${WINDOW}s"

# The profile has to be armed on the tablet before anything can reboot itself.
# COM17 is a shared resource: a previous watcher can still be letting go of it,
# so the preflight is retried instead of declaring the tablet dead.
boot_id=""
for attempt in 1 2 3; do
	pre=$(device_probe preflight)
	printf '%s\n' "$pre" | grep -aE "boot_id=|running=|wd=|shell never answered|could not open" | tee -a "$OUT"
	boot_id=$(field "$ROUNDS_DIR/round-preflight-device.txt" 'boot_id=')
	say "preflight attempt $attempt: boot_id=${boot_id:-unknown}"
	[ -n "$boot_id" ] && break
	say "preflight: no answer, waiting 20 s for the port"
	sleep 20
done
if [ -z "$boot_id" ]; then
	say "FATAL: the tablet is not answering on COM17; not starting a loop"
	exit 1
fi
say "preflight armed: boot_id=$boot_id"

recoveries=0
stalls=0
for i in $(seq 1 "$N"); do
	say "=== round $i: boot + ${WINDOW}s observation ==="
	# The round *is* a boot: every recorded stall began 13-36 s after one, so
	# the reboot is issued first and the same capture covers the shutdown, the
	# boot, the stall window and (with the profile armed) the panic reboot that
	# follows it.  Nothing is sent after the reboot, so a stalled tablet is
	# never touched while it recovers.
	timeout $((WINDOW + 150)) "$PS" -NoProfile -ExecutionPolicy Bypass -File "$CW" \
		-Out "$WINROOT\\round-$i.log" -Seconds "$WINDOW" \
		-Command 'systemctl reboot' -CommandAtSeconds 8 \
		2>&1 | grep -aE "SENT|PRESENCE usb|watch done" | tail -6 | tee -a "$OUT"

	log=$ROUNDS_DIR/round-$i-console.log
	cp "$WINLOCAL/round-$i.log" "$log" 2>/dev/null || say "WARNING: no console capture for round $i"

	classify "$log" "$i" >/dev/null
	grep -aE "marker_|_line=" "$ROUNDS_DIR/round-$i.txt" | grep -avE "=0$|=$" | sed 's/^/  /' | tee -a "$OUT"

	probe=$(device_probe "$i")
	printf '%s\n' "$probe" | grep -aE "boot_id=|running=|wd=|previous_boot=|previous_boot_end=|pstore_panic_lines=|marker_panic=|marker_soft_lockup=|shell never answered|could not open|probe=" | sed 's/^/  /' | tee -a "$OUT"

	new_id=$(field "$ROUNDS_DIR/round-$i-device.txt" 'boot_id=')
	{
		echo "boot_id_before=$boot_id"
		echo "boot_id_after=${new_id:-unknown}"
	} >>"$ROUNDS_DIR/round-$i.txt"

	if grep -aqE "marker_soft_lockup_report=[1-9]|marker_wq_stall=[1-9]|marker_panic=[1-9]|marker_hung_task=[1-9]|marker_rpmh_warn=[1-9]" "$ROUNDS_DIR/round-$i.txt"; then
		stalls=$((stalls + 1))
		echo "stall_signature=yes" >>"$ROUNDS_DIR/round-$i.txt"
		say "round $i: STALL SIGNATURE in the capture"
	else
		echo "stall_signature=no" >>"$ROUNDS_DIR/round-$i.txt"
	fi

	# The round starts with its own reboot, so a changed boot_id on its own
	# proves nothing.  What distinguishes an unattended recovery is a stall
	# signature in the capture (or a previous boot the tablet ended without a
	# clean shutdown) *plus* a new boot_id.
	prev_end=$(field "$ROUNDS_DIR/round-$i-device.txt" 'previous_boot_end=')
	if [ -n "$new_id" ] && [ "$new_id" != "$boot_id" ]; then
		echo "reboot=yes" >>"$ROUNDS_DIR/round-$i.txt"
		echo "previous_boot_end=${prev_end:-unknown}" >>"$ROUNDS_DIR/round-$i.txt"
		if grep -aqE "marker_soft_lockup_report=[1-9]|marker_wq_stall=[1-9]|marker_panic=[1-9]|marker_hung_task=[1-9]|marker_rpmh_warn=[1-9]" "$ROUNDS_DIR/round-$i.txt" ||
			[ "$prev_end" = "hard-reset-or-incomplete" ] || [ "$prev_end" = "panic" ]; then
			recoveries=$((recoveries + 1))
			echo "auto_recovery=yes" >>"$ROUNDS_DIR/round-$i.txt"
			say "round $i: UNATTENDED RECOVERY #$recoveries (stall signature / previous boot did not shut down cleanly)"
		else
			echo "auto_recovery=no-clean-kick" >>"$ROUNDS_DIR/round-$i.txt"
			say "round $i: the boot_id change is this round's own reboot (clean round)"
		fi
		boot_id=$new_id
	else
		echo "reboot=no" >>"$ROUNDS_DIR/round-$i.txt"
		say "round $i: boot_id unchanged"
		if grep -aqE "shell never answered|could not open" "$ROUNDS_DIR/round-$i-device.txt"; then
			say "round $i: NO AUTO-REBOOT - the tablet is stuck and needs a manual power hold; stopping"
			break
		fi
	fi
done

say "stall loop done: rounds=$N stalls_seen=$stalls auto_recoveries=$recoveries"
{
	echo "rounds=$N"
	echo "window_seconds=$WINDOW"
	echo "stalls_seen=$stalls"
	echo "auto_recoveries=$recoveries"
} >"$D/stall-loop-summary.txt"
cat "$D/stall-loop-summary.txt"
