#!/usr/bin/env bash
# test-191: does the EPSS L3 provider bind, and does cpufreq probe because of it?
#
# This is the *cheap and definite* half of test 191.  The expensive half is the
# wedge-rate series (wedge-rate.sh), which needs tens of cycles to say anything.
# This one probe answers the narrow question in a single boot:
#
#   did 17d90000.interconnect get a driver, and did 17d91000.cpufreq stop
#   being permanently deferred because of it?
#
# It is read-only: nothing is written, nothing is rebooted, nothing is flashed.
#
#   reference/boot-tests/test-191-*/verify-osm-l3.sh          # probe + verdict
#
# SAFETY: reads only.  The tablet must be up and at the console.
#
# The probe is ONE line with `;` separators, like every proven harness in this
# repository.  console-run.ps1 forwards it with $sp.WriteLine(), and while that
# would carry embedded newlines, each one is a second chance for the bash ->
# PowerShell quoting to mangle the payload.  There is no need: `for ...; do ...;
# done` fits on a line.  No single quotes appear inside the command either, since
# console-run.sh wraps the whole value for PowerShell.
set -uo pipefail

D=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$D/../../.." && pwd)
CR=$REPO/scripts/console-run.sh

PORT=${GTS9_SHELL_PORT:-COM17}
WINDIR=${GTS9_WINDIR:-'C:\Users\ms\AppData\Local\Temp\gts9-wedge'}
OUT=${GTS9_OUT:-$D/verify-$(date -u +%Y%m%dT%H%M%SZ)}
RAW=$OUT-raw.txt
VERDICT=$OUT-verdict.txt
READY=${GTS9_READY_SECONDS:-60}

# dmesg needs no privilege here - the shell is root - and 2>/dev/null keeps a
# restricted dmesg from turning the probe into a no-op.
PROBE='echo PB'
PROBE+=';echo boot_id=$(cat /proc/sys/kernel/random/boot_id)'
PROBE+=';echo uptime=$(cut -d" " -f1 /proc/uptime)'
PROBE+=';echo release=$(uname -r)'
PROBE+=';echo --_icc_providers'
PROBE+=';for d in 1500000 24100000 17d90000 1600000 1680000 16c0000 16e0000 1700000 1780000 320c0000; do printf "icc_%s=%s\n" "$d" "$(ls -d /sys/bus/platform/devices/$d.interconnect/driver 2>/dev/null | wc -l)"; done'
PROBE+=';echo --_cpufreq'
PROBE+=';echo cpufreq_driver=$(ls -d /sys/bus/platform/devices/17d91000.cpufreq/driver 2>/dev/null | wc -l)'
PROBE+=';echo policies=$(ls -d /sys/devices/system/cpu/cpufreq/policy* 2>/dev/null | wc -l)'
PROBE+=';for p in /sys/devices/system/cpu/cpufreq/policy*; do if [ -d "$p" ]; then printf "policy_%s cpus=%s gov=%s min=%s max=%s cur=%s\n" "$(basename "$p")" "$(cat "$p/related_cpus" 2>/dev/null | tr " " ",")" "$(cat "$p/scaling_governor" 2>/dev/null)" "$(cat "$p/cpuinfo_min_freq" 2>/dev/null)" "$(cat "$p/cpuinfo_max_freq" 2>/dev/null)" "$(cat "$p/scaling_cur_freq" 2>/dev/null)"; fi; done'
PROBE+=';echo --_energy_model'
PROBE+=';for p in /sys/devices/system/cpu/cpufreq/policy*; do if [ -d "$p/energy_model" ]; then echo "em_$(basename "$p")=present"; fi; done'
PROBE+=';echo --_deferred'
PROBE+=';echo deferred=$(cat /sys/kernel/debug/devices_deferred 2>/dev/null | wc -l)'
PROBE+=';echo deferred_list=$(tr "\n" "|" < /sys/kernel/debug/devices_deferred 2>/dev/null)'
PROBE+=';echo --_counters'
PROBE+=';echo icc_paths_msg=$(dmesg 2>/dev/null | grep -ac "Failed to find icc paths")'
PROBE+=';echo osm_hw_disabled=$(dmesg 2>/dev/null | grep -ac "error hardware not enabled")'
PROBE+=';echo gcc_pending_cpufreq=$(dmesg 2>/dev/null | grep -ac "sync_state() pending due to 17d91000.cpufreq")'
PROBE+=';echo defer_pending_cpufreq=$(dmesg 2>/dev/null | grep -ac "17d91000.cpufreq: deferred probe pending")'
PROBE+=';echo --_dmesg'
PROBE+=';dmesg 2>/dev/null | grep -aE "osm-l3|epss|cpufreq|energy_model|OPP|opp" | head -40'
PROBE+=';echo --_dt'
PROBE+=';echo icc_of=$(tr -d "\0" < /proc/device-tree/interconnect@17d90000/compatible 2>/dev/null | tr "\n" ",")'
PROBE+=';echo icc_status=$(tr -d "\0" < /proc/device-tree/interconnect@17d90000/status 2>/dev/null)'
PROBE+=';echo END'

