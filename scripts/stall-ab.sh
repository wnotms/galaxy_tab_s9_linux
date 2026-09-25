#!/usr/bin/env bash
# X710 GPU / ACD / RPMh stall A/B harness.
#
# Runs the pre-agreed profiles of docs/GPU_GMU_RPMH_STALL_PLAN.md §7 and
# summarises one table per round, so a profile comparison is a diff of two
# summary files instead of a re-reading of raw console logs.
#
# Profiles (each one token apart, see boot/cmdline.stall-ab-*.example.txt):
#
#	baseline   profile A  no extra token
#	no-acd     profile B  msm.disable_acd=1
#	no-gpu     profile C  msm.skip_gpu=1
#	late-deferred  profile G  deferred_probe_timeout=300
#
# Profile G moves the deferred-probe-timeout burst (~14.3 s) out of the stall
# window without changing which devices are deferred, separating "the
# whole-system re-probe + sync_state burst" from "the GPU specifically".
#
# Profiles only change vendor_boot.img: boot.img (kernel + DTB) and
# init_boot.img (initramfs) must be identical across them, or the A/B is not an
# A/B.  All profiles must be built from one kernel and one initramfs.
#
# SAFETY: this script never flashes and never writes a partition or the BCB.
# It issues reboots over the USB shell console, and only when
# GTS9_ALLOW_POWER=1.  Without that variable it runs the preflight and exits.
#
# Usage:
#	scripts/stall-ab.sh baseline 5
#	scripts/stall-ab.sh no-acd 5
#	scripts/stall-ab.sh no-gpu 5
#	scripts/stall-ab.sh late-deferred 5
#	GTS9_ALLOW_POWER=1 scripts/stall-ab.sh baseline 5
#
#	scripts/stall-ab.sh --summary              # table over whatever was run
set -uo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
CR=$REPO/scripts/console-run.sh
CW=$REPO/scripts/console-watch.sh
SHELL_PORT=${GTS9_SHELL_PORT:-COM17}
CONSOLE_PORT=${GTS9_CONSOLE_PORT:-COM19}
ALLOW=${GTS9_ALLOW_POWER:-0}
WINDOW=${GTS9_WINDOW:-150}
READY=${GTS9_READY:-240}
RESULTS=${GTS9_AB_RESULTS:-$REPO/out/stall-ab}

say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { say "FATAL: $*" >&2; exit 1; }

count_in() { local n; n=$(grep -a -c -E "$2" "$1" 2>/dev/null); printf '%s' "${n:-0}"; }

# First monotonic timestamp of an anomaly class, or "none".
first_ts() {
	grep -a -o -E "\[ *[0-9]+\.[0-9]+\][^\n]*($2)" "$1" 2>/dev/null \
		| head -1 | sed -E 's/^\[ *([0-9]+\.[0-9]+)\].*/\1/'
}

# The anomaly classes the investigation needs, in the order they are reported.
# Each entry is "key|extended-regex".  Kept in one place so the summary file,
# the comparison table and the host test all agree on the definitions.
ANOMALIES=(
	'soft_lockup|soft lockup'
	'hung_task|hung task|task .* blocked for more than'
	'rcu_stall|rcu:.*(detected stall|self-detected stall)'
	'workqueue_stall|workqueue: .*(stall|BUG: workqueue)'
	'rpmh_timeout|rpmh_write_batch'
	'rpmh_active_only|ACTIVE_ONLY'
	'dpu_frame_timeout|frame done timeout'
	'mmc_timeout|mmc[0-9]+: .*[Tt]imeout|mmc.*timeout'
	'gpu_acd_aoss|Unable to send ACD state to AOSS'
	'gpu_device_link|Unable to drop a managed device link reference'
	'gpu_acd_skipped|Skipping GPU ACD probe'
	'gpu_dummy_reg|supply vdd(cx)? not found, using dummy regulator'
	'disp_rcg_stale|rcg didn.t update its configuration'
	'panic|Kernel panic'
	'watchdog_reboot|watchdog: .*reboot|gts9-watchdog-debug'
)

usage() {
	cat >&2 <<'EOF'
usage: stall-ab.sh PROFILE ROUNDS
       stall-ab.sh --summary
PROFILE is one of: baseline, no-acd, no-gpu, late-deferred
EOF
	exit 2
}

