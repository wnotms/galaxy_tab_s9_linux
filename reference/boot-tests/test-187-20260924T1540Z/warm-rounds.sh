#!/usr/bin/env bash
# test-187: run one profile as a series of warm reboots and collect the stall
# metrics per round.
#
# This is deliberately NOT scripts/stall-ab.sh. That harness is the
# full-featured one (console capture on COM19 plus a journal probe) and its
# PowerShell calls exceed a comfortable timeout on this console, which is slow:
# a single command round-trips in ~60-70 s here. This runner keeps every step to
# one short command and writes the result to a file on the device, then reads it
# back with `cat`, so nothing depends on parsing a long echoed line.
#
# HONEST LABELLING: every round here is a WARM REBOOT (`systemctl reboot`), not a
# cold boot. The brief forbids passing one off as the other, so the round records
# carry `kind=warm-reboot` and no cold-boot claim is made anywhere. A cold boot
# needs a physical power cycle, which the operator must perform.
#
# SAFETY: reboots only with GTS9_ALLOW_POWER=1. Never flashes, never writes a
# partition.
#
#   reference/boot-tests/test-187-*/warm-rounds.sh baseline 5
#   GTS9_ALLOW_POWER=1 reference/boot-tests/test-187-*/warm-rounds.sh baseline 5
set -uo pipefail

PROFILE=${1:?usage: warm-rounds.sh <baseline|no-acd|no-gpu|late-deferred> <rounds>}
ROUNDS=${2:-5}
REPO=$(cd "$(dirname "$0")/../../.." && pwd)
D=$(cd "$(dirname "$0")" && pwd)
PS=powershell.exe
CR=$REPO/scripts/console-run.ps1
PORT=${GTS9_SHELL_PORT:-COM17}
ALLOW=${GTS9_ALLOW_POWER:-0}
OUT=$D/warm-rounds-$PROFILE.txt
DIR=$D/warm-rounds-$PROFILE
WINDIR='C:\gts9-work\stall-ab\warm'

mkdir -p "$DIR"

say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$OUT"; }

# One short command; the device writes the report itself so the console only has
# to carry a filename.
probe() {
	local tag=$1
	local log="$WINDIR\\probe-$tag.log"
	timeout 420 "$PS" -NoProfile -ExecutionPolicy Bypass -File "$CR" \
		-Out "$log" -Port "$PORT" -WaitReadySeconds 240 -ReadSeconds 90 \
		-Commands 'R=/tmp/gts9-r.txt; { echo "REL=$(uname -r)"; echo "BID=$(cat /proc/sys/kernel/random/boot_id)"; echo "UP=$(cut -d" " -f1 /proc/uptime)"; echo "GPU=$(readlink -f /sys/bus/platform/devices/3d00000.gpu/driver 2>/dev/null | xargs -r basename)"; echo "DEF=$(wc -l < /sys/kernel/debug/devices_deferred)"; echo "SL=$(journalctl -b -k --no-pager 2>/dev/null | grep -c "soft lockup")"; echo "HT=$(journalctl -b -k --no-pager 2>/dev/null | grep -c "hung task")"; echo "RCU=$(journalctl -b -k --no-pager 2>/dev/null | grep -c "rcu.*stall")"; echo "WQ=$(journalctl -b -k --no-pager 2>/dev/null | grep -c "workqueue.*stall")"; echo "RPMH=$(journalctl -b -k --no-pager 2>/dev/null | grep -c "rpmh_write_batch")"; echo "DPU=$(journalctl -b -k --no-pager 2>/dev/null | grep -c "frame done timeout")"; echo "MMC=$(journalctl -b -k --no-pager 2>/dev/null | grep -c "Timeout waiting for hardware cmd")"; echo "BURST=$(journalctl -b -k --no-pager 2>/dev/null | grep -c "deferred probe pending")"; echo "ACD=$(dmesg 2>/dev/null | grep -c "Unable to send ACD")"; echo "DROP=$(dmesg 2>/dev/null | grep -c "Unable to drop a managed")"; echo "FIRST=$(journalctl -b -k --no-pager 2>/dev/null | grep -oE "^\[ *[0-9]+\.[0-9]+\]" | tail -1 | tr -d "[] ")"; echo "FAILED=$(systemctl --failed --no-pager --plain 2>/dev/null | grep -c "loaded failed")"; } > $R 2>&1; cat $R' \
		>"$DIR/probe-$tag-raw.txt" 2>&1
	# Pull the key=value lines out of the captured text.
	sed -n 's/.*RECV  //p' "$DIR/probe-$tag-raw.txt" \
		| grep -aE '^(REL|BID|UP|GPU|DEF|SL|HT|RCU|WQ|RPMH|DPU|MMC|BURST|ACD|DROP|FIRST|FAILED)=' \
		>"$DIR/probe-$tag.txt"
}

pre=$(probe preflight)
cat "$DIR/probe-preflight.txt" 2>/dev/null | tee -a "$OUT"

case "$PROFILE" in
	baseline) want='' ;;
	no-acd) want='msm.disable_acd=1' ;;
	no-gpu) want='msm.no_gpu=1' ;;
	late-deferred) want='deferred_probe_timeout=300' ;;
	*) echo "unknown profile: $PROFILE" >&2; exit 2 ;;
esac

if [ "$ALLOW" != "1" ]; then
	say "dry run: probe only, nothing rebooted. Set GTS9_ALLOW_POWER=1 to run $ROUNDS warm rounds."
	exit 0
fi

for i in $(seq 1 "$ROUNDS"); do
	say "=== $PROFILE warm round $i/$ROUNDS ==="
	timeout 300 "$PS" -NoProfile -ExecutionPolicy Bypass -File "$CR" \
		-Out "$WINDIR\\reboot-$i.log" -Port "$PORT" -WaitReadySeconds 120 -ReadSeconds 25 \
		-Commands 'systemctl reboot' >"$DIR/reboot-$i-raw.txt" 2>&1
	sleep 75

	probe "$i" || true
	{
		echo "profile=$PROFILE"
		echo "round=$i"
		echo "kind=warm-reboot"
		cat "$DIR/probe-$i.txt" 2>/dev/null
	} >"$DIR/round-$i.txt"
	say "round $i: $(grep -aE '^(BID|UP|GPU|SL|RCU|WQ|RPMH|DPU|MMC|BURST|ACD|DROP)=' "$DIR/round-$i.txt" 2>/dev/null | tr '\n' ' ')"
done

say "done: $PROFILE"
cat "$DIR"/round-*.txt 2>/dev/null | grep -aE '^(profile|round|kind|BID|GPU|SL|RCU|WQ|RPMH|BURST|ACD|DROP)='