echo "probing $PORT -> $RAW"
timeout 400 "$CR" -Out "$WINDIR\\test191-verify.log" -Port "$PORT" \
	-WaitReadySeconds "$READY" -ReadSeconds 30 -Commands "$PROBE" >"$RAW" 2>&1
rc=$?

get() { sed -n "s/.*$1=//p" "$RAW" 2>/dev/null | head -1 | tr -d '\r'; }
have() { [ "$(get "$1")" = "$2" ]; }

{
	echo "probe_rc=$rc"
	echo "raw=$RAW"
	for k in boot_id uptime release cpufreq_driver policies deferred \
	         icc_17d90000 icc_1500000 icc_24100000 \
	         icc_paths_msg osm_hw_disabled gcc_pending_cpufreq defer_pending_cpufreq; do
		echo "$k=$(get "$k")"
	done
	echo "deferred_list=$(get deferred_list)"
	echo "--- policy lines"
	grep -a '^policy_' "$RAW" 2>/dev/null | tr -d '\r'
	echo "--- energy model"
	grep -a '^em_' "$RAW" 2>/dev/null | tr -d '\r'
	echo "--- verdict"
} >"$VERDICT"

# PASS/FAIL against the pre-agreed criteria in candidate.txt.  These are written
# so that a *failure* is informative rather than ambiguous: the osm_hw_disabled
# row distinguishes "the provider has no driver" from "the provider's probe was
# refused by the hardware".
{
	if [ "$rc" != 0 ]; then
		echo "FAIL probe did not complete (rc=$rc)"
	elif [ -z "$(get boot_id)" ]; then
		echo "FAIL no boot_id: the shell never answered"
	else
		have icc_17d90000 1 && echo "PASS 17d90000.interconnect binds" \
			|| echo "FAIL 17d90000.interconnect has no driver"
		have cpufreq_driver 1 && echo "PASS 17d91000.cpufreq binds" \
			|| echo "FAIL 17d91000.cpufreq is still unbound"
		[ "$(get policies)" = "3" ] && echo "PASS 3 cpufreq policies" \
			|| echo "FAIL policies=$(get policies), expected 3"
		grep -qa '^policy_.*gov=schedutil' "$RAW" 2>/dev/null \
			&& echo "PASS governor is schedutil" \
			|| echo "WARN governor is not schedutil: $(grep -a '^policy_' "$RAW" 2>/dev/null | tr -d '\r' | head -3)"
		have defer_pending_cpufreq 0 && echo "PASS cpufreq is no longer on the deferred list" \
			|| echo "FAIL cpufreq still reported deferred"
		have gcc_pending_cpufreq 0 && echo "PASS gcc no longer blocked by cpufreq" \
			|| echo "WARN gcc still names 17d91000.cpufreq as its sync_state blocker"
		if have osm_hw_disabled 0; then
			echo "PASS osm-l3 did not refuse the hardware"
		else
			echo "FAIL osm-l3 said 'error hardware not enabled' - ABL does not enable the EPSS block"
		fi
	fi
	echo "--- raw evidence"
	echo "see $RAW"
} >>"$VERDICT"

cat "$VERDICT"