summary_table() {
	shopt -s nullglob
	local rows=("$RESULTS"/*/round-*.txt)
	shopt -u nullglob
	if [ ${#rows[@]} -eq 0 ]; then
		echo "no rounds recorded under $RESULTS"
		return 0
	fi
	local keys="profile round boot_id kernel_release stall rpmh rcu wq dpu mmc"
	echo "profile    round  stall  rpmh  rcu  wq  dpu  mmc  first_anomaly        boot_id"
	echo "---------  -----  -----  ----  ---  --  ---  ---  -------------------  --------"
	for r in $(printf '%s\n' "${rows[@]}" | sort); do
		local p rn
		p=$(sed -n 's/^profile=//p' "$r" | head -1)
		rn=$(sed -n 's/^round=//p' "$r" | head -1)
		printf '%-9s  %-5s  %-5s  %-4s  %-3s  %-2s  %-3s  %-3s  %-19s  %s\n' \
			"${p:-?}" "${rn:-?}" \
			"$(sed -n 's/^stall=//p' "$r" | head -1)" \
			"$(sed -n 's/^rpmh_timeout=//p' "$r" | head -1)" \
			"$(sed -n 's/^rcu_stall=//p' "$r" | head -1)" \
			"$(sed -n 's/^workqueue_stall=//p' "$r" | head -1)" \
			"$(sed -n 's/^dpu_frame_timeout=//p' "$r" | head -1)" \
			"$(sed -n 's/^mmc_timeout=//p' "$r" | head -1)" \
			"$(sed -n 's/^first_anomaly=//p' "$r" | head -1)" \
			"$(sed -n 's/^boot_id_after=//p' "$r" | head -1 | cut -c1-8)"
	done
	echo
	echo "stall = soft_lockup + hung_task + rcu_stall + workqueue_stall (any watchdog-visible wedge)"
}

run_probe() {
	local tag=$1 out=$2 winlog=$3
	timeout 500 "$CR" \
		-Out "$winlog" -Port "$SHELL_PORT" \
		-WaitReadySeconds "$READY" -ReadSeconds 30 \
		-Commands 'echo PB;echo boot_id=$(cat /proc/sys/kernel/random/boot_id);echo uptime=$(cut -d" " -f1 /proc/uptime);echo release=$(uname -r);echo cmdline=$(cat /proc/cmdline);echo gpu=$(ls -d /sys/bus/platform/devices/3d00000.gpu 2>/dev/null | wc -l);echo gpu_driver=$(basename $(readlink -f /sys/bus/platform/devices/3d00000.gpu/driver 2>/dev/null) 2>/dev/null || echo NONE);echo aoss_driver=$(basename $(readlink -f /sys/bus/platform/devices/c300000.power-management/driver 2>/dev/null) 2>/dev/null || echo NONE);echo gmu_node=$(ls -d /sys/bus/platform/devices/3d6a000.gmu 2>/dev/null | wc -l);echo gpu_devfreq=$(cat /sys/bus/platform/devices/3d00000.gpu/devfreq/3d00000.gpu/cur_freq 2>/dev/null || echo none);echo gpu_gov=$(cat /sys/bus/platform/devices/3d00000.gpu/devfreq/3d00000.gpu/governor 2>/dev/null || echo none);echo deferred=$(cat /sys/kernel/debug/devices_deferred 2>/dev/null | wc -l);echo wd=$(cat /proc/sys/kernel/watchdog) slp=$(cat /proc/sys/kernel/softlockup_panic) htp=$(cat /proc/sys/kernel/hung_task_panic);echo ctrl=$(cat /sys/class/tty/console/active);echo failed=$(systemctl --failed --no-pager --plain 2>/dev/null | grep -c "loaded failed");echo msm_params=$(ls /sys/module/msm/parameters/ 2>/dev/null | tr "\n" ",");echo apps_rsc_irq=$(grep -E apps_rsc /proc/interrupts 2>/dev/null | tr -s " " | sed "s/^ //" | cut -d" " -f2);echo aoss_qmp_irq=$(grep -E aoss-qmp /proc/interrupts 2>/dev/null | tr -s " " | sed "s/^ //" | cut -d" " -f2);echo panel_status=$(ls /sys/class/drm/*/status 2>/dev/null | wc -l):$(cat /sys/class/drm/card*-DSI-1/status 2>/dev/null | head -1);echo usb_state=$(cat /sys/class/udc/a600000.usb/state 2>/dev/null);echo "--- prev boot anomaly lines";journalctl -b -1 -k -o short-monotonic --no-pager 2>/dev/null | grep -a -E "soft lockup|hung task|rcu:.*stall|workqueue: .*stall|rpmh_write_batch|ACTIVE_ONLY|frame done timeout|mmc.*[Tt]imeout|Unable to send ACD|Unable to drop a managed|Skipping GPU ACD|rcg didn|Kernel panic" | head -80;echo "--- prev boot tail";journalctl -b -1 -o short-monotonic --no-pager 2>/dev/null | tail -5' \
		>"$out" 2>&1
	:
}

