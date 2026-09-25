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
# journald is wedged by then too, and `softlockup_panic=1` sends the rest to
# /dev/console as KERN_EMERG.  The stack trace exists once, on the wire, and then
# the watchdog reboots - so the only way to have it is to be holding COM19.
#
# The cycle is driven by EVIDENCE, not by a clock.  COM19 is held open for the
# whole cycle, and that watcher is both the instrument and the sensor: its
# `PRESENCE usb0525:a4a7=False` line is the tablet actually going away, and the
# matching `True` is it coming back.  Nothing sleeps waiting for a reboot; the loop
# polls the watcher's own log once a second and acts the moment the transition
# appears, which is also what gives an honest outage measurement.
#
# (An earlier revision polled the shell instead, and got it wrong twice: it slept
# through the window it was hunting, and its readiness probe could not tell "the
# tablet is rebooting" from "the host lost its route to it".)
#
# Every cycle is `systemctl reboot` over the console: a WARM REBOOT, never called a
# cold boot.  Nothing is flashed and no partition is written.
#
#   reference/boot-tests/test-190-*/wedge-hunt.sh 30          # dry run
#   GTS9_ALLOW_POWER=1 reference/boot-tests/test-190-*/wedge-hunt.sh 30
set -uo pipefail

D=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$D/../../.." && pwd)
CR=$REPO/scripts/console-run.sh
CW=$REPO/scripts/console-watch.sh

CYCLES=${1:?usage: wedge-hunt.sh <cycles|-1>}
ALLOW=${GTS9_ALLOW_POWER:-0}
# Must cover shutdown + boot + the first seconds after it: every wedge on record
# struck between 5.4 s and 7.0 s into the new boot, and a reboot here takes ~15 s.
WINDOW=${GTS9_WINDOW:-60}
ONLINE_GRACE=${GTS9_ONLINE_GRACE:-25}
WINDIR=${GTS9_WINDIR:-'C:\Users\ms\AppData\Local\Temp\gts9-wedge'}
LOCAL=${GTS9_LOCALDIR:-/mnt/c/Users/ms/AppData/Local/Temp/gts9-wedge}
DIR=$D/wedge-hunt
OUT=$D/wedge-hunt.txt

mkdir -p "$DIR" "$LOCAL"
say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$OUT"; }
now() { date -u +%s; }
stamp() { date -u +%Y-%m-%dT%H:%M:%SZ; }

if [ "$ALLOW" != "1" ]; then
	say "dry run: would run ${CYCLES} warm-reboot cycles, holding COM19 for ${WINDOW}s"
	say "each and following the tablet's own USB presence rather than a timer."
	say "Set GTS9_ALLOW_POWER=1 to run."
	exit 0
fi

say "=== wedge hunt: cycles=${CYCLES} window=${WINDOW}s kind=warm-reboot ==="

