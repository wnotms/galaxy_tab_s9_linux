#!/usr/bin/env bash
# test-183: controlled-stall rounds - the watchdog chain, on demand.
#
# The real stall is a race (it has been seen five times in a day of instrumented
# boots), so the recovery chain is also validated with a stall we control:
#
#   mode=hung  - a kernel thread blocks uninterruptibly; the hung-task detector
#                (45 s, hung_task_panic=1) must panic and panic=10 must reboot.
#   mode=spin  - one CPU spins with interrupts disabled for N seconds; the
#                soft-lockup detector (softlockup_panic=1) must report
#                "BUG: soft lockup - CPU#n stuck for Ns" and panic.
#
# Both are self-clearing: if the profile is broken the tablet resumes instead of
# wedging.  The point is that the *detector report reaches the host* (through
# gts9-kmsg-console) and the *tablet comes back on its own*, which is what the
# real stall needs.
#
#   reference/boot-tests/test-183-*/inject-rounds.sh [rounds] [mode] [seconds]
set -uo pipefail

REPO=/home/ms/Samsung/galaxy_tab_s9_linux
D=$(cd "$(dirname "$0")" && pwd)
OUT=$D/inject-rounds.txt
ROUNDS_DIR=$D/rounds-inject
CR=$REPO/scripts/console-run.ps1
CW=$REPO/scripts/console-watch.ps1
PS=powershell.exe
N=${1:-3}
MODE=${2:-hung}
SECS=${3:-60}
WINROOT='C:\gts9-work\test183'
WINLOCAL=/mnt/c/gts9-work/test183
KO=/root/gts9_stall_test.ko

mkdir -p "$ROUNDS_DIR"

say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$OUT"; }
field() { grep -a -m1 -- "$2" "$1" 2>/dev/null | sed "s/.*$2//" | tr -d '\r'; }
count() { local n; n=$(grep -a -c -E "$1" "$2" 2>/dev/null); printf '%s' "${n:-0}"; }

probe() {
	# Split, not one `local`: bash 5.3 expands every assignment before making
	# any of them, so `local a=$1 b=$DIR/x-$a` dies on unbound $a under set -u.
	local tag=$1
	local out=$ROUNDS_DIR/probe-$tag.txt
	local raw=$ROUNDS_DIR/probe-$tag-raw.txt
	sleep 5
	timeout 300 "$PS" -NoProfile -ExecutionPolicy Bypass -File "$CR" \
		-Out "C:\\gts9-work\\test183\\inject-probe-$tag.log" \
		-WaitReadySeconds 180 -ReadSeconds 20 \
		-Commands 'echo IP;BID=$(cat /proc/sys/kernel/random/boot_id);echo boot_id=$BID;cut -d" " -f1 /proc/uptime;echo running=$(systemctl is-system-running);D=$(ls -1d /var/log/gts9-boot-evidence/*-$(echo $BID | cut -c1-8)/ 2>/dev/null | head -1);echo dir=$D;cat "$D/verdict.txt" 2>/dev/null | head -20' \
		>"$raw" 2>&1
	grep -aE "RECV  (IP|boot_id=|[0-9]+\.[0-9]+|running=|collected_utc=|previous_boot=|prev_kernel_lines=|marker_)|shell never answered|could not open" "$raw" >"$out"
	cat "$out"
}

say "test-183 controlled stalls: rounds=$N mode=$MODE seconds=$SECS"

# COM17 is shared: a previous caller can still be letting go of it, so retry
# instead of declaring the tablet dead.
boot_id=""
for attempt in 1 2 3; do
	sleep 5
	pre=$(probe pre)
	printf '%s\n' "$pre" | tee -a "$OUT"
	boot_id=$(field "$ROUNDS_DIR/probe-pre.txt" 'boot_id=')
	say "preflight attempt $attempt: boot_id=${boot_id:-unknown}"
	[ -n "$boot_id" ] && break
	say "preflight: no answer, waiting 20 s"
	sleep 20
done
[ -n "$boot_id" ] || { say "FATAL: tablet not answering"; exit 1; }
say "start boot_id=$boot_id"

ok=0
for i in $(seq 1 "$N"); do
	say "=== injected round $i ($MODE ${SECS}s) ==="
	timeout $((SECS + 260)) "$PS" -NoProfile -ExecutionPolicy Bypass -File "$CW" \
		-Out "$WINROOT\\inject-$i.log" -Seconds $((SECS + 150)) \
		-Command "rmmod gts9_stall_test 2>/dev/null; insmod $KO mode=$([ "$MODE" = spin ] && echo 1 || echo 0) seconds=$SECS" \
		-CommandAtSeconds 10 \
		2>&1 | grep -aE "SENT|PRESENCE usb|watch done" | tail -8 | tee -a "$OUT"

	log=$ROUNDS_DIR/inject-$i-console.log
	cp "$WINLOCAL/inject-$i.log" "$log" 2>/dev/null || say "WARNING: no capture for round $i"
	{
		echo "round=$i"
		echo "mode=$MODE"
		echo "seconds=$SECS"
		echo "marker_hung_report=$(count 'blocked for more than' "$log")"
		echo "marker_soft_lockup=$(count 'BUG: soft lockup' "$log")"
		echo "marker_soft_lockup_allcpu=$(count 'softlockup' "$log")"
		echo "marker_panic=$(count 'Kernel panic' "$log")"
		echo "marker_usb_gap=$(count 'PRESENCE usb' "$log")"
		echo "hung_line=$(grep -a -m1 'blocked for more than' "$log" 2>/dev/null)"
		echo "lockup_line=$(grep -a -m1 'BUG: soft lockup' "$log" 2>/dev/null)"
	} >"$ROUNDS_DIR/inject-$i.txt"
	grep -aE "marker_|_line=" "$ROUNDS_DIR/inject-$i.txt" | grep -avE "=0$|=$" | sed 's/^/  /' | tee -a "$OUT"

	post=$(probe "$i")
	printf '%s\n' "$post" | grep -aE "boot_id=|running=|previous_boot=|marker_|shell never answered" | sed 's/^/  /' | tee -a "$OUT"
	new_id=$(field "$ROUNDS_DIR/probe-$i.txt" 'boot_id=')
	prev_end=$(field "$ROUNDS_DIR/probe-$i.txt" 'previous_boot_end=')

	if [ -n "$new_id" ] && [ "$new_id" != "$boot_id" ]; then
		ok=$((ok + 1))
		echo "recovery=yes" >>"$ROUNDS_DIR/inject-$i.txt"
		echo "previous_boot_end=${prev_end:-unknown}" >>"$ROUNDS_DIR/inject-$i.txt"
		say "injected round $i: new boot_id -> the watchdog rebooted the tablet ($ok/$N)"
		boot_id=$new_id
	else
		echo "recovery=no" >>"$ROUNDS_DIR/inject-$i.txt"
		say "injected round $i: boot_id unchanged"
		if grep -aqE "shell never answered|could not open" "$ROUNDS_DIR/probe-$i.txt"; then
			say "injected round $i: the tablet did not come back; stopping"
			break
		fi
	fi
done

say "controlled stalls done: recoveries=$ok/$N"
{
	echo "rounds=$N"
	echo "mode=$MODE"
	echo "seconds=$SECS"
	echo "recoveries=$ok"
} >"$D/inject-rounds-summary.txt"
cat "$D/inject-rounds-summary.txt"
