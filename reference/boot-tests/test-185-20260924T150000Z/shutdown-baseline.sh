#!/usr/bin/env bash
# test-185: shutdown / reboot baseline with the heavy instrumentation off.
#
# Question this answers: test-184 saw a ~3.5 minute shutdown while the DPU ftrace
# stream was writing megabytes per second to the microSD, and a stale
# /etc/systemd/system/gts9-dpu-flight.service meant the "off by default" flag was
# not actually in effect.  It is now.  Does the slow shutdown still happen?
#
# The profile under test is the current image with the watchdog detectors alone:
#
#	gts9_watchdog_debug=1     detectors armed
#	gts9_kmsg_mirror          must be OFF
#	gts9_dpu_flight           must be OFF
#	ttyGS0                    login shell
#	ttyGS1                    kernel console
#
# SAFETY: this script never flashes, never writes a partition, never touches the
# BCB.  It only sends `systemctl reboot` / `systemctl poweroff` over the console,
# and only when the operator explicitly allows it:
#
#	GTS9_ALLOW_POWER=1 reference/boot-tests/test-185-*/shutdown-baseline.sh 3 reboot
#
# Without that variable it performs the preflight and prints what it would do.
#
# Per round it records: boot_id, /proc/cmdline, failed units, the time the
# command was issued, when the USB ACM link disappeared and reappeared, the
# previous boot's shutdown journal tail, watchdog state, flight/mirror service
# state, tty state, and any workqueue/RCU/RPMh/DPU/MMC stall marker.
set -uo pipefail

REPO=/home/ms/Samsung/galaxy_tab_s9_linux
D=$(cd "$(dirname "$0")" && pwd)
OUT=$D/shutdown-baseline.txt
ROUNDS_DIR=$D/rounds
CR=$REPO/scripts/console-run.ps1
CW=$REPO/scripts/console-watch.ps1
PS=powershell.exe
N=${1:-3}
ACTION=${2:-reboot}          # reboot | poweroff | both
SHELL_PORT=${GTS9_SHELL_PORT:-COM17}
CONSOLE_PORT=${GTS9_CONSOLE_PORT:-COM19}
ALLOW=${GTS9_ALLOW_POWER:-0}
WINROOT='C:\gts9-work\test185'
WINLOCAL=/mnt/c/gts9-work/test185

mkdir -p "$ROUNDS_DIR" "$WINLOCAL"

say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$OUT"; }
field() { grep -a -m1 -- "$2" "$1" 2>/dev/null | sed "s/.*$2//" | tr -d '\r'; }
count() { local n; n=$(grep -a -c -E "$1" "$2" 2>/dev/null); printf '%s' "${n:-0}"; }

preflight() {
	local out=$ROUNDS_DIR/preflight.txt
	local raw=$ROUNDS_DIR/preflight-raw.txt
	timeout 300 "$PS" -NoProfile -ExecutionPolicy Bypass -File "$CR" \
		-Out "$WINROOT\\preflight.log" -Port "$SHELL_PORT" \
		-WaitReadySeconds 150 -ReadSeconds 25 \
		-Commands 'echo PF;BID=$(cat /proc/sys/kernel/random/boot_id);echo boot_id=$BID;cut -d" " -f1 /proc/uptime;echo flags=$(cat /proc/cmdline | tr " " "\n" | grep -c -E "gts9_kmsg_mirror|gts9_dpu_flight");echo wd=$(cat /proc/sys/kernel/watchdog) slp=$(cat /proc/sys/kernel/softlockup_panic) htp=$(cat /proc/sys/kernel/hung_task_panic) wq=$(cat /sys/module/workqueue/parameters/panic_on_stall_time);echo flight=$(systemctl is-active gts9-dpu-flight.service) mirror=$(systemctl is-active gts9-kmsg-console.service);echo getty=$(systemctl is-active gts9-acm-getty.service) msm0=$(systemctl is-enabled serial-getty@ttyMSM0.service 2>&1);echo ttyGS0=$(test -c /dev/ttyGS0 && echo yes || echo no) ttyGS1=$(test -c /dev/ttyGS1 && echo yes || echo no);echo failed=$(systemctl --failed --no-pager --plain | grep -c "loaded failed");cat /proc/cmdline' \
		>"$raw" 2>&1
	grep -aE "RECV  (PF|boot_id=|flags=|wd=|flight=|getty=|ttyGS0=|failed=|[0-9]+\.[0-9]+)|shell never answered|could not open" "$raw" >"$out"
	cat "$out"
}

# send_action ROUND ACTION
# Listen on both ports, send the power command to the shell port, and report the
# USB presence transitions and how long the tablet took to go away or come back.
send_action() {
	local round=$1 action=$2
	local clog=$ROUNDS_DIR/console-$action-$round.log
	local slog=$ROUNDS_DIR/shell-$action-$round.log
	timeout 900 "$PS" -NoProfile -ExecutionPolicy Bypass -File "$CW" \
		-Out "$WINROOT\\console-$action-$round.log" -Seconds 150 -Port "$CONSOLE_PORT" \
		>"$ROUNDS_DIR/console-$action-$round-watch.txt" 2>&1 &
	local conpid=$!
	sleep 2
	timeout 300 "$PS" -NoProfile -ExecutionPolicy Bypass -File "$CW" \
		-Out "$WINROOT\\shell-$action-$round.log" -Seconds 120 -Port "$SHELL_PORT" \
		-Command "$action" -CommandAtSeconds 6 \
		2>&1 | grep -aE "SENT|PRESENCE usb|watch done" | tee -a "$OUT"
	wait "$conpid" 2>/dev/null || true
	cp "$WINLOCAL/console-$action-$round.log" "$clog" 2>/dev/null || true
	cp "$WINLOCAL/shell-$action-$round.log" "$slog" 2>/dev/null || true
}

