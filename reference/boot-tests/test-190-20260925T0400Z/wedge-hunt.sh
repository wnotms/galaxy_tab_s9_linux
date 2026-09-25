#!/usr/bin/env bash
# test-190: hunt for a CPU wedge, and keep the stack trace when one happens.
#
# Why.  docs/CPU_WEDGE_EVIDENCE.md establishes that the failure is a CPU-level
# wedge: 11 of the 88 boots the journal retains show an unanswered NMI, and never
# a mere software stall.  It also establishes why no trace of the *cause* exists.
# On the one post-fix wedge the journal ends in the middle of the lockup dump:
#
#   [104.320045] watchdog: BUG: soft lockup - CPU#7 stuck for 53s! [rcu_exp_gp_kthr:19]
#   [104.517368] gts9 kernel:         #5: 100% system,  0% softirq,  0% hardirq, 0% idle
#   <end of journal>
#
# journald is itself wedged by then, and `softlockup_panic=1` sends the rest to
# /dev/console as KERN_EMERG.  So the stack trace exists exactly once, on the wire,
# for as long as it takes the watchdog to reboot - and the only way to have it is to
# be holding COM19 when it happens.
#
# This runs warm-reboot cycles with COM19 held across each one, and stops the moment
# a cycle captures a panic or a lockup so the capture is preserved with the context
# around it.
#
# Every cycle is `systemctl reboot` over the console: a WARM REBOOT, never called a
# cold boot.  Nothing is flashed and no partition is written.
#
#   reference/boot-tests/test-190-*/wedge-hunt.sh 10            # dry run
#   GTS9_ALLOW_POWER=1 reference/boot-tests/test-190-*/wedge-hunt.sh 10
#
# At the post-fix rate measured so far (1 of 29 boots) 30 cycles is about a 65%
# chance and 50 about an 80% chance; `-1` means "keep going until one is caught or
# the operator stops it".
set -uo pipefail

D=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$D/../.." && pwd)
CR=$REPO/scripts/console-run.sh
CW=$REPO/scripts/console-watch.sh
SSH="$REPO/scripts/gts9-ssh.sh"

CYCLES=${1:?usage: wedge-hunt.sh <cycles|-1>}
ALLOW=${GTS9_ALLOW_POWER:-0}
WINDOW=${GTS9_WINDOW:-240}
SETTLE=${GTS9_SETTLE:-90}
WINDIR=${GTS9_WINDIR:-'C:\Users\ms\AppData\Local\Temp\gts9-wedge'}
LOCAL=${GTS9_LOCALDIR:-/mnt/c/Users/ms/AppData/Local/Temp/gts9-wedge}
DIR=$D/wedge-hunt
OUT=$D/wedge-hunt.txt

mkdir -p "$DIR" "$LOCAL"
say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$OUT"; }

# The keyboard and display draw an observer effect of their own, so they are left
# exactly as profile A leaves them: nothing here turns anything on.
LIVENESS='echo GTS9_ALIVE_$(cut -d" " -f1 /proc/uptime)_END'

if [ "$ALLOW" != "1" ]; then
	say "dry run: would run ${CYCLES} warm-reboot cycles, holding COM19 for ${WINDOW}s each,"
	say "and stop at the first captured panic or lockup. Set GTS9_ALLOW_POWER=1 to run."
	exit 0
fi

say "=== wedge hunt: cycles=${CYCLES} window=${WINDOW}s kind=warm-reboot ==="
i=0
caught=0
while [ "$CYCLES" = "-1" ] || [ "$i" -lt "$CYCLES" ]; do
	i=$((i + 1))
	say "--- cycle $i ---"

	# Hold COM19 across the whole shutdown, boot and the window in which every
	# wedge on record has struck (5.4-7.0 s of the new boot, and later).
	timeout $((WINDOW + 120)) "$CW" -Out "$WINDIR\\cycle-$i.log" -Seconds "$WINDOW" \
		-Port COM19 >"$DIR/cycle-$i-watch.txt" 2>&1 &
	w=$!
	sleep 6

	"$CR" -Port COM17 -Out "$WINDIR\\trigger-$i.log" -WaitReadySeconds 120 \
		-ReadSeconds 15 -Commands 'systemctl reboot' >"$DIR/cycle-$i-trigger.txt" 2>&1

	wait "$w" 2>/dev/null || true
	cp "$LOCAL/cycle-$i.log" "$DIR/cycle-$i-console.log" 2>/dev/null || true
	clog=$DIR/cycle-$i-console.log
	[ -f "$clog" ] || : >"$clog"

	{
		echo "cycle=$i"
		echo "kind=warm-reboot"
		echo "console_bytes=$(wc -c <"$clog")"
		echo "panic=$(grep -ac 'Kernel panic' "$clog" || true)"
		echo "softlockup=$(grep -acE 'BUG: soft lockup|watchdog: BUG' "$clog" || true)"
		echo "hardlockup=$(grep -acE 'BUG: hard LOCKUP' "$clog" || true)"
		echo "workqueue=$(grep -ac 'BUG: workqueue lockup' "$clog" || true)"
		echo "rcu=$(grep -acE 'rcu.*detected stall' "$clog" || true)"
		echo "nmi_unanswered=$(grep -acE "haven.t responded to the NMI" "$clog" || true)"
	} >"$DIR/cycle-$i-verdict.txt"

	nmi=$(sed -n 's/^nmi_unanswered=//p' "$DIR/cycle-$i-verdict.txt")
	panic=$(sed -n 's/^panic=//p' "$DIR/cycle-$i-verdict.txt")
	sl=$(sed -n 's/^softlockup=//p' "$DIR/cycle-$i-verdict.txt")
	wq=$(sed -n 's/^workqueue=//p' "$DIR/cycle-$i-verdict.txt")
	say "  panic=$panic softlockup=$sl workqueue=$wq rcu=$(sed -n 's/^rcu=//p' "$DIR/cycle-$i-verdict.txt") nmi=$nmi"

	if [ "${panic:-0}" != "0" ] || [ "${sl:-0}" != "0" ] || [ "${wq:-0}" != "0" ]; then
		caught=1
		say "  *** WEDGE CAPTURED in cycle $i - stopping so the capture is preserved"
		say "      console: $clog"
		# The report is the point: keep everything around it, not just the match.
		grep -aE -B4 -A40 'Kernel panic|BUG: soft lockup|BUG: workqueue lockup' "$clog" \
			| sed 's/\x1b\[[0-9;]*m//g' >"$D/wedge-hunt-capture.txt"
		say "      extracted to wedge-hunt-capture.txt ($(wc -l <"$D/wedge-hunt-capture.txt") lines)"
		break
	fi

	# Wait for a shell that EXECUTES, not merely echoes - the distinction that
	# hid the A-5 failure for five rounds.
	alive=0
	for attempt in 1 2 3 4; do
		if "$CR" -Port COM17 -Out "$WINDIR\\live-$i-$attempt.log" \
			-WaitReadySeconds 240 -ReadSeconds 20 -Commands "$LIVENESS" 2>/dev/null \
			| grep -aq 'GTS9_ALIVE_[0-9]'; then
			alive=1
			break
		fi
		sleep "$SETTLE"
	done
	if [ "$alive" != "1" ]; then
		caught=1
		say "  *** no executing shell after cycle $i - a wedge that panicked before the"
		say "      capture window would look like this; stopping"
		break
	fi
done

say "=== done: $i cycle(s), wedge_captured=$caught ==="
exit $((caught ? 0 : 1))
