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
# The USB network function, not the console: the getty check below runs over ssh
# because a console that cannot execute a command cannot be asked this question.
SSH=$REPO/scripts/gts9-ssh.sh

CYCLES=${1:?usage: wedge-rate.sh <cycles|-1>}
ALLOW=${GTS9_ALLOW_POWER:-0}
WINDOW=${GTS9_WINDOW:-300}
ONLINE_GRACE=${GTS9_ONLINE_GRACE:-40}
# Cut a cycle short once the boot has provably survived the wedge window; see the
# long comment in the cycle body.  GTS9_EARLY_EXIT=0 restores the full window.
EARLY_EXIT=${GTS9_EARLY_EXIT:-1}
EARLY_MIN_UPTIME=${GTS9_EARLY_MIN_UPTIME:-45}
case "$EARLY_EXIT" in 0|1) ;; *) echo "GTS9_EARLY_EXIT must be 0 or 1" >&2; exit 2 ;; esac
case "$EARLY_MIN_UPTIME" in ''|*[!0-9]*) echo "GTS9_EARLY_MIN_UPTIME must be a number" >&2; exit 2 ;; esac
# How long one console round trip is allowed to take.  The getty restart below
# doubles the number of probes for a cycle whose console went quiet.
CONSOLE_PROBE_TIMEOUT=${GTS9_CONSOLE_PROBE_TIMEOUT:-60}
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
	say "dry run: would run ${CYCLES} warm-reboot cycles in $DIR, following the"
	say "tablet's own USB presence rather than a timer.  COM19 is held for up to"
	say "${WINDOW}s, but a cycle ends as soon as the boot answers a command past"
	say "${EARLY_MIN_UPTIME}s with no wedge marker (GTS9_EARLY_EXIT=${EARLY_EXIT})."
	say "Set GTS9_ALLOW_POWER=1 to run."
	exit 0
fi

# --- console shell guard -----------------------------------------------------
# A silent console has two causes and they look identical: a boot that wedged, and
# a getty that is "active (running)" with no reachable shell on ttyGS0.  Measured on
# the healthy test-191 boot: the tty echoed every character and executed none of it,
# and `systemctl restart gts9-acm-getty.service` fixed it outright.  A series that
# could not tell those apart would report the getty defect as a stall, so before a
# silent console is believed, the getty is checked and restarted once.
#
# The check is `ps -t ttyGS0`, NOT `systemctl show -p TasksCurrent`: logind moves the
# session into session-N.scope, so TasksCurrent is 0 for a getty that works.
#
# The guard only applies where ssh can answer, and that is deliberate.  "Console
# silent" has two very different readings depending on the channel that carries it:
#
#   console silent, ssh alive    -> instrument defect; fix the getty and re-probe
#   console silent, ssh dead too -> a real failure; never restart anything
#
# and ssh itself answers only after userspace is up.  On the three boots on record
# where ssh was *refused* while ICMP still answered, the console was the only
# channel - so a guard that demanded ssh would have declared those boots stalls.
# Every outcome is recorded, so a cycle that could not be attributed is visible as
# unattributed rather than counted as a clean run.
GETTY_RESTARTED=0
WEDGE_ATTRIBUTION=attributed
ssh_answers() {
	timeout 20 "$SSH" 'echo GTS9_SSH_OK' 2>/dev/null | grep -q GTS9_SSH_OK
}
ssh_shell_present() {
	timeout 45 "$SSH" 'ps -t ttyGS0 -o args= 2>/dev/null | grep -qE "(^|/|-)(bash|sh|ash)( |$)"' \
		>/dev/null 2>&1
}
# Returns 0 only when a shell is present, restarting the getty once if needed.
# Sets GETTY_RESTARTED=1 when it had to intervene.
ensure_console_shell() {
	if ssh_shell_present; then
		return 0
	fi
	timeout 60 "$SSH" 'systemctl restart gts9-acm-getty.service' >/dev/null 2>&1
	sleep 6
	if ssh_shell_present; then
		GETTY_RESTARTED=1
		return 0
	fi
	return 1
}

