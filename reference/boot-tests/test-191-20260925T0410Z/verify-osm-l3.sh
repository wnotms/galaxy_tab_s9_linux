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

mkdir -p "$(dirname "$WINDIR" 2>/dev/null)" 2>/dev/null || true

# One compound command.  `dmesg` needs no privilege here - the shell is root - and
# `2>/dev/null` keeps a restricted dmesg from turning the probe into a no-op.
read -r -d '' CMDS <<'EOS' || true
echo PB
echo boot_id=$(cat /proc/sys/kernel/random/boot_id)
echo uptime=$(cut -d" " -f1 /proc/uptime)
echo release=$(uname -r)
echo --_icc_providers
for d in 1500000 24100000 17d90000 1600000 1680000 16c0000 16e0000 1700000 1780000 320c0000; do
  printf 'icc_%s=%s\n' "$d" "$(ls -d /sys/bus/platform/devices/$d.interconnect/driver 2>/dev/null | wc -l)"
done
echo --_cpufreq
echo cpufreq_driver=$(ls -d /sys/bus/platform/devices/17d91000.cpufreq/driver 2>/dev/null | wc -l)
echo policies=$(ls -d /sys/devices/system/cpu/cpufreq/policy* 2>/dev/null | wc -l)
for p in /sys/devices/system/cpu/cpufreq/policy*; do
  [ -d "$p" ] || continue
  printf 'policy_%s cpus=%s gov=%s min=%s max=%s cur=%s\n' \
    "$(basename "$p")" \
    "$(cat "$p/related_cpus" 2>/dev/null | tr ' ' ',')" \
    "$(cat "$p/scaling_governor" 2>/dev/null)" \
    "$(cat "$p/cpuinfo_min_freq" 2>/dev/null)" \
    "$(cat "$p/cpuinfo_max_freq" 2>/dev/null)" \
    "$(cat "$p/scaling_cur_freq" 2>/dev/null)"
done
echo --_energy_model
for p in /sys/devices/system/cpu/cpufreq/policy*; do
  [ -d "$p/energy_model" ] && printf 'em_%s=present\n' "$(basename "$p")" || true
done
echo --_deferred
echo deferred=$(cat /sys/kernel/debug/devices_deferred 2>/dev/null | wc -l)
echo deferred_list=$(tr '\n' '|' < /sys/kernel/debug/devices_deferred 2>/dev/null)
echo --_counters
echo icc_paths_msg=$(dmesg 2>/dev/null | grep -ac "Failed to find icc paths")
echo osm_hw_disabled=$(dmesg 2>/dev/null | grep -ac "error hardware not enabled")
echo gcc_pending_cpufreq=$(dmesg 2>/dev/null | grep -ac "sync_state() pending due to 17d91000.cpufreq")
echo defer_pending_cpufreq=$(dmesg 2>/dev/null | grep -ac "17d91000.cpufreq: deferred probe pending")
echo --_dmesg
dmesg 2>/dev/null | grep -aE "osm-l3|epss|cpufreq|cpufreq-hw|energy_model|OPP|opp" | head -40
echo --_dt
echo icc_of=$(tr -d '\0' < /proc/device-tree/interconnect@17d90000/compatible 2>/dev/null | tr '\n' ',')
echo icc_status=$(tr -d '\0' < /proc/device-tree/interconnect@17d90000/status 2>/dev/null)
echo END
EOS

echo "probing $PORT -> $RAW"
timeout 400 "$CR" -Out "$WINDIR\\test191-verify.log" -Port "$PORT" \
	-WaitReadySeconds "$READY" -ReadSeconds 30 -Commands "$CMDS" >"$RAW" 2>&1
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
			|| echo "WARN governor is not schedutil: $(grep -a '^policy_' "$RAW" | tr -d '\r' | head -3)"
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
	echo "see $RAW and ${OUT}-raw.txt"
} >>"$VERDICT"

cat "$VERDICT"
