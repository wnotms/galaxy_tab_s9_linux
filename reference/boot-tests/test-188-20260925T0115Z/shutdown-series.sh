#!/usr/bin/env bash
# test-188: repeat the shutdown-path series on the CURRENT kernel, and record the
# two facts round 15 introduced that test-187 never looked at.
#
# Why a second series is worth the device time.  The 16 clean shutdown cycles in
# test-187 were all run on the AOSS-QMP + IPCC kernel.  Round 15 then enabled
# CONFIG_HWSPINLOCK_QCOM, which is not a cosmetic change: it unbinds the whole
# SMEM -> smp2p -> ADSP chain, so four more drivers now bind and a remoteproc is
# now registered that did not exist during any of those 16 cycles:
#
#   remoteproc0 -> adsp state=offline   (qcom_q6v5_pas bound, firmware absent)
#
# The failure this round is chasing lives in the SHUTDOWN path, so a change to
# which drivers participate in shutdown invalidates the old series as evidence
# about the current kernel.  This runner re-establishes it, on profile A, with no
# cmdline change and no flash.
#
# It also records two things test-187 did not:
#
#   CTXFAULTS / CTXSID  the early arm-smmu context faults.  Round 15's write-up
#                       attributed these to the ADSP; the fault's own SID field
#                       says SID=0x1c00, which sm8550.dtsi gives to
#                       `mdss: display-subsystem@ae00000`, not to the ADSP.  The
#                       per-boot count is recorded here so the claim is testable
#                       instead of asserted.
#   ADSP                remoteproc presence and state, so "the ADSP is registered
#                       but offline" is measured each round rather than assumed.
#
# SAFETY: `systemctl reboot` and a printk console level. Nothing else. No flash,
# no partition write, no voltage change. Requires GTS9_ALLOW_POWER=1.
#
#   reference/boot-tests/test-188-*/shutdown-series.sh            # dry run
#   GTS9_ALLOW_POWER=1 GTS9_ROUNDS=6 reference/boot-tests/test-188-*/shutdown-series.sh
set -uo pipefail

REPO=$(cd "$(dirname "$0")/../../.." && pwd)
D=$(cd "$(dirname "$0")" && pwd)
CR=$REPO/scripts/console-run.sh
CW=$REPO/scripts/console-watch.sh
SHELL_PORT=${GTS9_SHELL_PORT:-COM17}
CONSOLE_PORT=${GTS9_CONSOLE_PORT:-COM19}
ALLOW=${GTS9_ALLOW_POWER:-0}
ROUNDS=${GTS9_ROUNDS:-6}
# 300 s was enough for the test-187 series: ~61 s to shut down plus a warm boot
# that reaches a shell in about a minute on this microSD.
WINDOW=${GTS9_WINDOW:-300}
WINDIR=${GTS9_WINDIR:-'C:\gts9-work\test188'}
LOCAL=${GTS9_LOCALDIR:-/mnt/c/gts9-work/test188}
OUT=$D/shutdown-series.txt

mkdir -p "$LOCAL"
say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$OUT"; }

