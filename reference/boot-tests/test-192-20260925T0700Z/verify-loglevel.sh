#!/usr/bin/env bash
# test-192: is the console now able to see the level-4 marker?
#
# The whole point of the profile is that `console_loglevel` must be 7.  This
# checks that directly, and then checks the consequence that does not need a
# failure: with the filter lifted, the console record should begin near monotonic 0
# and carry level-6 lines, where the loglevel=4 record began at 4.4 s with only
# level 0-3 lines.
#
# It is read-only: nothing is written, nothing is rebooted, nothing is flashed.
#
#   reference/boot-tests/test-192-*/verify-loglevel.sh
set -uo pipefail

D=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$D/../../.." && pwd)
CR=$REPO/scripts/console-run.sh

PORT=${GTS9_SHELL_PORT:-COM17}
WINDIR=${GTS9_WINDIR:-'C:\Users\ms\AppData\Local\Temp\gts9-wedge'}
OUT=${GTS9_OUT:-$D/verify-$(date -u +%Y%m%dT%H%M%SZ)}
RAW=$OUT-raw.txt
VERDICT=$OUT-verdict.txt

# One line, `;` separated, no single quotes: the same rule every other probe in
# this repository follows, for the same bash -> PowerShell quoting reason.
PROBE='echo PB'
PROBE+=';echo boot_id=$(cat /proc/sys/kernel/random/boot_id)'
PROBE+=';echo uptime=$(cut -d" " -f1 /proc/uptime)'
PROBE+=';echo printk=$(cat /proc/sys/kernel/printk)'
PROBE+=';echo console_loglevel=$(cut -d" " -f1 /proc/sys/kernel/printk)'
PROBE+=';echo cmdline_loglevel=$(cat /proc/cmdline | tr " " "\n" | grep -c "^loglevel=7$")'
PROBE+=';echo dmesg_lvl6=$(dmesg 2>/dev/null | grep -ac "gts9wifi-sec-log: persistent console at")'
PROBE+=';echo dmesg_calibrate=$(dmesg 2>/dev/null | grep -ac "Calibrating delay loop")'
PROBE+=';echo pstore_dir=$(ls -A /sys/fs/pstore 2>/dev/null | tr "\n" ",")'
PROBE+=';echo pstore_archived=$(ls -A /var/lib/systemd/pstore 2>/dev/null | tr "\n" ",")'
PROBE+=';echo END'

echo "probing $PORT -> $RAW"
timeout 400 "$CR" -Out "$WINDIR\\test192-verify.log" -Port "$PORT" \
	-WaitReadySeconds 60 -ReadSeconds 30 -Commands "$PROBE" >"$RAW" 2>&1
rc=$?

get() { sed -n "s/.*$1=//p" "$RAW" 2>/dev/null | head -1 | tr -d '\r'; }

{
	echo "probe_rc=$rc"
	echo "raw=$RAW"
	for k in boot_id uptime printk console_loglevel cmdline_loglevel \
	         dmesg_lvl6 dmesg_calibrate pstore_dir pstore_archived; do
		echo "$k=$(get "$k")"
	done
	echo "--- verdict"
	if [ "$rc" != 0 ]; then
		echo "FAIL probe did not complete (rc=$rc)"
	elif [ -z "$(get boot_id)" ]; then
		echo "FAIL no boot_id: the shell never answered"
	elif [ "$(get console_loglevel)" = "7" ]; then
		echo "PASS console_loglevel is 7 - level-4 pr_warn now reaches the console"
		[ "$(get cmdline_loglevel)" = "1" ] \
			&& echo "PASS loglevel=7 is on the command line" \
			|| echo "WARN loglevel=7 is not on the command line; /proc/sys/kernel/printk may have been changed at runtime"
		[ "$(get dmesg_lvl6)" -ge 1 ] 2>/dev/null \
			&& echo "PASS a level-6 line is present (sec-log: persistent console at)" \
			|| echo "WARN the sec-log level-6 line is absent from dmesg; check the console record after a reboot"
	else
		echo "FAIL console_loglevel=$(get console_loglevel), expected 7 - the token did not take"
	fi
	echo "--- pstore"
	echo "note: /sys/fs/pstore is normally EMPTY because systemd-pstore moves records"
	echo "      to /var/lib/systemd/pstore before gts9-prev-boot-evidence runs."
} >>"$VERDICT"

cat "$VERDICT"
