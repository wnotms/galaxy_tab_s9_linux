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
# One identity per invocation.  Round records carry it, so records from two runs
# can never be mistaken for one series - which is exactly what happened on
# 2026-09-25: a 20-round run was started into the directory a 5-round run had
# just filled, and the only reason it was detectable at all was that the earlier
# five had been archived elsewhere.  Nothing in a round record said which run it
# came from.  Same class as the overwritten test-190 capture.
RUN=${GTS9_RUN:-$(date -u +%Y%m%dT%H%M%SZ)}

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
	# The strongest CPU-level signature the three complete wedge records share.
	# `nmi_backtrace.c` prints "After N seconds, these CPUS still haven't
	# responded to the NMI: ..." at pr_warn, so it needs loglevel>=4 to reach a
	# console - but it is `KERN_WARNING` in the ring regardless, which is why the
	# KLOG channel can see it on this build.
	'nmi_unresponsive|haven.t responded to the NMI|still haven.t responded'
	'watchdog_reboot|watchdog: .*reboot|gts9-watchdog-debug'
)

# Anomaly classes that are evidence of a **CPU-level wedge** on their own.  A
# lone DPU, MMC or RPMh timeout is not one of these: test-194's boot printed a
# frame-done timeout and then ran normally for 170 s to a clean restart.  The
# distinction is the whole point of the verdict field below.
# Space-separated: these are iterated as names, so a pipe-joined string would
# loop once over the whole thing and every count would silently read 0.
WEDGE_CLASSES='soft_lockup hung_task rcu_stall workqueue_stall nmi_unresponsive panic'
# Classes that are real signals but not sufficient for a wedge verdict.
#
# `disp_rcg_stale` is deliberately NOT here even though it is a real message:
# it fires exactly once per boot on every boot measured, healthy and wedged alike
# (`docs/X710_EARLY_BOOT_WARNINGS.md` §4), so counting it would make `clean`
# unreachable and turn every round into `suspect`.  A marker that cannot
# discriminate does not belong in a classifier.  It is still counted per channel
# by the ANOMALIES loop, just not scored.
#
# `gpu_dummy_reg` is the same case and is likewise counted but not scored.
SUSPECT_CLASSES='rpmh_timeout rpmh_active_only dpu_frame_timeout mmc_timeout gpu_acd_aoss gpu_device_link'

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
	local keys="run profile round boot_id kernel_release stall rpmh rcu wq dpu mmc"
	echo "run               profile    round  verdict       wedge  susp  boot_id"
	echo "----------------  ---------  -----  ------------  -----  ----  --------"
	for r in $(printf '%s\n' "${rows[@]}" | sort); do
		local p rn
		p=$(sed -n 's/^profile=//p' "$r" | head -1)
		rn=$(sed -n 's/^round=//p' "$r" | head -1)
		printf '%-16s  %-9s  %-5s  %-12s  %-5s  %-4s  %s\n' \
			"$(sed -n 's/^run=//p' "$r" | head -1)" "${p:-?}" "${rn:-?}" \
			"$(sed -n 's/^verdict=//p' "$r" | head -1)" \
			"$(sed -n 's/^wedge_markers=//p' "$r" | head -1)" \
			"$(sed -n 's/^suspect_markers=//p' "$r" | head -1)" \
			"$(sed -n 's/^boot_id_after=//p' "$r" | head -1 | cut -c1-8)"
	done
	echo
	echo "verdict: clean | wedge | suspect | unattributed (see the verdict block)"
	echo "wedge_markers = soft_lockup + hung_task + rcu_stall + workqueue_stall + nmi_unresponsive + panic"
	echo "  a lone DPU/MMC/RPMh timeout is a *suspect* marker and does NOT make a wedge"
}