# One command, short enough to survive this slow console. The device writes the
# report itself and the console only has to carry the filename back.
PROBE='R=/tmp/gts9-t188.txt; { echo "REL=$(uname -r)"; echo "BID=$(cat /proc/sys/kernel/random/boot_id)"; echo "UP=$(cut -d" " -f1 /proc/uptime)"; echo "GPU=$(readlink -f /sys/bus/platform/devices/3d00000.gpu/driver 2>/dev/null | xargs -r basename)"; echo "DEF=$(wc -l < /sys/kernel/debug/devices_deferred)"; echo "CTXFAULTS=$(dmesg 2>/dev/null | grep -ac "Unhandled context fault")"; echo "CTXSID=$(dmesg 2>/dev/null | grep -ao "SID=0x[0-9a-f]*" | sort -u | tr "\n" ",")"; echo "ADSP=$(cat /sys/class/remoteproc/remoteproc0/state 2>/dev/null || echo none)"; echo "PFW=$(dmesg 2>/dev/null | grep -ac "request_firmware failed")"; echo "ACD=$(dmesg 2>/dev/null | grep -ac "Unable to send ACD")"; echo "DROP=$(dmesg 2>/dev/null | grep -ac "Unable to drop a managed")"; echo "RCGWARN=$(dmesg 2>/dev/null | grep -ac "rcg didn.t update")"; echo "SL=$(journalctl -b -k --no-pager 2>/dev/null | grep -v "Kernel command line" | grep -c "soft lockup")"; echo "HT=$(journalctl -b -k --no-pager 2>/dev/null | grep -v "Kernel command line" | grep -c "hung task")"; echo "RCU=$(journalctl -b -k --no-pager 2>/dev/null | grep -v "Kernel command line" | grep -c "rcu.*stall")"; echo "WQ=$(journalctl -b -k --no-pager 2>/dev/null | grep -v "Kernel command line" | grep -c "BUG: workqueue lockup")"; echo "RPMH=$(journalctl -b -k --no-pager 2>/dev/null | grep -v "Kernel command line" | grep -c "rpmh_write_batch")"; echo "DPU=$(journalctl -b -k --no-pager 2>/dev/null | grep -v "Kernel command line" | grep -c "frame done timeout")"; echo "MMC=$(journalctl -b -k --no-pager 2>/dev/null | grep -v "Kernel command line" | grep -c "Timeout waiting for hardware cmd")"; echo "BURST=$(journalctl -b -k --no-pager 2>/dev/null | grep -v "Kernel command line" | grep -c "deferred probe pending")"; echo "FAILED=$(systemctl --failed --no-pager --plain 2>/dev/null | grep -c "loaded failed")"; } > $R 2>&1; cat $R'

pull() { sed -n 's/.*RECV  //p' "$1" | grep -aE '^[A-Z]+='; }

# A round is only usable if the probe EXECUTED. An echo with no command output is
# the stall state itself, not a clean round - see test-187/on-device/STALL-SIGNATURE.md.
LIVE='echo GTS9_ALIVE_$(cut -d" " -f1 /proc/uptime)_END'

probe_round() {
	local tag=$1 live_raw=$D/live-$1.txt
	local a
	for a in 1 2 3 4 5; do
		timeout 420 "$CR" -Port "$SHELL_PORT" -Out "$WINDIR\\live-$tag-$a.log" \
			-WaitReadySeconds 300 -ReadSeconds 20 -Commands "$LIVE" >"$live_raw" 2>&1
		if grep -aq 'GTS9_ALIVE_[0-9]' "$live_raw"; then break; fi
		say "  liveness $tag attempt $a: no command output (echo-only = stalled, or still booting)"
		sleep 45
	done
	if ! grep -aq 'GTS9_ALIVE_[0-9]' "$live_raw"; then
		say "  *** NO COMMAND EVER EXECUTED for $tag - treating as STALLED"
		return 1
	fi
	timeout 420 "$CR" -Port "$SHELL_PORT" -Out "$WINDIR\\probe-$tag.log" \
		-WaitReadySeconds 240 -ReadSeconds 40 -Commands "$PROBE" >"$D/probe-$tag-raw.txt" 2>&1
	pull "$D/probe-$tag-raw.txt" >"$D/probe-$tag.txt"
	[ -s "$D/probe-$tag.txt" ]
}

# --- dry run ---------------------------------------------------------------
if [ "$ALLOW" != "1" ]; then
	say "dry run: would run $ROUNDS warm-reboot shutdown cycles on $SHELL_PORT,"
	say "capturing $CONSOLE_PORT for ${WINDOW}s across each shutdown+boot."
	say "No flash, no cmdline change. Set GTS9_ALLOW_POWER=1 to actually run it."
	probe_round preflight && { say "current state:"; cat "$D/probe-preflight.txt" | sed 's/^/  /'; }
	exit 0
fi

say "=== test-188 shutdown series: rounds=$ROUNDS window=${WINDOW}s kind=warm-reboot ==="

