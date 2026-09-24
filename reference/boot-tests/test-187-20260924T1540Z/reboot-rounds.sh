#!/usr/bin/env bash
# test-187: simple sequential warm-reboot rounds with retries.
#
# Why this exists next to warm-rounds.sh: this console is slow (a command
# round-trips in ~60-70 s) and COM17 is exclusive, so a single failed open
# silently poisons a whole series. This runner
#   - opens the port once per step, never concurrently,
#   - retries a failed open instead of recording an empty round,
#   - writes the probe output to a file on the device and reads it back with
#     `cat`, so nothing depends on parsing a long echoed command line,
#   - records `kind=warm-reboot` on every round.
#
# HONEST LABELLING: these are WARM REBOOTS, not cold boots. A cold boot needs a
# physical power cycle. No cold-boot claim is made.
#
#   reference/boot-tests/test-187-*/reboot-rounds.sh baseline 5
#   GTS9_ALLOW_POWER=1 reference/boot-tests/test-187-*/reboot-rounds.sh baseline 5
set -uo pipefail

PROFILE=${1:?usage: reboot-rounds.sh <profile> <rounds>}
ROUNDS=${2:-5}
REPO=$(cd "$(dirname "$0")/../../.." && pwd)
D=$(cd "$(dirname "$0")" && pwd)
CR=$REPO/scripts/console-run.ps1
PS=${GTS9_POWERSHELL:-powershell.exe}
PORT=${GTS9_SHELL_PORT:-COM17}
ALLOW=${GTS9_ALLOW_POWER:-0}
DIR=$D/rounds-$PROFILE
WIN='C:\gts9-work\stall-ab\rr'
OUT=$D/rounds-$PROFILE.txt
mkdir -p "$DIR" /mnt/c/gts9-work/stall-ab/rr

say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$OUT"; }

# Run one console command with retries on a failed open.
# $1 tag  $2 commands  $3 rawfile  $4 max_attempts
console() {
	local tag=$1 cmds=$2 raw=$3 tries=${4:-3} n=1
	while [ "$n" -le "$tries" ]; do
		timeout 420 "$PS" -NoProfile -ExecutionPolicy Bypass -File "$CR" \
			-Out "$WIN\\$tag-$n.log" -Port "$PORT" \
			-WaitReadySeconds 240 -ReadSeconds 90 \
			-Commands "$cmds" >"$raw" 2>&1
		if ! grep -aq "could not open\|send failed" "$raw"; then
			return 0
		fi
		say "  $tag attempt $n: port busy/failed, retrying after 20s"
		sleep 20
		n=$((n + 1))
	done
	return 1
}

PROBE_CMDS='R=/tmp/gts9-probe.txt; { echo "REL=$(uname -r)"; echo "BID=$(cat /proc/sys/kernel/random/boot_id)"; echo "UP=$(cut -d" " -f1 /proc/uptime)"; echo "GPU=$(readlink -f /sys/bus/platform/devices/3d00000.gpu/driver 2>/dev/null | xargs -r basename)"; echo "DEF=$(wc -l < /sys/kernel/debug/devices_deferred)"; echo "SL=$(journalctl -b -k --no-pager 2>/dev/null | grep -c "soft lockup")"; echo "HT=$(journalctl -b -k --no-pager 2>/dev/null | grep -c "hung task")"; echo "RCU=$(journalctl -b -k --no-pager 2>/dev/null | grep -c "rcu.*stall")"; echo "RPMH=$(journalctl -b -k --no-pager 2>/dev/null | grep -c "rpmh_write_batch")"; echo "DPU=$(journalctl -b -k --no-pager 2>/dev/null | grep -c "frame done timeout")"; echo "MMC=$(journalctl -b -k --no-pager 2>/dev/null | grep -c "Timeout waiting for hardware cmd")"; echo "BURST=$(journalctl -b -k --no-pager 2>/dev/null | grep -c "deferred probe pending")"; echo "ACD=$(dmesg 2>/dev/null | grep -c "Unable to send ACD")"; echo "DROP=$(dmesg 2>/dev/null | grep -c "Unable to drop a managed")"; echo "FAILED=$(systemctl --failed --no-pager --plain 2>/dev/null | grep -c "loaded failed")"; } > $R 2>&1; cat $R'

