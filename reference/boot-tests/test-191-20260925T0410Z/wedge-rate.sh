#!/usr/bin/env bash
# test-191: measure the CPU-wedge rate with the EPSS L3 provider built in.
#
# This is the expensive half of test 191, and it is a *rate* measurement, not a
# capture hunt.  docs/CPU_WEDGE_EVIDENCE.md gives the confound-free baseline it
# must be compared against:
#
#   pre-fix   10 of 46 boots  (21.7%)   Fisher p = 0.043 against post-fix
#   post-fix   1 of 29 boots  ( 3.4%)
#
# and the confound-free marker is the unanswered NMI, not any watchdog message:
# all 11 wedge boots carry
#
#   After 10 seconds, these CPUS still haven't responded to the NMI: N
#
# while downstream victims (soft lockup, workqueue lockup, RCU stall, the panic)
# vary.  So `nmi_unanswered` is what this counts, and it is a STOP condition here
# - unlike test-190's hunt, which could walk past a wedge that showed only the NMI
# inside the capture window.
#
# Four things differ from test-190's hunt, all of them things that run taught:
#
#   1. every run gets its OWN output directory (timestamped), so a later run can
#      never overwrite an earlier capture - test-190 lost one that way;
#   2. WINDOW defaults to 300 s, not 60: the panic lands ~180 s after the wedge;
#   3. the NMI marker is a stop condition and is extracted into the capture;
#   4. the cycle records the cpufreq state as well, so a run that somehow lost the
#      new kernel is visible in the data rather than inferred later.
#
# Every cycle is `systemctl reboot` over the console: a WARM REBOOT, never called a
# cold boot.  Nothing is flashed and no partition is written by this script.
#
#   reference/boot-tests/test-191-*/wedge-rate.sh 20            # dry run
#   GTS9_ALLOW_POWER=1 reference/boot-tests/test-191-*/wedge-rate.sh 20
set -uo pipefail

D=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$D/../../.." && pwd)
CR=$REPO/scripts/console-run.sh
CW=$REPO/scripts/console-watch.sh

CYCLES=${1:?usage: wedge-rate.sh <cycles|-1>}
ALLOW=${GTS9_ALLOW_POWER:-0}
WINDOW=${GTS9_WINDOW:-300}
ONLINE_GRACE=${GTS9_ONLINE_GRACE:-40}
WINDIR=${GTS9_WINDIR:-'C:\Users\ms\AppData\Local\Temp\gts9-wedge'}
LOCAL=${GTS9_LOCALDIR:-/mnt/c/Users/ms/AppData/Local/Temp/gts9-wedge}

case "$CYCLES" in ''|*[!0-9-]*) echo "cycles must be a number or -1" >&2; exit 2 ;; esac

# One directory per run.  RUN is overridable so a run can be resumed or named.
RUN=${GTS9_RUN:-$(date -u +%Y%m%dT%H%M%SZ)}
DIR=$D/wedge-rate-$RUN
OUT=$DIR/wedge-rate.txt

mkdir -p "$DIR" "$LOCAL"
say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$OUT"; }
now() { date -u +%s; }
stamp() { date -u +%Y-%m-%dT%H:%M:%SZ; }

if [ "$ALLOW" != "1" ]; then
	say "dry run: would run ${CYCLES} warm-reboot cycles, holding COM19 for ${WINDOW}s"
	say "each, in $DIR, following the tablet's own USB presence rather than a timer."
	say "Set GTS9_ALLOW_POWER=1 to run."
	exit 0
fi

say "=== wedge rate: cycles=${CYCLES} window=${WINDOW}s kind=warm-reboot dir=$DIR ==="
say "baseline to compare against: pre-fix 10/46 (21.7%), post-fix 1/29 (3.4%)"