if ! probe_round preflight; then
	say "FATAL: no executing shell before the series; refusing to start"; exit 1
fi
say "preflight:"; cat "$D/probe-preflight.txt" | sed 's/^/  /' | tee -a "$OUT"
bid_prev=$(sed -n 's/^BID=//p' "$D/probe-preflight.txt" | head -1)

for i in $(seq 1 "$ROUNDS"); do
	say "=== shutdown round $i/$ROUNDS ==="

	# Full kernel verbosity so the shutdown side is visible on COM19. Panic text
	# is KERN_EMERG and would print anyway; this is for the messages above it.
	timeout 200 "$CR" -Port "$SHELL_PORT" -Out "$WINDIR\\pre-$i.log" \
		-WaitReadySeconds 200 -ReadSeconds 45 \
		-Commands 'echo "before=$(cat /proc/sys/kernel/printk)"; echo 8 > /proc/sys/kernel/printk; echo "after=$(cat /proc/sys/kernel/printk)"; echo LVL_SET' \
		>"$D/shutdown-$i-pre.txt" 2>&1
	say "  loglevel: $(grep -aoE 'after=[0-9. ]+' "$D/shutdown-$i-pre.txt" | tail -1)"

	# Capture COM19 only. Holding COM17 for the capture would block the very
	# trigger this script needs - that is what produced empty captures in round 8.
	timeout $((WINDOW + 120)) "$CW" -Out "$WINDIR\\console-$i.log" \
		-Seconds "$WINDOW" -Port "$CONSOLE_PORT" >"$D/shutdown-$i-w19.txt" 2>&1 &
	w=$!
	sleep 8

	timeout 200 "$CR" -Port "$SHELL_PORT" -Out "$WINDIR\\trigger-$i.log" \
		-WaitReadySeconds 120 -ReadSeconds 15 \
		-Commands 'echo TRIGGER_SHUTDOWN; systemctl reboot' >"$D/shutdown-$i-trigger.txt" 2>&1
	say "  triggered at $(date -u +%H:%M:%S)"
	wait "$w" 2>/dev/null || true

	clog=$LOCAL/console-$i.log
	cp "$clog" "$D/shutdown-$i-console.log" 2>/dev/null || say "  WARNING: no console capture"
	grep -ac . "$D/shutdown-$i-console.log" >/dev/null 2>&1 || : >"$D/shutdown-$i-console.log"

	{
		echo "round=$i"
		echo "kind=warm-reboot"
		echo "console_bytes=$(wc -c <"$D/shutdown-$i-console.log" 2>/dev/null || echo 0)"
		echo "console_lines=$(wc -l <"$D/shutdown-$i-console.log" 2>/dev/null || echo 0)"
		echo "panic_lines=$(grep -ac 'Kernel panic' "$D/shutdown-$i-console.log" 2>/dev/null || echo 0)"
		echo "softlockup_lines=$(grep -acE 'BUG: soft lockup|watchdog: BUG' "$D/shutdown-$i-console.log" 2>/dev/null || echo 0)"
		echo "hardlockup_lines=$(grep -acE 'BUG: hard LOCKUP|Hard LOCKUP' "$D/shutdown-$i-console.log" 2>/dev/null || echo 0)"
		echo "hungtask_lines=$(grep -acE 'hung_task|blocked for more than' "$D/shutdown-$i-console.log" 2>/dev/null || echo 0)"
		echo "rcu_lines=$(grep -acE 'rcu.*detected stall|rcu.*starved' "$D/shutdown-$i-console.log" 2>/dev/null || echo 0)"
		echo "calltrace_lines=$(grep -ac 'Call trace' "$D/shutdown-$i-console.log" 2>/dev/null || echo 0)"
		echo "systemd_shutdown_seen=$(grep -ac 'systemd-shutdown' "$D/shutdown-$i-console.log" 2>/dev/null || echo 0)"
		echo "connection_terminated=$(grep -ac 'Connection terminated' "$D/shutdown-$i-console.log" 2>/dev/null || echo 0)"
		echo "sd_shutting_down=$(grep -ac 'Shutting down' "$D/shutdown-$i-console.log" 2>/dev/null || echo 0)"
		echo "ctxfault_lines=$(grep -ac 'Unhandled context fault' "$D/shutdown-$i-console.log" 2>/dev/null || echo 0)"
		echo "burst_lines=$(grep -ac 'deferred probe pending' "$D/shutdown-$i-console.log" 2>/dev/null || echo 0)"
	} >"$D/shutdown-$i-verdict.txt"
	cat "$D/shutdown-$i-verdict.txt" | sed 's/^/  /' | tee -a "$OUT"

	if grep -aq "Kernel panic\|BUG: soft lockup\|BUG: hard LOCKUP\|rcu.*detected stall" "$D/shutdown-$i-console.log" 2>/dev/null; then
		echo "verdict=PANIC-OR-LOCKUP-CAPTURED" >>"$D/shutdown-$i-verdict.txt"
		say "  *** PANIC/LOCKUP CAPTURED on the shutdown path"
	elif [ "$(sed -n 's/^systemd_shutdown_seen=//p' "$D/shutdown-$i-verdict.txt")" = "0" ] && \
	     [ "$(sed -n 's/^sd_shutting_down=//p' "$D/shutdown-$i-verdict.txt")" != "0" ]; then
		echo "verdict=SHUTDOWN-HUNG-NO-PANIC" >>"$D/shutdown-$i-verdict.txt"
		say "  *** SHUTDOWN STARTED AND NEVER REACHED systemd-shutdown, WITH NO PANIC"
	elif [ "$(sed -n 's/^systemd_shutdown_seen=//p' "$D/shutdown-$i-verdict.txt")" != "0" ]; then
		echo "verdict=clean" >>"$D/shutdown-$i-verdict.txt"
		say "  shutdown completed normally"
	else
		echo "verdict=unknown-capture-empty" >>"$D/shutdown-$i-verdict.txt"
		say "  WARNING: capture shows neither a shutdown nor a panic - inspect, do not call it clean"
	fi

	if ! probe_round "$i"; then
		say "  *** round $i did not come back with an executing shell - stopping"
		echo "status=stalled-or-no-shell" >>"$D/shutdown-$i-verdict.txt"
		break
	fi
	cp "$D/probe-$i.txt" "$D/probe-$i-round.txt" 2>/dev/null || true
	say "  post-round: $(grep -aE '^(BID|UP|GPU|DEF|CTXFAULTS|ADSP|ACD|RPMH|BURST)=' "$D/probe-$i.txt" | tr '\n' ' ')"

	bid_now=$(sed -n 's/^BID=//p' "$D/probe-$i.txt" | head -1)
	if [ -n "$bid_prev" ] && [ "$bid_now" = "$bid_prev" ]; then
		echo "status=stale-boot" >>"$D/shutdown-$i-verdict.txt"
		say "  WARNING: boot_id did not change - the reboot did not happen; round is stale"
		break
	fi
	bid_prev=$bid_now
done

say "=== series complete ==="
printf '%-6s %-8s %-10s %-8s %-8s %-8s\n' round verdict sd_shut panic ctxfault adsp | tee -a "$OUT"
for i in $(seq 1 "$ROUNDS"); do
	[ -f "$D/shutdown-$i-verdict.txt" ] || continue
	printf '%-6s %-8s %-10s %-8s %-8s %-8s\n' "$i" \
		"$(sed -n 's/^verdict=//p' "$D/shutdown-$i-verdict.txt")" \
		"$(sed -n 's/^systemd_shutdown_seen=//p' "$D/shutdown-$i-verdict.txt")" \
		"$(sed -n 's/^panic_lines=//p' "$D/shutdown-$i-verdict.txt")" \
		"$(sed -n 's/^CTXFAULTS=//p' "$D/probe-$i.txt" 2>/dev/null)" \
		"$(sed -n 's/^ADSP=//p' "$D/probe-$i.txt" 2>/dev/null)" | tee -a "$OUT"
done
