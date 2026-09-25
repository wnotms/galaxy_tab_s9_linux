#!/usr/bin/env bash
# test-187: capture the SHUTDOWN path with kernel output on the host console.
#
# Round 7 localised the failure to the shutdown path: the anomalous boot's journal
# shows an ordinary shutdown in progress at 70.5 s (multi-user.target stopped,
# services stopping), three "Connection terminated" errors showing dbus was already
# gone, and then NO systemd-shutdown where a clean boot has exactly two. So the
# machine fails to COMPLETE a shutdown.
#
# pstore does not survive a reboot on this board (measured twice), and journald
# stops with userspace, so the only channel that can show whether a panic occurs is
# a host console held open ACROSS the reset. Round 7 proved that channel works:
# with printk's console loglevel raised, a /dev/kmsg marker reached COM19. Panic
# output is KERN_EMERG and bypasses the loglevel entirely.
#
# This script therefore:
#   1. raises the console loglevel so shutdown-time kernel messages are printed,
#      not just userspace ones;
#   2. starts a long capture on BOTH ports BEFORE issuing anything;
#   3. issues `systemctl reboot`;
#   4. leaves the capture running through the shutdown and the next boot.
#
# SAFETY: one `systemctl reboot`, nothing else. No flash, no partition write.
#
#   reference/boot-tests/test-187-*/shutdown-capture.sh          # dry run
#   GTS9_ALLOW_POWER=1 reference/boot-tests/test-187-*/shutdown-capture.sh
set -uo pipefail

REPO=$(cd "$(dirname "$0")/../../.." && pwd)
D=$(cd "$(dirname "$0")" && pwd)
CR=$REPO/scripts/console-run.sh
CW=$REPO/scripts/console-watch.sh
ALLOW=${GTS9_ALLOW_POWER:-0}
WINDIR='C:\gts9-work\shutdown-cap'
LOCAL=/mnt/c/gts9-work/shutdown-cap
ROUNDS=${GTS9_SHUTDOWN_ROUNDS:-1}
SECONDS_PER_ROUND=${GTS9_SHUTDOWN_WINDOW:-900}

mkdir -p "$LOCAL"
OUT=$D/shutdown-capture.txt
say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$OUT"; }

if [ "$ALLOW" != "1" ]; then
	say "dry run: would raise the console loglevel, capture COM19 for"
	say "${SECONDS_PER_ROUND}s per round, issue 'systemctl reboot', and inspect the"
	say "capture for a panic. Set GTS9_ALLOW_POWER=1 to actually run it."
	exit 0
fi

for r in $(seq 1 "$ROUNDS"); do
	say "=== shutdown round $r/$ROUNDS ==="

	# 1. Full kernel verbosity on the console for this round.
	timeout 200 "$CR" \
		-Out "$WINDIR\\pre-$r.log" -Port COM17 -WaitReadySeconds 200 -ReadSeconds 60 \
		-Commands 'echo "before=$(cat /proc/sys/kernel/printk)"; echo 8 > /proc/sys/kernel/printk; echo "after=$(cat /proc/sys/kernel/printk)"; echo LVL_SET' \
		>"$D/shutdown-$r-pre.txt" 2>&1
	say "  loglevel: $(grep -aoE 'after=[0-9. ]+' "$D/shutdown-$r-pre.txt" | tail -1)"

	# 2. Capture COM19 only, and ISSUE THE TRIGGER FIRST over COM17.
	# Holding COM17 for a capture blocks the very trigger this script needs -
	# that is what made round 8 produce 373-byte empty captures. COM19 is the
	# port that carries kernel output, so it is the only one worth watching here.
	timeout $((SECONDS_PER_ROUND + 120)) "$CW" \
		-Out "$WINDIR\\console-$r.log" \
		-Seconds "$SECONDS_PER_ROUND" -Port COM19 >"$D/shutdown-$r-w19.txt" 2>&1 &
	w19=$!
	sleep 8

	# 3. The suspect action, over the shell port, before anything watches it.
	timeout 200 "$CR" \
		-Out "$WINDIR\\trigger-$r.log" -Port COM17 -WaitReadySeconds 120 -ReadSeconds 20 \
		-Commands 'echo TRIGGER_SHUTDOWN; systemctl reboot' >"$D/shutdown-$r-trigger.txt" 2>&1
	say "  shutdown triggered at $(date -u +%H:%M:%S); COM19 capture running"

	wait "$w19" 2>/dev/null || true

	# 4. Inspect the capture for the two decisive outcomes.
	clog=$LOCAL/console-$r.log
	cp "$clog" "$D/shutdown-$r-console.log" 2>/dev/null || say "  WARNING: no console capture"
	{
		echo "round=$r"
		echo "kind=warm-reboot"
		echo "console_bytes=$(wc -c <"$D/shutdown-$r-console.log" 2>/dev/null || echo 0)"
		echo "console_lines=$(wc -l <"$D/shutdown-$r-console.log" 2>/dev/null || echo 0)"
		echo "panic_lines=$(grep -ac 'Kernel panic' "$D/shutdown-$r-console.log" 2>/dev/null || echo 0)"
		echo "softlockup_lines=$(grep -acE 'BUG: soft lockup|watchdog: BUG' "$D/shutdown-$r-console.log" 2>/dev/null || echo 0)"
		echo "hardlockup_lines=$(grep -acE 'BUG: hard LOCKUP|Hard LOCKUP' "$D/shutdown-$r-console.log" 2>/dev/null || echo 0)"
		echo "hungtask_lines=$(grep -acE 'hung_task|blocked for more than' "$D/shutdown-$r-console.log" 2>/dev/null || echo 0)"
		echo "rcu_lines=$(grep -acE 'rcu.*detected stall|rcu.*starved' "$D/shutdown-$r-console.log" 2>/dev/null || echo 0)"
		echo "calltrace_lines=$(grep -ac 'Call trace' "$D/shutdown-$r-console.log" 2>/dev/null || echo 0)"
		echo "systemd_shutdown_seen=$(grep -ac 'systemd-shutdown' "$D/shutdown-$r-console.log" 2>/dev/null || echo 0)"
		echo "connection_terminated=$(grep -ac 'Connection terminated' "$D/shutdown-$r-console.log" 2>/dev/null || echo 0)"
		echo "sd_shutting_down=$(grep -ac 'Shutting down' "$D/shutdown-$r-console.log" 2>/dev/null || echo 0)"
	} >"$D/shutdown-$r-verdict.txt"
	cat "$D/shutdown-$r-verdict.txt" | sed 's/^/  /' | tee -a "$OUT"

	# The decisive split.
	if grep -aq "Kernel panic\|BUG: soft lockup\|BUG: hard LOCKUP" "$D/shutdown-$r-console.log" 2>/dev/null; then
		say "  *** PANIC/LOCKUP CAPTURED on the shutdown path - extract the report above it"
	elif [ "$(grep -ac 'systemd-shutdown' "$D/shutdown-$r-console.log" 2>/dev/null)" = "0" ] && \
	     [ "$(grep -ac 'Shutting down' "$D/shutdown-$r-console.log" 2>/dev/null)" != "0" ]; then
		say "  *** SHUTDOWN STARTED BUT NEVER REACHED systemd-shutdown, WITH NO PANIC"
		say "      => the shutdown hangs without a kernel panic; the watchdog does not classify it"
	else
		say "  shutdown completed normally this round (no stall on this attempt)"
	fi
done

say "done; captures under $LOCAL and $D/shutdown-N-console.log"