wedges=0
cycles_done=0
i=0
while [ "$CYCLES" = "-1" ] || [ "$i" -lt "$CYCLES" ]; do
	i=$((i + 1))
	wlog=$LOCAL/test191-cycle-$i.log
	rm -f "$wlog"
	say "--- cycle $i ---"

	timeout $((WINDOW + 60)) "$CW" -Out "$WINDIR\\test191-cycle-$i.log" -Seconds "$WINDOW" \
		-Port COM19 >"$DIR/cycle-$i-watch.txt" 2>&1 &
	w=$!

	for _ in $(seq 1 40); do
		grep -qa "port open on COM19" "$wlog" 2>/dev/null && break
		sleep 1
	done

	# CRLF, and the "True" that matters is the one AFTER the "False".
	transitions() {
		tr -d '\r' <"$wlog" 2>/dev/null | awk '
			/PRESENCE usb0525:a4a7=False/ && !off { off = $1 }
			/PRESENCE usb0525:a4a7=True/  && off && !on { on = $1 }
			END { printf "%s %s", (off ? off : "-"), (on ? on : "-") }'
	}
	off_at=""; on_at=""
	trigger=$(now)
	"$CR" -Port COM17 -Out "$WINDIR\\test191-trigger-$i.log" -WaitReadySeconds 30 \
		-ReadSeconds 5 -Commands 'systemctl reboot' >"$DIR/cycle-$i-trigger.txt" 2>&1
	say "  reboot issued at $(stamp)"

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

	# One health check, requiring a command RESULT rather than an echo.
	alive=$("$CR" -Port COM17 -Out "$WINDIR\\test191-alive-$i.log" -WaitReadySeconds 90 \
		-ReadSeconds 5 -Commands 'echo GTS9_ALIVE_$(cut -d" " -f1 /proc/uptime)_END' 2>/dev/null \
		| sed -n 's/.*GTS9_ALIVE_\([0-9][0-9]*\)\.[0-9]*_END.*/\1/p' | tail -1)
	echo "uptime_after=${alive:-none}" >>"$DIR/cycle-$i-verdict.txt"

	# The new kernel's fingerprint, from the boot that just happened.  Without
	# this a run could quietly measure the old kernel.
	kernel=$(sed -n 's/.*Linux version \([^ ]*\).*/\1/p' "$clog" | tail -1)
	echo "kernel=${kernel:-unknown}" >>"$DIR/cycle-$i-verdict.txt"
	policies=$("$CR" -Port COM17 -Out "$WINDIR\\test191-policy-$i.log" -WaitReadySeconds 60 \
		-ReadSeconds 5 -Commands 'echo GTS9_P_$(ls -d /sys/devices/system/cpu/cpufreq/policy* 2>/dev/null | wc -l)_END' 2>/dev/null \
		| sed -n 's/.*GTS9_P_\([0-9][0-9]*\)_END.*/\1/p' | tail -1)
	echo "policies=${policies:-none}" >>"$DIR/cycle-$i-verdict.txt"

	get() { sed -n "s/^$1=//p" "$DIR/cycle-$i-verdict.txt"; }
	say "  uptime=${alive:-?}s  panic=$(get panic) softlockup=$(get softlockup) workqueue=$(get workqueue) rcu=$(get rcu) nmi=$(get nmi_unanswered) policies=$(get policies)"

	nmi=$(get nmi_unanswered); [ -n "$nmi" ] || nmi=0
	if [ "$nmi" != "0" ]; then
		wedges=$((wedges + 1))
		say "  *** WEDGE: $nmi unanswered-NMI line(s) in cycle $i"
	fi

	# Stop on a wedge only when it is worth stopping for.  The NMI marker alone is
	# a real wedge and must be recorded, but the *stack* only exists if the panic
	# landed inside the window, so the run stops for either and says which it got.
	if [ -z "$on_at" ] || [ -z "$alive" ] || [ "$(get panic)" != "0" ] \
		|| [ "$(get softlockup)" != "0" ] || [ "$(get workqueue)" != "0" ] \
		|| [ "$(get rcu)" != "0" ] || [ "$nmi" != "0" ]; then
		grep -aE -B4 -A60 'Kernel panic|BUG: soft lockup|BUG: workqueue lockup|rcu.*detected stall|haven.t responded to the NMI' "$clog" \
			| sed 's/\x1b\[[0-9;]*m//g' >"$DIR/capture-cycle-$i.txt"
		say "  extracted to capture-cycle-$i.txt ($(wc -l <"$DIR/capture-cycle-$i.txt") lines)"
		if [ "$(get panic)" != "0" ] || [ "$(get softlockup)" != "0" ]; then
			say "  *** stopping: this capture carries a stack trace"
			break
		fi
		say "  *** continuing: NMI marker only, no stack in this window"
	fi
	cycles_done=$i
done

{
	echo "cycles_run=$cycles_done"
	echo "wedges=$wedges"
	echo "window=$WINDOW"
	echo "dir=$DIR"
} >"$DIR/wedge-rate-summary.txt"
say "=== done: $cycles_done cycle(s), wedges=$wedges ==="
cat "$DIR/wedge-rate-summary.txt" | tee -a "$OUT"