probe_after() {
	local tag=$1
	local out=$ROUNDS_DIR/after-$tag.txt
	local raw=$ROUNDS_DIR/after-$tag-raw.txt
	timeout 400 "$PS" -NoProfile -ExecutionPolicy Bypass -File "$CR" \
		-Out "$WINROOT\\after-$tag.log" -Port "$SHELL_PORT" \
		-WaitReadySeconds 300 -ReadSeconds 30 \
		-Commands 'echo AF;echo boot_id=$(cat /proc/sys/kernel/random/boot_id);cut -d" " -f1 /proc/uptime;echo failed=$(systemctl --failed --no-pager --plain | grep -c "loaded failed");echo "--- previous boot tail";journalctl -b -1 -o short-monotonic --no-pager 2>/dev/null | tail -25;echo "--- previous boot markers";journalctl -b -1 -k -o short-monotonic --no-pager 2>/dev/null | grep -a -c -E "workqueue: .*stall|rcu:.*detected stall|rpmh_write_batch|frame done timeout|mmc.*[Tt]imeout|soft lockup|hung_task"' \
		>"$raw" 2>&1
	grep -aE "RECV  (AF|boot_id=|failed=|\[ *[0-9]+\.|--- )|shell never answered|could not open" "$raw" >"$out"
	cat "$out"
}

say "test-185 shutdown baseline: rounds=$N action=$ACTION allow_power=$ALLOW"

pre=$(preflight)
printf '%s\n' "$pre" | grep -aE "boot_id=|flags=|wd=|flight=|getty=|ttyGS0=|failed=" | sed 's/^/  /' | tee -a "$OUT"

if ! grep -aq "flags=0" "$ROUNDS_DIR/preflight.txt" 2>/dev/null; then
	say "WARNING: the command line still carries gts9_kmsg_mirror/gts9_dpu_flight; this is not the low-instrumentation profile"
fi
if ! grep -aq "flight=inactive" "$ROUNDS_DIR/preflight.txt" 2>/dev/null; then
	say "WARNING: gts9-dpu-flight.service is active; the measurement would be confounded"
fi

if [ "$ALLOW" != "1" ]; then
	say "dry run: set GTS9_ALLOW_POWER=1 to actually send power commands"
	say "would run, per round: $ACTION over $SHELL_PORT, capture on $CONSOLE_PORT, then read -b -1"
	exit 0
fi

boot_id=$(field "$ROUNDS_DIR/preflight.txt" 'boot_id=')
[ -n "$boot_id" ] || { say "FATAL: no shell on $SHELL_PORT"; exit 1; }

actions=()
case "$ACTION" in
reboot) for _ in $(seq 1 "$N"); do actions+=(reboot); done ;;
poweroff) for _ in $(seq 1 "$N"); do actions+=(poweroff); done ;;
both) for _ in $(seq 1 "$N"); do actions+=(reboot poweroff); done ;;
*) say "FATAL: action must be reboot, poweroff or both"; exit 2 ;;
esac

i=0
for act in "${actions[@]}"; do
	i=$((i + 1))
	say "=== round $i: $act (boot_id before=$boot_id) ==="
	send_action "$i" "$act" | tee -a "$OUT"

	# poweroff leaves the tablet off: the operator powers it back on, and the
	# harness waits for the shell instead of pretending it can continue.
	txt=$(probe_after "$i-$act")
	printf '%s\n' "$txt" | grep -aE "boot_id=|failed=|shell never answered" | sed 's/^/  /' | tee -a "$OUT"
	new_id=$(field "$ROUNDS_DIR/after-$i-$act.txt" 'boot_id=')

	{
		echo "round=$i"
		echo "action=$act"
		echo "boot_id_before=$boot_id"
		echo "boot_id_after=${new_id:-none}"
		echo "shell_log=$ROUNDS_DIR/shell-$act-$i.log"
		echo "console_log=$ROUNDS_DIR/console-$act-$i.log"
		echo "usb_gone=$(count 'PRESENCE usb0525:a4a7=False' "$ROUNDS_DIR/shell-$act-$i.log")"
		echo "usb_back=$(count 'PRESENCE usb0525:a4a7=True' "$ROUNDS_DIR/shell-$act-$i.log")"
		echo "shell_never_answered=$(count 'shell never answered' "$ROUNDS_DIR/after-$i-$act-raw.txt")"
		echo "prev_boot_stall_markers=$(grep -a -o -E 'RECV  [0-9]+$' "$ROUNDS_DIR/after-$i-$act.txt" | tail -1 | tr -dc '0-9')"
	} >"$ROUNDS_DIR/round-$i-$act.txt"
	grep -aE "usb_gone|usb_back|shell_never|prev_boot_stall" "$ROUNDS_DIR/round-$i-$act.txt" | sed 's/^/  /' | tee -a "$OUT"

	if [ "$act" = poweroff ] && [ -n "$new_id" ]; then
		say "round $i: the operator powered the tablet back on"
		boot_id=$new_id
	elif [ "$act" = poweroff ]; then
		say "round $i: tablet stayed off (expected for poweroff); stopping here"
		break
	else
		[ -n "$new_id" ] && boot_id=$new_id
	fi
done

say "shutdown baseline done (action=$ACTION, rounds=$i)"