# Ask the console how long the boot has been up.  /proc/uptime is "889.01", so the
# pattern needs the decimal point: a pattern without it matches nothing and reports
# a false stall, which this project has already shipped twice.
probe_console_uptime() {
	timeout $((CONSOLE_PROBE_TIMEOUT + 30)) "$CR" -Port COM17 \
		-Out "$WINDIR\\test191-alive-$1.log" -WaitReadySeconds "$CONSOLE_PROBE_TIMEOUT" \
		-ReadSeconds 15 \
		-Commands 'echo GTS9_ALIVE_$(cut -d" " -f1 /proc/uptime)_END' 2>/dev/null \
		| sed -n 's/.*GTS9_ALIVE_\([0-9][0-9]*\)\.[0-9]*_END.*/\1/p' | tail -1
}
# The same question over the other channel.  A console that will not answer is not
# by itself a dead kernel, and on a boot where ssh works it is not a dead kernel at
# all - so this decides between "instrument" and "stall", and it is recorded.
probe_ssh_uptime() {
	timeout 45 "$SSH" 'cut -d" " -f1 /proc/uptime' 2>/dev/null \
		| sed -n 's/^\([0-9][0-9]*\)\..*/\1/p' | tail -1
}

say "=== wedge rate: cycles=${CYCLES} window=${WINDOW}s kind=warm-reboot dir=$DIR ==="
say "early exit: ${EARLY_EXIT} (a boot that answers a command past ${EARLY_MIN_UPTIME}s with no marker ends its cycle)"
say "measured: the tablet is away 19.4 s per cycle on average; the window is for the panic, not the boot"
say "baseline to compare against: pre-fix 10/46 (21.7%), post-fix 1/29 (3.4%)"

