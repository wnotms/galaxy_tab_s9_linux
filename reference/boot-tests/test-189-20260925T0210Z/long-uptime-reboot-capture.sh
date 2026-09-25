#!/usr/bin/env bash
# test-189: capture a LONG-UPTIME reboot with the console loglevel raised.
#
# Why. One shutdown on 2026-09-25 sat for ~178 s between
# `systemd-shutdown: Sending SIGTERM to remaining processes...` and the machine
# actually going away, while the next one, 4 minutes later, finished in 0.16 s
# from `reboot.target` to the device disappearing.  Same kernel, same units, same
# USB config; the only correlate is uptime (2936 s against ~70 s).  See
# docs/SLOW_SHUTDOWN_ANALYSIS.md.
#
# The journal cannot see past `Sending SIGTERM` because journald is one of the
# processes being killed there - in BOTH the slow and the fast case - so the
# difference is invisible in it.  systemd-shutdown's own progress lines go to
# /dev/console, which includes ttyGS1, but the console loglevel is 4 and they are
# not printed.  Raising it to 8 and holding COM19 across the shutdown is the whole
# experiment.
#
# This script waits for the uptime that reproduced the slow case before spending
# the reboot, so it does not have to be babysat.
#
#   reference/boot-tests/test-189-*/long-uptime-reboot-capture.sh          # dry run
#   GTS9_ALLOW_POWER=1 reference/boot-tests/test-189-*/long-uptime-reboot-capture.sh
set -uo pipefail

D=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$D/../../.." && pwd)
CW=$REPO/scripts/console-watch.sh
ALLOW=${GTS9_ALLOW_POWER:-0}
MIN_UPTIME=${GTS9_MIN_UPTIME:-2700}
WINDOW=${GTS9_WINDOW:-420}
SSH_KEY=${GTS9_SSH_KEY:-$HOME/.ssh/gts9_ed25519}
DEV=${GTS9_DEVICE:-169.254.42.1}
WINDIR=${GTS9_WINDIR:-'C:\Users\ms\AppData\Local\Temp\gts9-longuptime.log'}
LOCAL=${GTS9_LOCAL:-/mnt/c/Users/ms/AppData/Local/Temp/gts9-longuptime.log}
OUT=$D/long-uptime-reboot-capture.txt

say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$OUT"; }
ssh_() { timeout 30 ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no \
	-o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 "root@$DEV" "$@" 2>/dev/null; }

if [ "$ALLOW" != "1" ]; then
	say "dry run: would wait for uptime >= ${MIN_UPTIME}s on $DEV, raise the console"
	say "loglevel to 8, hold COM19 for ${WINDOW}s across the reboot, and record which"
	say "systemd-shutdown line is last. Set GTS9_ALLOW_POWER=1 to run it."
	exit 0
fi

say "=== waiting for uptime >= ${MIN_UPTIME}s on $DEV ==="
while :; do
	up=$(ssh_ 'cut -d. -f1 /proc/uptime')
	[ -n "$up" ] || { say "  no ssh; retrying"; sleep 60; continue; }
	if [ "$up" -ge "$MIN_UPTIME" ]; then
		say "  uptime is ${up}s - proceeding"
		break
	fi
	if [ $((up % 300)) -lt 60 ]; then say "  uptime ${up}s, waiting"; fi
	sleep 60
done

bid_before=$(ssh_ 'cat /proc/sys/kernel/random/boot_id')
say "boot_id before: $bid_before"

# Raise the console loglevel by SSH rather than over COM17: it is one command, it
# cannot be lost to a busy port, and the console ports stay free for the capture.
say "loglevel: $(ssh_ 'echo "before=$(cat /proc/sys/kernel/printk)"; echo 8 > /proc/sys/kernel/printk; echo "after=$(cat /proc/sys/kernel/printk)"' | tr '\n' ' ')"

say "starting the COM19 capture for ${WINDOW}s"
timeout $((WINDOW + 120)) "$CW" -Out "$WINDIR" -Seconds "$WINDOW" -Port COM19 \
	>"$D/long-uptime-watch.txt" 2>&1 &
w=$!
sleep 6

say "issuing systemctl reboot at $(date -u +%H:%M:%S)"
ssh_ 'systemctl reboot' >/dev/null 2>&1
trigger=$(date -u +%s)

wait "$w" 2>/dev/null || true
cp "$LOCAL" "$D/long-uptime-console.log" 2>/dev/null || say "WARNING: no capture file"

# Wait for the tablet to answer again, and time it: that is the quantity the
# operator noticed.
say "waiting for the tablet to come back"
for _ in $(seq 1 30); do
	up=$(ssh_ 'cut -d. -f1 /proc/uptime')
	if [ -n "$up" ]; then
		now=$(date -u +%s)
		say "back after $((now - trigger))s (uptime ${up}s)"
		ssh_ "echo \"boot_id after: \$(cat /proc/sys/kernel/random/boot_id)\"" | tee -a "$OUT"
		break
	fi
	sleep 15
done

{
	echo "kind=warm-reboot"
	echo "uptime_before_s=$up"
	echo "trigger_to_back_s=$(( $(date -u +%s) - trigger ))"
	echo "capture_bytes=$(wc -c <"$D/long-uptime-console.log" 2>/dev/null || echo 0)"
	echo "systemd_shutdown_lines=$(grep -ac 'systemd-shutdown' "$D/long-uptime-console.log" 2>/dev/null || echo 0)"
} >"$D/long-uptime-verdict.txt"
cat "$D/long-uptime-verdict.txt" | tee -a "$OUT"

say "=== systemd-shutdown lines captured, with the seconds between them ==="
grep -a "systemd-shutdown" "$D/long-uptime-console.log" 2>/dev/null \
	| sed 's/\x1b\[[0-9;]*m//g' | tee -a "$OUT"
say "=== done ==="