# --- durable round identity --------------------------------------------------
# Every artifact a round produces - console capture, journal, pstore, USB
# presence trace - is collected by a *different* mechanism at a *different* time,
# and nothing in them says which round they belong to.  test-194 is what that
# costs: the episode's boot could only be identified by re-deriving a host<->
# monotonic clock offset, and an earlier pass analysed the wrong boot entirely
# because `boot_id before` reads like "this round's boot" when it is the previous
# round's result.
#
# So before each reboot the round stamps its identity into two places that
# survive it, and the next boot proves the binding instead of assuming it:
#
#   /dev/kmsg    -> enters the kernel ring, so `journalctl -k -b -1` carries it
#                   and it is bound to the boot that wrote it;
#   /dev/pmsg0   -> the ramoops persistent-message region, write-only, read back
#                   from the *next* boot's pstore copy.  Never read /dev/pmsg0
#                   directly: it fails with EINVAL and the open truncates.
#
# If the binding cannot be proved the round is `unattributed` and no conclusion
# may be drawn from it.
mark_round() {
	local tag=$1
	# Quoting note, because the first version of this got it wrong and the ring
	# recorded the literal text `boot_id=$(cat /proc/sys/kernel/random/boot_id)`:
	# the harness variables (RUN, PROFILE, tag) must expand LOCALLY, while the
	# boot id must be resolved REMOTELY on the tablet.  So the message is built
	# locally into a literal and only `$BID` is left for the remote shell, which
	# is why the remote fragment is double-quoted and not single-quoted.
	local msg="GTS9_AB run=$RUN profile=$PROFILE round=$tag"
	timeout 120 "$CR" -Port "$SHELL_PORT" \
		-Out "$WINDIR\\mark-$tag.log" -WaitReadySeconds "$READY" -ReadSeconds 12 \
		-Commands "BID=\$(cut -c1-8 /proc/sys/kernel/random/boot_id); MSG=\"$msg boot_id=\$BID\"; echo \"\$MSG\" > /dev/kmsg; printf '%s\\n' \"\$MSG\" > /dev/pmsg0; echo MARK_rc=\$?; echo MARK_msg=\"\$MSG\"; echo MARK_sha=\$(printf '%s' \"\$MSG\" | sha256sum | cut -c1-16); echo MARK_rel=\$(uname -r); echo MARK_cmd=\$(sha256sum /proc/cmdline | cut -c1-16)" \
		>"$DIR/mark-$tag-raw.txt" 2>&1
	sed -n 's/.*RECV  MARK_/MARK_/p' "$DIR/mark-$tag-raw.txt" 2>/dev/null >"$DIR/mark-$tag.txt"
	:
}

# Read the binding back from the boot that just ended, and say whether it holds.
# Both halves must agree: the kernel-ring copy names the boot that wrote it, and
# the pmsg copy proves it survived the reboot into the pstore of the next one.
verify_round_identity() {
	local tag=$1
	IDENTITY=missing
	local ring pmsg
	ring=$(sed -n 's/.*RECV  \(GTS9_AB .*\)/\1/p' "$DIR/probe-$tag-raw.txt" 2>/dev/null | tail -1)
	pmsg=$(sed -n 's/.*RECV  \(GTS9_AB .*\)/\1/p' "$DIR/probe-$tag-raw.txt" 2>/dev/null | tail -1)
	echo "identity_ring=${ring:-none}" >>"$DIR/round-$tag-identity.txt"
	echo "identity_pmsg=${pmsg:-none}" >>"$DIR/round-$tag-identity.txt"
	case "$ring" in
	*"run=$RUN profile=$PROFILE round=$tag"*) IDENTITY=verified ;;
	"") IDENTITY=missing ;;
	*) IDENTITY=mismatch ;;
	esac
}