# --- main -------------------------------------------------------------------

if [ "${1:-}" = "--summary" ]; then
	summary_table
	exit 0
fi

PROFILE=${1:-}; ROUNDS=${2:-5}
case "$PROFILE" in baseline|no-acd|no-gpu|late-deferred) ;; *) usage ;; esac
case "$ROUNDS" in ''|*[!0-9]*) usage ;; esac
[ "$ROUNDS" -ge 1 ] || usage

CMDLINE=$REPO/boot/cmdline.stall-ab-$PROFILE.example.txt
[ -f "$CMDLINE" ] || die "missing profile file: $CMDLINE"

# The A/B must not silently run the wrong profile: the token that distinguishes
# this profile has to be in the file, and the other profile's token must not be.
case "$PROFILE" in
	baseline)
		grep -q 'msm.disable_acd' "$CMDLINE" && die "baseline must not carry msm.disable_acd"
		grep -q 'msm.skip_gpu' "$CMDLINE" && die "baseline must not carry msm.skip_gpu"
		grep -q 'deferred_probe_timeout' "$CMDLINE" && die "baseline must not carry deferred_probe_timeout" ;;
	no-acd)
		grep -q 'msm.disable_acd=1' "$CMDLINE" || die "no-acd profile lacks msm.disable_acd=1"
		grep -q 'msm.skip_gpu' "$CMDLINE" && die "no-acd must not carry msm.skip_gpu"
		grep -q 'deferred_probe_timeout' "$CMDLINE" && die "no-acd must not carry deferred_probe_timeout" ;;
	no-gpu)
		grep -q 'msm.skip_gpu=1' "$CMDLINE" || die "no-gpu profile lacks msm.skip_gpu=1"
		grep -q 'msm.disable_acd' "$CMDLINE" && die "no-gpu must not carry msm.disable_acd"
		grep -q 'deferred_probe_timeout' "$CMDLINE" && die "no-gpu must not carry deferred_probe_timeout" ;;
	late-deferred)
		grep -q 'deferred_probe_timeout=300' "$CMDLINE" || die "late-deferred profile lacks deferred_probe_timeout=300"
		grep -q 'msm.skip_gpu' "$CMDLINE" && die "late-deferred must not carry msm.skip_gpu"
		grep -q 'msm.disable_acd' "$CMDLINE" && die "late-deferred must not carry msm.disable_acd" ;;
esac
grep -q 'msm.separate_gpu_kms=1' "$CMDLINE" || die "every profile keeps msm.separate_gpu_kms=1"
grep -q 'gts9_watchdog_debug=1' "$CMDLINE" || die "every profile keeps the watchdog detectors"
grep -q 'console=ttyGS1' "$CMDLINE" || die "every profile keeps the ttyGS1 kernel console"
for forbidden in gts9_kmsg_mirror gts9_dpu_flight gts9_rpmh_debug gts9_poweroff_trace; do
	grep -q "$forbidden" "$CMDLINE" && die "$forbidden must be absent from an A/B profile (observer effect)"
done

WINDIR="C:\\gts9-work\\stall-ab\\$PROFILE"
LOCALDIR=/mnt/c/gts9-work/stall-ab/$PROFILE
DIR=$RESULTS/$PROFILE
mkdir -p "$DIR" "$LOCALDIR" 2>/dev/null || true

OUT=$DIR/ab-$PROFILE.txt
say "stall A/B profile=$PROFILE rounds=$ROUNDS allow_power=$ALLOW window=${WINDOW}s" | tee -a "$OUT"
say "cmdline file: ${CMDLINE#$REPO/}" | tee -a "$OUT"

# Preflight: confirm which profile the tablet actually booted with, before
# spending rounds on it.
pre=$DIR/preflight.txt
run_probe preflight "$DIR/preflight-raw.txt" "$WINDIR\\preflight.log"
grep -aE "RECV  (PB|boot_id=|uptime=|release=|gpu=|gpu_driver=|aoss_driver=|gmu_node=|gpu_devfreq=|gpu_gov=|deferred=|wd=|ctrl=|failed=|msm_params=|apps_rsc_irq=|aoss_qmp_irq=|panel_status=|usb_state=)" \
	"$DIR/preflight-raw.txt" >"$pre" 2>/dev/null