caught=0
i=0
while [ "$CYCLES" = "-1" ] || [ "$i" -lt "$CYCLES" ]; do
	i=$((i + 1))
	wlog=$LOCAL/cycle-$i.log
	rm -f "$wlog"
	say "--- cycle $i ---"

	# The watcher is the instrument AND the sensor.  It timestamps every console
	# line and every USB presence change, so the capture and the timing come from
	# the same clock and the same file.
	timeout $((WINDOW + 60)) "$CW" -Out "$WINDIR\\cycle-$i.log" -Seconds "$WINDOW" \
		-Port COM19 >"$DIR/cycle-$i-watch.txt" 2>&1 &
	w=$!

	# Wait for the watcher to have the port, then trigger.  Short and bounded: the
	# lead only has to be long enough for the port to open.
	for _ in $(seq 1 40); do
		grep -qa "port open on COM19" "$wlog" 2>/dev/null && break
		sleep 1
	done

	# Read the two transitions out of the watcher's own log.  The file is written
	# with CRLF, so the CR is stripped first; and the "True" that matters is the
	# one AFTER the "False", not the one the watcher logs when it starts.
	transitions() {
		tr -d '\r' <"$wlog" 2>/dev/null | awk '
			/PRESENCE usb0525:a4a7=False/ && !off { off = $1 }
			/PRESENCE usb0525:a4a7=True/  && off && !on { on = $1 }
			END { printf "%s %s", (off ? off : "-"), (on ? on : "-") }'
	}
	off_at=""; on_at=""
	trigger=$(now)
	"$CR" -Port COM17 -Out "$WINDIR\\trigger-$i.log" -WaitReadySeconds 30 \
		-ReadSeconds 5 -Commands 'systemctl reboot' >"$DIR/cycle-$i-trigger.txt" 2>&1
	say "  reboot issued at $(stamp)"

	# Follow the tablet, not a clock.
	deadline=$(( $(now) + WINDOW + ONLINE_GRACE ))
	while [ "$(now)" -lt "$deadline" ]; do
		read -r seen_off seen_on <<<"$(transitions)"
		if [ "$seen_off" != "-" ] && [ -z "$off_at" ]; then
			off_at=$seen_off
			say "  tablet gone at $off_at"
		fi
		if [ "$seen_on" != "-" ]; then
			on_at=$seen_on
			say "  tablet back at $on_at"
			break
		fi
		sleep 1
	done

	wait "$w" 2>/dev/null || true
	cp "$wlog" "$DIR/cycle-$i-console.log" 2>/dev/null || : >"$DIR/cycle-$i-console.log"
	clog=$DIR/cycle-$i-console.log

	{
		echo "cycle=$i"
		echo "kind=warm-reboot"
		echo "triggered_at=$(date -u -d "@$trigger" +%Y-%m-%dT%H:%M:%SZ)"
		echo "tablet_gone_at=${off_at:-never}"
		echo "tablet_back_at=${on_at:-never}"
		echo "console_bytes=$(wc -c <"$clog")"
		echo "panic=$(grep -ac 'Kernel panic' "$clog" || true)"
		echo "softlockup=$(grep -acE 'BUG: soft lockup|watchdog: BUG' "$clog" || true)"
		echo "hardlockup=$(grep -acE 'BUG: hard LOCKUP' "$clog" || true)"
		echo "workqueue=$(grep -ac 'BUG: workqueue lockup' "$clog" || true)"
		echo "rcu=$(grep -acE 'rcu.*detected stall' "$clog" || true)"
		echo "nmi_unanswered=$(grep -acE "haven.t responded to the NMI" "$clog" || true)"
	} >"$DIR/cycle-$i-verdict.txt"

	# One health check, and it requires a command RESULT rather than an echo - the
	# distinction that hid the A-5 failure for five rounds.
	alive=$("$CR" -Port COM17 -Out "$WINDIR\\alive-$i.log" -WaitReadySeconds 60 \
		-ReadSeconds 5 -Commands 'echo GTS9_ALIVE_$(cut -d" " -f1 /proc/uptime)_END' 2>/dev/null \
		| sed -n 's/.*GTS9_ALIVE_\([0-9][0-9]*\)\.[0-9]*_END.*/\1/p' | tail -1)
	echo "uptime_after=${alive:-none}" >>"$DIR/cycle-$i-verdict.txt"

	get() { sed -n "s/^$1=//p" "$DIR/cycle-$i-verdict.txt"; }
	say "  uptime=${alive:-?}s  panic=$(get panic) softlockup=$(get softlockup) workqueue=$(get workqueue) rcu=$(get rcu) nmi=$(get nmi_unanswered)"

	if [ -z "$on_at" ] || [ -z "$alive" ] || [ "$(get panic)" != "0" ] \
		|| [ "$(get softlockup)" != "0" ] || [ "$(get workqueue)" != "0" ] \
		|| [ "$(get rcu)" != "0" ]; then
		caught=1
		say "  *** WEDGE CAPTURED in cycle $i - stopping so the capture is preserved"
		grep -aE -B4 -A40 'Kernel panic|BUG: soft lockup|BUG: workqueue lockup|rcu.*detected stall' "$clog" \
			| sed 's/\x1b\[[0-9;]*m//g' >"$D/wedge-hunt-capture.txt"
		say "      extracted to wedge-hunt-capture.txt ($(wc -l <"$D/wedge-hunt-capture.txt") lines)"
		break
	fi
done

say "=== done: $i cycle(s), wedge_captured=$caught ==="
exit $((caught ? 0 : 1))