run_probe() {
	local tag=$1 out=$2 winlog=$3
	timeout 500 "$CR" \
		-Out "$winlog" -Port "$SHELL_PORT" \
		-WaitReadySeconds "$READY" -ReadSeconds 30 \
		-Commands 'echo PB;echo boot_id=$(cat /proc/sys/kernel/random/boot_id);echo uptime=$(cut -d" " -f1 /proc/uptime);echo release=$(uname -r);echo cmdline=$(cat /proc/cmdline);echo gpu=$(ls -d /sys/bus/platform/devices/3d00000.gpu 2>/dev/null | wc -l);echo gpu_driver=$(if [ -e /sys/bus/platform/devices/3d00000.gpu/driver ]; then basename $(readlink -f /sys/bus/platform/devices/3d00000.gpu/driver 2>/dev/null); else echo NONE; fi);echo aoss_driver=$(basename $(readlink -f /sys/bus/platform/devices/c300000.power-management/driver 2>/dev/null) 2>/dev/null || echo NONE);echo gmu_node=$(ls -d /sys/bus/platform/devices/3d6a000.gmu 2>/dev/null | wc -l);echo gpu_devfreq=$(cat /sys/bus/platform/devices/3d00000.gpu/devfreq/3d00000.gpu/cur_freq 2>/dev/null || echo none);echo gpu_gov=$(cat /sys/bus/platform/devices/3d00000.gpu/devfreq/3d00000.gpu/governor 2>/dev/null || echo none);echo deferred=$(cat /sys/kernel/debug/devices_deferred 2>/dev/null | wc -l);echo wd=$(cat /proc/sys/kernel/watchdog) slp=$(cat /proc/sys/kernel/softlockup_panic) htp=$(cat /proc/sys/kernel/hung_task_panic);echo ctrl=$(cat /sys/class/tty/console/active);echo failed=$(systemctl --failed --no-pager --plain 2>/dev/null | grep -c "loaded failed");echo msm_params=$(ls /sys/module/msm/parameters/ 2>/dev/null | tr "\n" ",");echo apps_rsc_irq=$(grep -E apps_rsc /proc/interrupts 2>/dev/null | tr -s " " | sed "s/^ //" | cut -d" " -f2);echo aoss_qmp_irq=$(grep -E aoss-qmp /proc/interrupts 2>/dev/null | tr -s " " | sed "s/^ //" | cut -d" " -f2);echo panel_status=$(ls /sys/class/drm/*/status 2>/dev/null | wc -l):$(cat /sys/class/drm/card*-DSI-1/status 2>/dev/null | head -1);echo usb_state=$(cat /sys/class/udc/a600000.usb/state 2>/dev/null);echo "--- IDENTITY (the binding this round claims)";journalctl -b -1 -k --no-pager 2>/dev/null | grep -a "GTS9_AB " | tail -3;echo "--- IDENTITY_PMSG";cat /var/lib/systemd/pstore/pmsg-ramoops-0 2>/dev/null | tr -d "\\0" | grep -a "GTS9_AB " | tail -3;echo "--- BUILDID";echo img_sha=$(sha256sum /boot/vmlinuz 2>/dev/null | cut -c1-16);echo cmdline_sha=$(sha256sum /proc/cmdline | cut -c1-16);echo "--- BOOT_UNDER_TEST";echo "under_test_boot_id=$(journalctl --list-boots --no-pager 2>/dev/null | grep -E \"^ *-1 \" | cut -d\" \" -f3)";echo "current_boot_id=$(cat /proc/sys/kernel/random/boot_id)";echo "boot_count=$(journalctl --list-boots --no-pager 2>/dev/null | wc -l)";echo "boot_list=$(journalctl --list-boots --no-pager 2>/dev/null | tail -4 | cut -c1-40 | tr \"\\n\" \"|\")";echo "--- PREVBOOT_KLOG (every line, tagged)";journalctl -b -1 -k -o short-monotonic --no-pager 2>/dev/null | sed "s/^/KLOG /" | head -3000;echo "--- PREVBOOT_PSTORE (tagged)";cat /var/lib/systemd/pstore/console-ramoops-0 /sys/fs/pstore/console-ramoops-0 2>/dev/null | sed "s/^/PSTORE /" | head -3000;echo "--- prev boot tail";journalctl -b -1 -o short-monotonic --no-pager 2>/dev/null | tail -5' \
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
say "stall A/B run=$RUN profile=$PROFILE rounds=$ROUNDS allow_power=$ALLOW window=${WINDOW}s" | tee -a "$OUT"
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
# The `RECV  ` prefix is load-bearing: the probe's own `SENT` line echoes the
# command text, which contains the literal `cmdline=`, so a bare `grep -m1
# 'cmdline='` matches the echo and never the tablet's answer.  That made the
# cmdline check below compare against a command string, so it reported
# "tablet cmdline lacks msm.skip_gpu=1" on a boot that plainly had it.
got_cmdline=$(grep -a -m1 'RECV  cmdline=' "$DIR/preflight-raw.txt" 2>/dev/null)
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

# Refuse to write a new run on top of an old one.  The summary table globs
# `round-*.txt`, so a mixed directory produces a table that looks like one series
# and is two - and when the earlier run is shorter, its stale tail survives the
# overwrite and is counted as if it were new.
shopt -s nullglob
existing=("$DIR"/round-*.txt)
shopt -u nullglob
if [ ${#existing[@]} -gt 0 ]; then
	other=$(sed -n 's/^run=//p' "${existing[@]}" 2>/dev/null | sort -u | grep -v "^${RUN}$" | head -1)
	if [ -n "$other" ]; then
		if [ "${GTS9_APPEND_RUNS:-0}" = "1" ]; then
			say "WARNING: $DIR already holds run $other; appending run $RUN to it" | tee -a "$OUT"
			say "         the summary table will mix both - run-id is recorded per round" | tee -a "$OUT"
		else
			die "$DIR already holds rounds from run ${other:-<unstamped>}; refusing to mix runs. Move them, or set GTS9_RUN=$other to continue that run, or GTS9_APPEND_RUNS=1 to mix deliberately"
		fi
	fi
fi

for i in $(seq 1 "$ROUNDS"); do
	say "=== $PROFILE round $i/$ROUNDS (boot_id before=$boot_id) ===" | tee -a "$OUT"

	# Stamp the round into /dev/kmsg and /dev/pmsg0 BEFORE the reboot, so both
	# the journal of this boot and the pstore of the next one carry it.  This is
	# the binding that makes console, journal, pstore and USB trace provably one
	# round; without it the round is `unattributed` by construction.
	IDENTITY=missing
	mark_round "$i"
	mark_bid=$(sed -n 's/^MARK_msg=.*boot_id=//p' "$DIR/mark-$i.txt" 2>/dev/null | tail -1)
	say "  marked run=$RUN round=$i on boot ${mark_bid:-?} (kmsg + pmsg)" | tee -a "$OUT"

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
	watch_log=$DIR/console-$i-watch.txt
	cp "$LOCALDIR/console-$i.log" "$klog" 2>/dev/null || say "WARNING: no console capture for round $i"

	run_probe "$i" "$DIR/probe-$i-raw.txt" "$WINDIR\\probe-$i.log"
	grep -aE "RECV  (PB|boot_id=|uptime=|release=|gpu=|gpu_driver=|aoss_driver=|gmu_node=|gpu_devfreq=|gpu_gov=|deferred=|wd=|ctrl=|failed=|apps_rsc_irq=|aoss_qmp_irq=|panel_status=|usb_state=|KLOG |PSTORE |\[ *[0-9]+\.|--- )" \
		"$DIR/probe-$i-raw.txt" >"$DIR/probe-$i.txt" 2>/dev/null

	new_id=$(sed -n 's/.*boot_id=//p' "$DIR/probe-$i.txt" 2>/dev/null | head -1 | tr -d '\r')

	# --- where the anomaly counts may come from, and why ---------------------
	# CORRECTED.  This note first said the COM19 capture holds "zero kernel
	# lines" and that anomaly counts taken from it were structurally 0.  The
	# measurement behind that was a bad regex (`^\[` against lines prefixed with
	# `<host timestamp> RECV  `), and test-194 disproved the conclusion: that
	# capture holds kernel lines, and it carried the `frame done timeout` that
	# opened the episode.  What is true is narrower and still worth acting on:
	# the gadget console only starts delivering once the host has enumerated it,
	# so **early** kernel output (the 0.67 s dummy regulators, the `rcg` message)
	# never appears there, while later messages do.
	#
	# Three channels, three blind spots, so counts come from the two that see the
	# kernel's own log and the third is recorded as coverage:
	#
	#   KLOG    `journalctl -k -b -1` - the whole previous ring, every level,
	#           because `loglevel` filters the consoles and not the ring.  Blind
	#           only if journald itself stops.
	#   PSTORE  the ramoops console - survives the reboot and carries a panic,
	#           which is how every complete failure record in this repo was
	#           captured, but it is a ring the next boot overwrites.
	#   CONSOLE the COM19 capture - userspace and post-enumeration kernel output
	#           only; recorded as `console_kernel_lines` so its coverage is
	#           visible instead of assumed.
	# From the RAW probe file, not the filtered `probe-$i.txt`: the summary grep
	# keeps lines whose text after `RECV  ` is a field or a bare `[time]`, and the
	# tagged lines begin `KLOG [time]`, so the filter drops every one of them.
	# Measured: 966 KLOG lines in the raw file, 0 in the filtered one.
	klog_src=$DIR/probe-$i-raw.txt
	awk '/^[^ ]* *RECV  --- PREVBOOT_KLOG/ {on=1; next} /^[^ ]* *RECV  --- / {on=0} on' \
		"$klog_src" 2>/dev/null | sed 's/^[^ ]* *RECV  //' >"$DIR/klog-$i.txt"
	awk '/^[^ ]* *RECV  --- PREVBOOT_PSTORE/ {on=1; next} /^[^ ]* *RECV  --- / {on=0} on' \
		"$klog_src" 2>/dev/null | sed 's/^[^ ]* *RECV  //' >"$DIR/pstore-$i.txt"
	src=$DIR/klog-$i.txt
	src2=$DIR/pstore-$i.txt
	# Kernel-prefixed lines in the console capture.  The pattern must allow for
	# the `<host timestamp> RECV  ` prefix that console-watch.ps1 writes, or it
	# counts nothing: an earlier version anchored on `^\[`, reported 0 while the
	# capture held 85 kernel lines, and was read as "this channel never carries
	# kernel text" - the opposite of the truth.  Measured on test-194's capture.
	console_kernel_lines=$(grep -acE 'RECV  \[[ ]*[0-9]+\.[0-9]+\]' "$klog" 2>/dev/null || echo 0)

	{
		echo "run=$RUN"
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
		# Anomaly classes, from each kernel channel and labelled with it.
		for spec in "${ANOMALIES[@]}"; do
			key=${spec%%|*}; re=${spec#*|}
			echo "${key}_klog=$(count_in "$src" "$re")"
			echo "${key}_pstore=$(count_in "$src2" "$re")"
		done
		echo "console_kernel_lines=$console_kernel_lines"
		echo "klog_lines=$(wc -l <"$src" 2>/dev/null || echo 0)"
		echo "pstore_lines=$(wc -l <"$src2" 2>/dev/null || echo 0)"
		echo "first_anomaly_pstore=$(first_ts "$src2" 'soft lockup|hung task|rcu:.*stall|workqueue: .*stall|rpmh_write_batch|frame done timeout|mmc.*[Tt]imeout|Kernel panic|Unable to send ACD|Unable to drop a managed')"
		echo "rpmh_callers=$(grep -a -o -E 'rpmh_write_batch.*' "$src" "$src2" 2>/dev/null | head -3 | tr '\n' ';')"
	} >"$DIR/round-$i.txt"

	# --- the verdict ---------------------------------------------------------
	# Four outcomes, and the names are load-bearing: test-194 showed that a
	# console-silence episode with a lone frame-done timeout is NOT a wedge, so
	# `wedge` requires CPU-level or persistent evidence and nothing weaker may
	# reach that name.
	#
	#   clean         new boot_id, shell answered, identity verified, no automatic
	#                 reboot (the round's own reboot is the one the harness
	#                 requested, so it does not count), and no wedge-class marker
	#                 in either kernel channel
	#   wedge         a wedge-class marker, or an unrequested automatic reboot,
	#                 bound to this round's boot id
	#   suspect       real signals - a lone DPU/MMC/RPMh timeout, console silence,
	#                 ssh/ping failure, a stale panel - with no CPU-level or
	#                 persistent evidence
	#   unattributed  the boot or the capture cannot be bound to this round, or
	#                 the probe itself failed; nothing may be concluded from it
	# The binding, read from the boot that just ended.  `identity_ring` is the
	# copy the kernel ring kept, which is what ties the round to the boot that
	# wrote it; `identity_pmsg` is the copy that survived into this boot's pstore.
	ident_ring=$(sed -n 's/.*RECV  \(GTS9_AB .*\)/\1/p' "$DIR/probe-$i-raw.txt" 2>/dev/null | tail -1)
	echo "identity=$ident_ring" >>"$DIR/round-$i.txt"
	# Which boot the klog/pstore evidence actually describes.  A round record
	# carries three different boot ids - the one the marker was written on
	# (`identity`), the one the harness rebooted (`boot_id_before`) and the one
	# running at probe time (`boot_id_after`) - and until test-196 none of them
	# named the boot the kernel log came from.  When an event inserts an extra
	# boot between them, that is the difference between diagnosing the failure
	# and diagnosing the boot before it.
	echo "boot_under_test=$(sed -n 's/.*RECV  under_test_boot_id=//p' "$DIR/probe-$i-raw.txt" 2>/dev/null | tail -1)" >>"$DIR/round-$i.txt"
	case "$ident_ring" in
	*"run=$RUN profile=$PROFILE round=$i"*) IDENTITY=verified ;;
	"") IDENTITY=missing ;;
	*) IDENTITY=mismatch ;;
	esac

	# Read one field back out of the round record that was just written.  This is
	# the seam between "collect the numbers" and "decide what they mean", and it
	# is deliberately a re-read: the verdict then consumes the same text a reader
	# will, so the two cannot drift apart.
	get() { sed -n "s/^$1=//p" "$DIR/round-$i.txt" | head -1; }
	# A missing field must read as 0.  An empty expansion makes the arithmetic
	# below an error rather than a count, and a round that silently fails to
	# classify is worse than one that classifies as clean-but-empty.
	getn() { local v; v=$(get "$1"); case "$v" in ''|*[!0-9]*) echo 0 ;; *) echo "$v" ;; esac; }

	# --- the automatic-reboot field, and the wedge detector ------------------
	# The console capture carries no kernel text *before USB enumeration* (see
	# the channel note above) but it DOES carry the USB presence transitions, and
	# a second outage is the one signal nothing but another restart can produce:
	# the harness issues exactly one `systemctl reboot` per round, so a second
	# outage means something else restarted the tablet - the watchdog, or a
	# panic.  `boot_id_after` cannot serve here, because it differs every round
	# by construction.
	#
	# Measured on the five clean test-193 rounds: exactly 1 False / 2 True each.
	# A wedge shows 2 False / 3 True or more.
	# The console watcher is still running while the probe waits for the shell, so
	# a wedge's own panic-restart lands in this file AFTER the probe returns.
	# Counting before the watcher exits misses exactly the event being looked for:
	# measured on test-195, where the count read 0 while the file already held two
	# outages - the harness's reboot and the panic's restart.  Wait for it first.
	wait "$conpid" 2>/dev/null || true
	read -r p_off p_on p_n <<<"$(tr -d '\r' <"$watch_log" 2>/dev/null | awk '
		/PRESENCE usb0525:a4a7=False/ { n++; if (n==1) f=$1; if (n==2) s=$1 }
		/PRESENCE usb0525:a4a7=True/  { t++; if (t==3) b=$1 }
		END { printf "%s %s %d", (s?s:"-"), (b?b:"-"), n+0 }')"
	echo "presence_outages=${p_n:-0}" >>"$DIR/round-$i.txt"
	echo "automatic_reboot=$(if [ "${p_n:-0}" -ge 2 ]; then echo yes; else echo no; fi)" >>"$DIR/round-$i.txt"
	echo "second_outage_gone=${p_off:--}" >>"$DIR/round-$i.txt"
	echo "second_outage_back=${p_on:--}" >>"$DIR/round-$i.txt"

	wedge_n=0
	for cls in $WEDGE_CLASSES; do
		wedge_n=$((wedge_n + $(getn "${cls}_klog") + $(getn "${cls}_pstore")))
	done
	suspect_n=0
	for cls in $SUSPECT_CLASSES; do
		suspect_n=$((suspect_n + $(getn "${cls}_klog") + $(getn "${cls}_pstore")))
	done
	echo "wedge_markers=$wedge_n" >>"$DIR/round-$i.txt"
	echo "suspect_markers=$suspect_n" >>"$DIR/round-$i.txt"
	echo "stall=$wedge_n" >>"$DIR/round-$i.txt"

	verdict=clean
	[ "${suspect_n:-0}" -gt 0 ] && verdict=suspect
	[ "${p_n:-0}" -ge 2 ] && verdict=wedge
	[ "${wedge_n:-0}" -gt 0 ] && verdict=wedge
	# unattributed outranks everything: an unbound boot makes the rest of the
	# record unreadable, and saying so is more useful than a confident label.
	[ "${IDENTITY:-missing}" != verified ] && verdict=unattributed
	[ -z "$new_id" ] && verdict=unattributed
	[ "$(get probe_after_reboot)" = failed ] && verdict=unattributed
	echo "wedge_class_evidence=$wedge_n" >>"$DIR/round-$i.txt"
	echo "verdict=$verdict" >>"$DIR/round-$i.txt"

	grep -aE "^(release|reboot_kind|verdict|identity|presence_outages|automatic_reboot|wedge_markers|suspect_markers|gpu_driver|aoss_driver|gmu_node|apps_rsc_irq|panel_status|deferred|stall|first_anomaly|boot_id_after|failed_units)=" \
		"$DIR/round-$i.txt" | sed 's/^/  /' | tee -a "$OUT"

	[ -n "$new_id" ] && boot_id=$new_id
	if [ "$verdict" = wedge ]; then
		# Preserve before anything else can overwrite it.  pstore is the only
		# instrument that survives a wedge, the next boot overwrites the console
		# ring, and only one of the four records so far was captured before that
		# happened.  This copies the wedge round's own artifacts - including the
		# raw, untagged pstore - into a `wedge-round-N/` directory so a later
		# round cannot touch them.
		pres=$DIR/wedge-round-$i
		mkdir -p "$pres" 2>/dev/null
		for f in round-$i.txt klog-$i.txt pstore-$i.txt console-$i-watch.txt \
			probe-$i-raw.txt mark-$i.txt; do
			cp "$DIR/$f" "$pres/" 2>/dev/null || true
		done
		# The device's own copy, read once more and stored verbatim.  This goes
		# through console-run on the shell port like everything else here - the
		# harness has no ssh channel, and inventing one would be a second transport
		# to keep alive on a device that has just wedged.
		timeout 180 "$CR" -Port "$SHELL_PORT" \
			-Out "$WINDIR\\wedge-$i-pstore.log" -WaitReadySeconds 120 -ReadSeconds 10 \
			-Commands 'cat /var/lib/systemd/pstore/console-ramoops-0' \
			>"$pres/on-device-console-raw.txt" 2>&1 || true
		sed -n 's/^[^ ]* *RECV  //p' "$pres/on-device-console-raw.txt" 2>/dev/null \
			>"$pres/on-device-console-ramoops.txt"
		timeout 90 "$CR" -Port "$SHELL_PORT" \
			-Out "$WINDIR\\wedge-$i-pmsg.log" -WaitReadySeconds 120 -ReadSeconds 8 \
			-Commands 'cat /var/lib/systemd/pstore/pmsg-ramoops-0' \
			>"$pres/on-device-pmsg-raw.txt" 2>&1 || true
		sed -n 's/^[^ ]* *RECV  //p' "$pres/on-device-pmsg-raw.txt" 2>/dev/null \
			| tr -d '\000' >"$pres/on-device-pmsg.txt"
		{
			echo "run=$RUN"
			echo "profile=$PROFILE"
			echo "round=$i"
			echo "verdict=$verdict"
			echo "identity=$(get identity)"
			echo "wedge_markers=$(get wedge_markers)"
			echo "suspect_markers=$(get suspect_markers)"
			echo "presence_outages=$(get presence_outages)"
			echo "second_outage_gone=$(get second_outage_gone)"
			echo "second_outage_back=$(get second_outage_back)"
			echo "on_device_console_bytes=$(wc -c <"$pres/on-device-console-ramoops.txt" 2>/dev/null || echo 0)"
			echo "on_device_pmsg=$(cat "$pres/on-device-pmsg.txt" 2>/dev/null | tail -1)"
		} >"$pres/MANIFEST.txt"
		say "round $i: *** WEDGE - evidence preserved in ${pres#$REPO/}" | tee -a "$OUT"
		say "           $(grep -c . "$pres/MANIFEST.txt" 2>/dev/null) manifest fields; pstore copied verbatim" | tee -a "$OUT"
	fi
	if [ "${p_n:-0}" -ge 2 ]; then
		say "round $i: *** the tablet restarted itself (${p_n} outages, second at ${p_off:-?})" | tee -a "$OUT"
		say "round $i: that is the failure signature, not a clean round - stopping" | tee -a "$OUT"
		break
	fi
	if [ "$verdict" = wedge ]; then
		say "round $i: stopping on the wedge verdict" | tee -a "$OUT"
		break
	fi
	if grep -aq "shell never answered\|could not open" "$DIR/probe-$i-raw.txt" 2>/dev/null; then
		say "round $i: the tablet did not come back; stopping (operator action needed)" | tee -a "$OUT"
		break
	fi
done

say "stall A/B done: profile=$PROFILE rounds=$ROUNDS" | tee -a "$OUT"
say "summarise with: scripts/stall-ab.sh --summary" | tee -a "$OUT"
summary_table | tee -a "$OUT"