cat "$pre" 2>/dev/null | tee -a "$OUT"

# Every `msm.<name>=` token in the profile must be a parameter the kernel really
# registered.  This is the check that was missing, and its absence is why the
# no-gpu profile shipped for two rounds with `msm.no_gpu=1` - a name that appears
# only in MODULE_PARM_DESC and is NOT settable.  The failure mode is silent: the
# kernel ignores an unknown parameter, the boot looks identical to baseline, and
# the A/B reports a false negative for the whole subsystem under test.
#
# Reading /sys/module/msm/parameters/ cannot be fooled by a wrong name, which is
# exactly why it is the authority here rather than the source or modinfo.
got_cmdline=$(grep -a -m1 'cmdline=' "$DIR/preflight-raw.txt" 2>/dev/null)
got_params=$(sed -n 's/^.*RECV  msm_params=//p' "$DIR/preflight-raw.txt" 2>/dev/null | tail -1)
if [ -n "$got_params" ]; then
	bad=""
	for tok in $(tr ' ' '\n' <"$CMDLINE" | grep -oE '^msm\.[a-z_]+=' | sort -u); do
		name=${tok#msm.}
		name=${name%=}
		case ",$got_params," in
		*",$name,"*) ;;
		*) bad="$bad $tok" ;;
		esac
	done
	if [ -n "$bad" ]; then
		say "FATAL: the profile sets parameters this kernel does not have:$bad"
		say "       the kernel would ignore them silently and this A/B would prove nothing."
		say "       registered msm parameters: $got_params"
		die "profile $PROFILE sets unknown msm parameters:$bad"
	fi
	say "preflight: every msm.* token in the profile is a registered parameter"
else
	say "WARNING: could not read /sys/module/msm/parameters/ - the unknown-parameter"
	say "         guard did NOT run, and a typo in a profile would go unnoticed"
fi
case "$PROFILE" in
	baseline)
		grep -aq 'msm.disable_acd=1' <<<"$got_cmdline" && say "WARNING: tablet cmdline has disable_acd but profile is baseline"
		grep -aq 'msm.skip_gpu=1' <<<"$got_cmdline" && say "WARNING: tablet cmdline has skip_gpu but profile is baseline" ;;
	no-acd) grep -aq 'msm.disable_acd=1' <<<"$got_cmdline" || say "WARNING: tablet cmdline lacks msm.disable_acd=1" ;;
	no-gpu) grep -aq 'msm.skip_gpu=1' <<<"$got_cmdline" || say "WARNING: tablet cmdline lacks msm.skip_gpu=1" ;;
esac

if [ "$ALLOW" != "1" ]; then
	say "dry run: nothing was rebooted.  Set GTS9_ALLOW_POWER=1 to run $ROUNDS rounds."
	say "when you do, this script will: capture $CONSOLE_PORT for ${WINDOW}s, issue"
	say "'systemctl reboot' on $SHELL_PORT, then read journalctl -b -1 for the metrics."
	exit 0
fi

boot_id=$(sed -n 's/.*boot_id=//p' "$pre" | head -1 | tr -d '\r')
[ -n "$boot_id" ] || die "no shell on $SHELL_PORT"