extract() { sed -n 's/.*RECV  //p' "$1" | grep -aE '^(REL|BID|UP|GPU|DEF|SL|HT|RCU|RPMH|DPU|MMC|BURST|ACD|DROP|FAILED)='; }

say "profile=$PROFILE rounds=$ROUNDS kind=warm-reboot allow_power=$ALLOW"

# --- preflight -------------------------------------------------------------
if console preflight "$PROBE_CMDS" "$DIR/preflight-raw.txt"; then
	extract "$DIR/preflight-raw.txt" >"$DIR/preflight.txt"
else
	say "FATAL: could not run the preflight probe"; exit 1
fi
cat "$DIR/preflight.txt" | tee -a "$OUT"

case "$PROFILE" in
	baseline|no-acd|no-gpu|late-deferred) ;;
	*) say "FATAL: unknown profile $PROFILE"; exit 2 ;;
esac

# Confirm the device is actually running this profile's command line.
gotcmd=$(timeout 300 "$PS" -NoProfile -ExecutionPolicy Bypass -File "$CR" \
	-Out "$WIN\\cmdline.log" -Port "$PORT" -WaitReadySeconds 120 -ReadSeconds 40 \
	-Commands 'cat /proc/cmdline' 2>/dev/null | grep -a "console=ttyMSM0" | tail -1 || true)
case "$PROFILE" in
	baseline)
		grep -q "msm.disable_acd" <<<"$gotcmd" && say "WARNING: device carries msm.disable_acd but profile is baseline"
		grep -q "msm.no_gpu" <<<"$gotcmd" && say "WARNING: device carries msm.no_gpu but profile is baseline" ;;
	no-acd) grep -q "msm.disable_acd=1" <<<"$gotcmd" || say "WARNING: device lacks msm.disable_acd=1" ;;
	no-gpu) grep -q "msm.no_gpu=1" <<<"$gotcmd" || say "WARNING: device lacks msm.no_gpu=1" ;;
	late-deferred) grep -q "deferred_probe_timeout=300" <<<"$gotcmd" || say "WARNING: device lacks deferred_probe_timeout=300" ;;
esac

if [ "$ALLOW" != "1" ]; then
	say "dry run: preflight only, nothing rebooted (set GTS9_ALLOW_POWER=1)"
	exit 0
fi

# --- rounds ----------------------------------------------------------------
for i in $(seq 1 "$ROUNDS"); do
	say "=== round $i/$ROUNDS (warm reboot) ==="
	console "reboot$i" 'systemctl reboot' "$DIR/reboot-$i-raw.txt" 3 || say "  reboot $i: could not issue"
	sleep 70
	if ! console "probe$i" "$PROBE_CMDS" "$DIR/probe-$i-raw.txt" 4; then
		say "  round $i: probe could not run; recording empty"
	fi
	{
		echo "profile=$PROFILE"
		echo "round=$i"
		echo "kind=warm-reboot"
		extract "$DIR/probe-$i-raw.txt" 2>/dev/null
	} >"$DIR/round-$i.txt"
	say "  $(grep -aE '^(BID|UP|GPU|SL|RCU|RPMH|BURST|ACD|DROP)=' "$DIR/round-$i.txt" 2>/dev/null | tr '\n' ' ')"
done

say "=== series complete: $PROFILE ==="
for f in "$DIR"/round-*.txt; do cat "$f"; echo; done | tee -a "$OUT" >/dev/null
grep -aE '^(round|kind|BID|GPU|SL|RCU|RPMH|BURST|ACD|DROP)=' "$DIR"/round-*.txt 2>/dev/null
