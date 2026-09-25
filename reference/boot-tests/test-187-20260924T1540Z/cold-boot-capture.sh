#!/usr/bin/env bash
# test-187: capture a COLD BOOT (operator power-cycles the tablet).
#
# A cold boot cannot be issued from the host — it needs the power button. Every
# other measurement in this round is a warm reboot, and a warm reboot leaves DRAM
# and the ramoops region intact across the reset, so a failure that depends on
# cold-boot state would not appear in any of them. See
# on-device/COLD-BOOT-GAP.md.
#
# The protocol is deliberately: capture FIRST, then the operator power-cycles.
# Starting the capture afterwards would miss the very transition under test.
#
#   reference/boot-tests/test-187-*/cold-boot-capture.sh          # dry run
#   GTS9_ALLOW_POWER=1 reference/boot-tests/test-187-*/cold-boot-capture.sh
#
# SAFETY: this script issues NO reboot of any kind. It opens a console capture and
# tells the operator to power-cycle the tablet by hand. It never flashes and never
# writes a partition. The `GTS9_ALLOW_POWER=1` gate is required only so a capture
# cannot start by accident.
set -uo pipefail

REPO=$(cd "$(dirname "$0")/../../.." && pwd)
D=$(cd "$(dirname "$0")" && pwd)
CR=$REPO/scripts/console-run.sh
CW=$REPO/scripts/console-watch.sh
ALLOW=${GTS9_ALLOW_POWER:-0}
WINDOW=${GTS9_COLD_WINDOW:-900}
WINDIR='C:\gts9-work\cold-boot'
LOCAL=/mnt/c/gts9-work/cold-boot
CONSOLE_PORT=${GTS9_CONSOLE_PORT:-COM19}

mkdir -p "$LOCAL"
OUT=$D/cold-boot-capture.txt
say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$OUT"; }

if [ "$ALLOW" != "1" ]; then
	say "dry run: would open a ${WINDOW}s capture on $CONSOLE_PORT and wait for YOU to"
	say "power-cycle the tablet. Set GTS9_ALLOW_POWER=1 to actually start it."
	say ""
	say "protocol:"
	say "  1. this script starts the capture and prints GO"
	say "  2. you hold power until the screen goes off, then power on"
	say "  3. the capture runs for ${WINDOW}s; the script then reads the device's"
	say "     own previous-boot verdict if the tablet came back"
	exit 0
fi

say "=== cold-boot capture ($WINDOW s) on $CONSOLE_PORT ==="
say "capture starts NOW; power-cycle the tablet after the GO line"

# Raise kernel verbosity first, while the tablet is still up and reachable, so the
# shutdown side of the cold boot is as visible as the warm boots were.
timeout 200 "$CR" \
	-Out "$WINDIR\\pre.log" -Port "${GTS9_SHELL_PORT:-COM17}" -WaitReadySeconds 200 -ReadSeconds 60 \
	-Commands 'echo "before=$(cat /proc/sys/kernel/printk)"; echo 8 > /proc/sys/kernel/printk; echo "after=$(cat /proc/sys/kernel/printk)"; echo COLD_PREP_DONE' \
	>"$D/cold-boot-pre.txt" 2>&1
say "loglevel: $(grep -aoE 'after=[0-9. ]+' "$D/cold-boot-pre.txt" | tail -1)"

# Capture BEFORE the power cycle. 10 s of lead so the port is definitely open.
say "GO - power-cycle the tablet now"
timeout $((WINDOW + 60)) "$CW" \
	-Out "$WINDIR\\cold.log" \
	-Seconds "$WINDOW" -Port "$CONSOLE_PORT" >"$D/cold-boot-watch.txt" 2>&1

cp "$LOCAL/cold.log" "$D/cold-boot-console.log" 2>/dev/null || say "WARNING: no capture file"

{
	echo "kind=cold-boot (operator power-cycle)"
	echo "window_s=$WINDOW"
	echo "console_bytes=$(wc -c <"$D/cold-boot-console.log" 2>/dev/null || echo 0)"
	echo "console_lines=$(wc -l <"$D/cold-boot-console.log" 2>/dev/null || echo 0)"
	echo "panic_lines=$(grep -ac 'Kernel panic' "$D/cold-boot-console.log" 2>/dev/null || echo 0)"
	echo "softlockup_lines=$(grep -acE 'BUG: soft lockup|watchdog: BUG' "$D/cold-boot-console.log" 2>/dev/null || echo 0)"
	echo "hardlockup_lines=$(grep -acE 'BUG: hard LOCKUP|Hard LOCKUP' "$D/cold-boot-console.log" 2>/dev/null || echo 0)"
	echo "hungtask_lines=$(grep -acE 'hung_task|blocked for more than' "$D/cold-boot-console.log" 2>/dev/null || echo 0)"
	echo "rcu_lines=$(grep -acE 'rcu.*detected stall|rcu.*starved' "$D/cold-boot-console.log" 2>/dev/null || echo 0)"
	echo "panel_recovery_lines=$(grep -ac 'ana38407 panel id' "$D/cold-boot-console.log" 2>/dev/null || echo 0)"
	echo "deferred_burst_lines=$(grep -ac 'deferred probe pending' "$D/cold-boot-console.log" 2>/dev/null || echo 0)"
} >"$D/cold-boot-verdict.txt"
cat "$D/cold-boot-verdict.txt" | sed 's/^/  /' | tee -a "$OUT"

# Read the tablet's own verdict for the boot that just ended, if it came back.
timeout 400 "$CR" \
	-Out "$WINDIR\\post.log" -Port "${GTS9_SHELL_PORT:-COM17}" -WaitReadySeconds 300 -ReadSeconds 90 \
	-Commands 'R=/tmp/cold-post.txt; D=$(ls -1d /var/log/gts9-boot-evidence/*/ 2>/dev/null | tail -1); { echo "EVIDDIR=$D"; cat "$D/verdict.txt" 2>/dev/null; echo "UP=$(cut -d" " -f1 /proc/uptime)"; } > $R 2>&1; cat $R' \
	>"$D/cold-boot-post-raw.txt" 2>&1
sed -n 's/.*RECV  //p' "$D/cold-boot-post-raw.txt" \
	| grep -aE '^(EVIDDIR|previous_boot_end|marker_|UP=)' \
	>"$D/cold-boot-post.txt"

say "=== post-boot device verdict ==="
cat "$D/cold-boot-post.txt" 2>/dev/null | sed 's/^/  /' | tee -a "$OUT"
say "done; compare against the warm baseline: burst 14.304 s, panel recovery ~4.7 s,"
say "clean shutdown ~61 s, systemd-shutdown present, sync_state 29-31 lines"