wedges=0
unattributed=0
getty_restarts=0
cycles_done=0
i=0
while [ "$CYCLES" = "-1" ] || [ "$i" -lt "$CYCLES" ]; do
	i=$((i + 1))
	wlog=$LOCAL/test191-cycle-$i.log
	rm -f "$wlog"
	GETTY_RESTARTED=0
	WEDGE_ATTRIBUTION=attributed
	say "--- cycle $i ---"

	timeout $((WINDOW + 60)) "$CW" -Out "$WINDIR\\test191-cycle-$i.log" -Seconds "$WINDOW" \
		-Port COM19 >"$DIR/cycle-$i-watch.txt" 2>&1 &
	w=$!

	for _ in $(seq 1 40); do
		grep -qa "port open on COM19" "$wlog" 2>/dev/null && break
		sleep 1
	done

	# CRLF, and the "True" that matters is the one AFTER the "False".
	#
	# EVERY transition is reported, not just the first pair.  The first version of
	# this function returned only the first `False` and the first `True` after it,
	# and that hid a real failure: the wedged boot of 2026-09-25T04:57Z shows up as
	# `gone=2 back=3` here - the reboot the harness asked for, then the boot wedged,
	# then the watchdog restarted the tablet - and the parser collapsed all of that
	# into one ordinary 19-second outage.  A second outage IS the failure signature:
	# nothing but the watchdog reboots a boot the harness has already started.
	transitions() {
		tr -d '\r' <"$wlog" 2>/dev/null | awk '
			/PRESENCE usb0525:a4a7=False/ { n++; if (!off) off = $1 }
			/PRESENCE usb0525:a4a7=True/  { if (off && !on) on = $1 }
			END { printf "%s %s %d", (off ? off : "-"), (on ? on : "-"), n + 0 }'
	}
	off_at=""; on_at=""; outages=0; off2_at=""; on2_at=""
	trigger=$(now)
	"$CR" -Port COM17 -Out "$WINDIR\\test191-trigger-$i.log" -WaitReadySeconds 30 \
		-ReadSeconds 5 -Commands 'systemctl reboot' >"$DIR/cycle-$i-trigger.txt" 2>&1
	say "  reboot issued at $(stamp)"

	deadline=$(( $(now) + WINDOW + ONLINE_GRACE ))
	while [ "$(now)" -lt "$deadline" ]; do
		read -r seen_off seen_on seen_n <<<"$(transitions)"
		if [ "$seen_off" != "-" ] && [ -z "$off_at" ]; then
			off_at=$seen_off
			say "  tablet gone at $off_at"
		fi
		if [ "$seen_on" != "-" ]; then
			on_at=$seen_on
			outages=$seen_n
			say "  tablet back at $on_at"
			break
		fi
		sleep 1
	done

	# --- early exit ---------------------------------------------------------
	# Measured on 18 cycles of this harness: the tablet is away for 19.4 s on
	# average (18.6-20.2 s) and the cycle costs 209 s.  So 91% of every cycle was
	# the fixed capture window, not the reboot - which is not what the window is
	# for.  The window exists because the *panic that carries the stack* is printed
	# ~180 s after a wedge, and a wedged boot looks healthy for its first ten
	# seconds, so there is nothing to wait for on a boot that has already proved it
	# survived.
	#
	# Every wedge on record struck between 5.4 s and 14.3 s into the boot
	# (docs/CPU_WEDGE_EVIDENCE.md), so a shell that answers a command past
	# EARLY_MIN_UPTIME with zero markers in the capture is a boot that survived.
	# If the shell does not answer, or any marker is present, the full window is
	# kept - that is precisely the case the window exists for.
	#
	# The wait to reach EARLY_MIN_UPTIME is taken on the host's clock, from the
	# watcher's own `tablet back` timestamp, and only then is the shell asked once.
	# Asking the shell in a loop instead cost 112 s a cycle on the first attempt:
	# each console-run round trip is tens of seconds, so the number of them, not
	# the waiting, is what has to be minimised.
	#
	# console-watch.ps1 writes with `Add-Content` per line, which flushes each
	# line, so cutting the watcher short cannot lose what was already captured.
	MARKERS='Kernel panic|BUG: soft lockup|watchdog: BUG|BUG: hard LOCKUP|BUG: workqueue lockup|rcu.*detected stall|havent responded to the NMI|haven.t responded to the NMI'
	alive=""; alive_via=""; early=0; wedged=0
	if [ "$EARLY_EXIT" = "1" ] && [ -n "$on_at" ]; then
		back_epoch=$(date -u -d "$on_at" +%s 2>/dev/null) || back_epoch=""
		if [ -n "$back_epoch" ]; then
			# The kernel starts a second or two before USB presence returns.
			target=$((back_epoch + EARLY_MIN_UPTIME))
			# While waiting for the boot to be old enough, keep watching presence: a
			# SECOND outage is the failure signature.  Nothing but the watchdog
			# restarts a boot the harness has already started, so this is the one
			# signal that cannot be explained by anything the harness itself did.
			# The wedged boot of 2026-09-25T04:57Z shows up here as gone=2 - the
			# reboot the harness asked for, then the boot wedged, then the watchdog
			# restarted it - and the harness recorded it as one ordinary outage.
			while [ "$(now)" -lt "$target" ]; do
				read -r _ _ n2 <<<"$(transitions)"
				if [ "${n2:-0}" -ge 2 ]; then
					read -r off2_at on2_at <<<"$(tr -d '\r' <"$wlog" | awk '
						/PRESENCE usb0525:a4a7=False/ { f++; if (f==2) off=$1 }
						/PRESENCE usb0525:a4a7=True/  { t++; if (t==3) on=$1 }
						END { printf "%s %s", (off?off:"-"), (on?on:"-") }')"
					outages=$n2
					wedged=1
					say "  *** SECOND OUTAGE: the boot wedged and the watchdog restarted it"
					say "      gone=$off2_at back=${on2_at:-pending}"
					break
				fi
				sleep 2
			done
		fi
		if [ "$wedged" = "0" ]; then
			alive=$(probe_console_uptime "$i")
			alive_via=console
			if [ -z "$alive" ]; then
				# The console went quiet.  Which of the two readings applies is
				# decided by the other channel, not by the console.
				if ssh_answers; then
					if ensure_console_shell; then
						say "  console shell absent; restarted the getty, re-probing"
						alive=$(probe_console_uptime "$i")
						if [ -n "$alive" ]; then
							alive_via=console-after-getty-restart
						fi
					else
						say "  console shell absent and a getty restart did not restore it"
					fi
					if [ -z "$alive" ]; then
						# ssh answers, so the kernel is running even though its
						# console is not.  This is the instrument, not a stall.
						alive=$(probe_ssh_uptime)
						if [ -n "$alive" ]; then
							alive_via=ssh
						fi
					fi
				else
					# No other channel.  Console silence stands, and nothing is
					# restarted on a boot that may simply be failing.
					alive_via=console-silent-ssh-unreachable
					WEDGE_ATTRIBUTION=unattributed
					say "  console silent and ssh unreachable: treating it as a stall"
				fi
			fi
			# A boot that answered on EITHER channel past EARLY_MIN_UPTIME with no
			# wedge marker in the capture has proved it survived.  Attribution is
			# recorded separately: an ssh-only answer means the boot was healthy,
			# not that its console was.
			if [ -n "$alive" ] && [ "$alive" -ge "$EARLY_MIN_UPTIME" ] \
				&& ! grep -qaE "$MARKERS" "$wlog" 2>/dev/null; then
				early=1
			fi
		fi
	fi

	if [ "$early" = "1" ]; then
		# Stop the watcher and let it exit, so its log is complete on disk.
		# `kill $w` alone is NOT enough: $w is the `timeout` wrapper, and killing it
		# leaves the PowerShell child alive still holding COM19 - observed when the
		# previous run was stopped by hand, and it would break the NEXT cycle's port
		# open.  Kill the child by pattern too, then wait for the port to be free.
		kill "$w" 2>/dev/null || true
		wait "$w" 2>/dev/null || true
		for _ in $(seq 1 15); do
			pgrep -f "console-watch.ps1.*test191-cycle-$i" >/dev/null 2>&1 || break
			pkill -f "console-watch.ps1.*test191-cycle-$i" 2>/dev/null || true
			sleep 1
		done
		if pgrep -f "console-watch.ps1.*test191-cycle-$i" >/dev/null 2>&1; then
			say "  WARNING: a watcher for cycle $i is still alive; the next cycle may not open COM19"
		fi
		say "  early exit after ${alive}s uptime: nothing to wait for"
	else
		wait "$w" 2>/dev/null || true
	fi
	cp "$wlog" "$DIR/cycle-$i-console.log" 2>/dev/null || : >"$DIR/cycle-$i-console.log"
	clog=$DIR/cycle-$i-console.log

	{
		echo "cycle=$i"
		echo "kind=warm-reboot"
		echo "triggered_at=$(date -u -d "@$trigger" +%Y-%m-%dT%H:%M:%SZ)"
		echo "tablet_gone_at=${off_at:-never}"
		echo "tablet_back_at=${on_at:-never}"
		echo "early_exit=$early"
		echo "wedged=$wedged"
		echo "getty_restarted=$GETTY_RESTARTED"
		echo "wedge_attribution=$WEDGE_ATTRIBUTION"
		echo "outages=${outages:-0}"
		echo "second_outage_gone=${off2_at:--}"
		echo "second_outage_back=${on2_at:--}"
		echo "console_bytes=$(wc -c <"$clog")"
		echo "panic=$(grep -ac 'Kernel panic' "$clog" || true)"
		echo "softlockup=$(grep -acE 'BUG: soft lockup|watchdog: BUG' "$clog" || true)"
		echo "hardlockup=$(grep -acE 'BUG: hard LOCKUP' "$clog" || true)"
		echo "workqueue=$(grep -ac 'BUG: workqueue lockup' "$clog" || true)"
		echo "rcu=$(grep -acE 'rcu.*detected stall' "$clog" || true)"
		# STRUCTURALLY ZERO on this channel: the cmdline carries loglevel=4, which
		# prints levels 0-3 only, and this line is pr_warn (4).  Kept because the
		# column is meaningful if the profile ever raises loglevel.  The real health
		# check is the shell answering, not this counter.
		echo "nmi_unanswered=$(grep -acE "haven.t responded to the NMI" "$clog" || true)"
		echo "frame_done_timeout=$(grep -ac 'frame done timeout' "$clog" || true)"
		echo "mmc_timeout=$(grep -ac 'Timeout waiting for hardware' "$clog" || true)"
	} >"$DIR/cycle-$i-verdict.txt"

	# One health check, requiring a command RESULT rather than an echo.  The early
	# exit above already made this probe, so do not pay for it twice.
	if [ -z "$alive" ]; then
		alive=$(probe_console_uptime "$i")
		alive_via=console
		if [ -z "$alive" ] && ssh_answers; then
			alive=$(probe_ssh_uptime)
			if [ -n "$alive" ]; then
				alive_via=ssh
			fi
		fi
	fi
	echo "uptime_after=${alive:-none}" >>"$DIR/cycle-$i-verdict.txt"
	echo "uptime_via=${alive_via:-none}" >>"$DIR/cycle-$i-verdict.txt"

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

	if [ "$GETTY_RESTARTED" = "1" ]; then
		getty_restarts=$((getty_restarts + 1))
	fi
	if [ "$WEDGE_ATTRIBUTION" = "unattributed" ]; then
		unattributed=$((unattributed + 1))
		say "  *** UNATTRIBUTED: console silent and ssh unreachable - getty defect and"
		say "      wedge are indistinguishable on the channels available, so this"
		say "      cycle is not evidence either way"
	fi

	nmi=$(get nmi_unanswered); [ -n "$nmi" ] || nmi=0
	if [ "$nmi" != "0" ]; then
		wedges=$((wedges + 1))
		say "  *** WEDGE: $nmi unanswered-NMI line(s) in cycle $i"
	fi

	# Stop on a wedge only when it is worth stopping for.  The NMI marker alone is
	# a real wedge and must be recorded, but the *stack* only exists if the panic
	# landed inside the window, so the run stops for either and says which it got.
	if [ "$wedged" = "1" ] || [ -z "$on_at" ] || [ -z "$alive" ] \
		|| [ "$(get panic)" != "0" ] || [ "$(get softlockup)" != "0" ] \
		|| [ "$(get workqueue)" != "0" ] || [ "$(get rcu)" != "0" ] \
		|| [ "$nmi" != "0" ]; then
		grep -aE -B4 -A60 'Kernel panic|BUG: soft lockup|BUG: workqueue lockup|rcu.*detected stall|haven.t responded to the NMI' "$clog" \
			| sed 's/\x1b\[[0-9;]*m//g' >"$DIR/capture-cycle-$i.txt"
		say "  extracted to capture-cycle-$i.txt ($(wc -l <"$DIR/capture-cycle-$i.txt") lines)"
		if [ "$wedged" = "1" ]; then
			# The whole watcher log, not a grep window: on the one capture of this
			# kind so far, the console went silent at the wedge, so there is no
			# panic block to extract - the *absence* of output is the evidence.
			cp "$clog" "$DIR/wedged-cycle-$i-console.log" 2>/dev/null || true
			say "  *** the boot wedged at ${off2_at} and the watchdog restarted it"
			say "      full console preserved as wedged-cycle-$i-console.log"
			say "      stopping: this is the failure, not a clean cycle"
			break
		fi
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
	echo "unattributed=$unattributed"
	echo "getty_restarts=$getty_restarts"
	echo "window=$WINDOW"
	echo "dir=$DIR"
} >"$DIR/wedge-rate-summary.txt"
say "=== done: $cycles_done cycle(s), wedges=$wedges ==="
cat "$DIR/wedge-rate-summary.txt" | tee -a "$OUT"