for i in $(seq 1 "$ROUNDS"); do
	say "=== $PROFILE round $i/$ROUNDS (boot_id before=$boot_id) ===" | tee -a "$OUT"

	# Console capture spans shutdown, boot and the 13-14 s window.
	timeout $((WINDOW + 200)) "$CW" \
		-Out "$WINDIR\\console-$i.log" -Seconds "$WINDOW" -Port "$CONSOLE_PORT" \
		>"$DIR/console-$i-watch.txt" 2>&1 &
	conpid=$!
	sleep 2
	timeout 300 "$CW" \
		-Out "$WINDIR\\shell-$i.log" -Seconds 60 -Port "$SHELL_PORT" \
		-Command 'systemctl reboot' -CommandAtSeconds 6 \
		2>&1 | grep -aE "SENT|PRESENCE usb" | tail -3 | tee -a "$OUT"
	wait "$conpid" 2>/dev/null || true

	klog=$DIR/console-$i.log
	cp "$LOCALDIR/console-$i.log" "$klog" 2>/dev/null || say "WARNING: no console capture for round $i"

	run_probe "$i" "$DIR/probe-$i-raw.txt" "$WINDIR\\probe-$i.log"
	grep -aE "RECV  (PB|boot_id=|uptime=|release=|gpu=|gpu_driver=|aoss_driver=|gmu_node=|gpu_devfreq=|gpu_gov=|deferred=|wd=|ctrl=|failed=|apps_rsc_irq=|aoss_qmp_irq=|panel_status=|usb_state=|\[ *[0-9]+\.|--- )" \
		"$DIR/probe-$i-raw.txt" >"$DIR/probe-$i.txt" 2>/dev/null

	new_id=$(sed -n 's/.*boot_id=//p' "$DIR/probe-$i.txt" 2>/dev/null | head -1 | tr -d '\r')

	# Per-round summary.  Counts come from the *kernel console capture* where it
	# exists because that is the only channel that survives a panic; the journal
	# probe is the cross-check.
	src=$klog
	[ -s "$src" ] || src=$DIR/probe-$i.txt

	{
		echo "profile=$PROFILE"
		echo "round=$i"
		echo "boot_id_before=$boot_id"
		echo "boot_id_after=${new_id:-none}"
		# The brief is explicit that a warm reboot must never be presented as a
		# cold boot.  This harness only ever issues `systemctl reboot`, so every
		# round it records is a warm reboot, and it says so in the record rather
		# than leaving the reader to infer it.  A panic reboot is a *different*
		# event and is counted separately, by `stall` and by whether the tablet
		# came back twice.
		echo "reboot_kind=warm"
		echo "probe_after_reboot=$([ -n "$new_id" ] && echo ok || echo failed)"
		echo "cmdline_file=boot/cmdline.stall-ab-$PROFILE.example.txt"
		echo "release=$(sed -n 's/.*release=//p' "$DIR/probe-$i.txt" | head -1 | tr -d '\r')"
		echo "console_log=$klog"
		echo "journal_probe=$DIR/probe-$i.txt"
		# GPU/GMU/AOSS probe state (from the post-boot probe, not the capture).
		for f in gpu gpu_driver aoss_driver gmu_node gpu_devfreq gpu_gov deferred \
			apps_rsc_irq aoss_qmp_irq panel_status usb_state; do
			echo "$f=$(sed -n "s/.*$f=//p" "$DIR/probe-$i.txt" | head -1 | tr -d '\r' | cut -d' ' -f1)"
		done
		echo "watchdog=$(sed -n 's/.*wd=//p' "$DIR/probe-$i.txt" | head -1 | tr -d '\r')"
		echo "console_active=$(sed -n 's/.*ctrl=//p' "$DIR/probe-$i.txt" | head -1 | tr -d '\r')"
		echo "failed_units=$(sed -n 's/.*failed=//p' "$DIR/probe-$i.txt" | head -1 | tr -d '\r')"
		# Anomaly classes.
		for spec in "${ANOMALIES[@]}"; do
			key=${spec%%|*}; re=${spec#*|}
			echo "$key=$(count_in "$src" "$re")"
		done
		echo "stall=$(( $(count_in "$src" 'soft lockup') + $(count_in "$src" 'hung task|task .* blocked for more than') + $(count_in "$src" 'rcu:.*stall') + $(count_in "$src" 'workqueue: .*stall') ))"
		echo "first_anomaly=$(first_ts "$src" 'soft lockup|hung task|rcu:.*stall|workqueue: .*stall|rpmh_write_batch|frame done timeout|mmc.*[Tt]imeout|Kernel panic|Unable to send ACD|Unable to drop a managed')"
		echo "rpmh_callers=$(grep -a -o -E 'rpmh_write_batch.*' "$src" 2>/dev/null | head -3 | tr '\n' ';')"
	} >"$DIR/round-$i.txt"

	grep -aE "^(release|reboot_kind|gpu_driver|aoss_driver|gmu_node|gpu_devfreq|gpu_gov|apps_rsc_irq|aoss_qmp_irq|panel_status|deferred|stall|rpmh_timeout|soft_lockup|first_anomaly|boot_id_after|failed_units)=" \
		"$DIR/round-$i.txt" | sed 's/^/  /' | tee -a "$OUT"

	[ -n "$new_id" ] && boot_id=$new_id
	if grep -aq "shell never answered\|could not open" "$DIR/probe-$i-raw.txt" 2>/dev/null; then
		say "round $i: the tablet did not come back; stopping (operator action needed)" | tee -a "$OUT"
		break
	fi
done

say "stall A/B done: profile=$PROFILE rounds=$ROUNDS" | tee -a "$OUT"
say "summarise with: scripts/stall-ab.sh --summary" | tee -a "$OUT"
summary_table | tee -a "$OUT"
