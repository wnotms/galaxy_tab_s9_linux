#!/usr/bin/env bash
# Run cpuidle-off rounds over the USB-NCM ssh channel, and classify each one.
#
# WHY THIS EXISTS, AND WHAT IT IS NOT
#
# scripts/stall-ab.sh drives rounds over the Windows COM ports: COM17 for the
# shell and COM19 for the console capture.  Neither is present on this host, and
# the harness says so explicitly - it "has no ssh channel, and inventing one
# would be a second transport".  So this is deliberately NOT a rewrite of that
# harness and NOT a replacement for it.  It is the same experiment carried over
# the one transport this host actually has, and it borrows the harness's
# definitions rather than restating them:
#
#   * the wedge/suspect/unattributed classes are the harness's own
#     (docs/CPU_WEDGE_EVIDENCE.md, and the verdict block in stall-ab.sh)
#   * `ENCODER_NOISE` fires once on every healthy boot and is never an anomaly
#   * a lone DPU/MMC/RPMh timeout is SUSPECT, never WEDGE (test-194)
#   * an unattributed round counts in neither direction
#
# WHAT IT CANNOT SEE, AND SAYS SO
#
# The COM19 console capture caught USB-presence outages, which was the harness's
# independent detector for "something other than the harness restarted this
# boot".  There is no such capture here.  This runner detects that condition a
# different way - by comparing the boot id it asked for a reboot on against the
# boot id it finds afterwards, and by counting the boots journald gained - and it
# records which detector it used so a reader is never misled about the channel.
# A panic-and-reboot therefore shows up as "the round's boot id is not the boot
# that answered", which is the same fact the presence outage encoded.
#
# SAFETY: this script never flashes and never writes a partition.  It issues
# `systemctl reboot` over ssh.  Recovery from a wedge is the kernel's own
# panic chain (softlockup_panic=1 -> panic=10 -> reboot), which the profile
# carries, so an unattended round cannot strand the tablet.
#
# Usage:
#   scripts/wedge-ssh.sh PROFILE ROUNDS          # PROFILE: cpuidle-off|baseline
#   GTS9_ALLOW_POWER=1 scripts/wedge-ssh.sh cpuidle-off 10

set -uo pipefail

REPO=$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)
SSH=$REPO/scripts/gts9-ssh.sh
PROFILE=${1:-}
ROUNDS=${2:-}
ALLOW=${GTS9_ALLOW_POWER:-0}
# How long to keep watching a boot before calling it clean.  The documented
# onsets are ~6.5-7.8 s and the observations run to ~45 s; the harness uses 150 s
# and this matches it, because a shorter window is what the project's own rate
# rule criticises.
WINDOW=${GTS9_WINDOW:-150}
DEV=${GTS9_DEVICE:-169.254.42.1}
RESULTS=${GTS9_SSH_RESULTS:-$REPO/out/wedge-ssh}

usage() {
	cat >&2 <<'EOF'
usage: wedge-ssh.sh PROFILE ROUNDS
PROFILE is one of: cpuidle-off, baseline
Set GTS9_ALLOW_POWER=1 to actually reboot; without it, only the arming gate runs.
EOF
	exit 2
}

case "$PROFILE" in cpuidle-off|baseline) ;; *) usage ;; esac
case "$ROUNDS" in ''|*[!0-9]*) usage ;; esac
[ "$ROUNDS" -ge 1 ] || usage

say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { say "FATAL: $*" >&2; exit 1; }

rsh() { timeout 180 "$SSH" "$@" 2>/dev/null | tr -d '\r'; }

# --- anomaly classes, from the harness ---------------------------------------
# Kept identical to stall-ab.sh's split so "wedge" means the same thing here.
WEDGE_CLASSES='rcu:.*(detected stall|self-detected stall)|soft lockup|BUG: workqueue lockup|haven.t responded to the NMI|Kernel panic'
SUSPECT_CLASSES='frame done timeout|mmc[0-9]+: .*[Tt]imeout|ACTIVE_ONLY|rpmh_write_batch'

count() { printf '%s' "$(rsh "journalctl -b $1 -k --no-pager 2>/dev/null | grep -acE '$2' || true")"; }

# --- identity, read once before anything --------------------------------------
mkdir -p "$RESULTS/$PROFILE"
OUT=$RESULTS/$PROFILE/run-$(date -u +%Y%m%dT%H%M%SZ).txt
say "wedge-ssh profile=$PROFILE rounds=$ROUNDS allow_power=$ALLOW window=${WINDOW}s" | tee -a "$OUT"

ver=$(rsh 'cat /proc/sys/kernel/random/boot_id')
[ -n "$ver" ] || die "no ssh to the tablet at $DEV"
say "starting boot_id=$ver" | tee -a "$OUT"
say "cmdline=$(rsh 'cat /proc/cmdline' | cut -c1-90)..." | tee -a "$OUT"

# --- the arming gate, before any round is counted -----------------------------
# Same logic as stall-ab.sh's: a profile that is silently NOT armed looks exactly
# like a healthy boot, and would make the whole series a no-op.
cmdline=$(rsh 'cat /proc/cmdline')
case "$PROFILE" in
cpuidle-off)
	grep -q 'cpuidle\.off=1' <<<"$cmdline" || die "cpuidle-off: the cmdline lacks cpuidle.off=1 - NOT armed"
	sysfs=$(rsh 'test -d /sys/devices/system/cpu/cpuidle && echo present || echo ABSENT')
	[ "$sysfs" = "ABSENT" ] || die "cpuidle-off: /sys/devices/system/cpu/cpuidle EXISTS - the framework is running, NOT armed"
	gov=$(rsh 'journalctl -b 0 -k --no-pager 2>/dev/null | grep -ac "cpuidle: using governor" || true')
	[ "${gov:-x}" = "0" ] || die "cpuidle-off: 'cpuidle: using governor' appeared $gov time(s) on this boot - NOT armed"
	driver=$(rsh 'cat /sys/devices/system/cpu/cpuidle/current_driver 2>/dev/null || echo NONE')
	say "arming gate PASSED: framework off (sysfs ABSENT, governor never registered, driver=$driver)" | tee -a "$OUT"
	;;
baseline)
	grep -q 'cpuidle\.off=1' <<<"$cmdline" && die "baseline: the cmdline carries cpuidle.off=1 - this is not the baseline profile"
	driver=$(rsh 'cat /sys/devices/system/cpu/cpuidle/current_driver 2>/dev/null || echo NONE')
	[ "$driver" = "psci_idle" ] || die "baseline: current_driver is '$driver', expected psci_idle - NOT armed"
	say "arming gate PASSED: psci_idle active" | tee -a "$OUT"
	;;
esac

if [ "$ALLOW" != "1" ]; then
	say "dry run: arming gate passed; set GTS9_ALLOW_POWER=1 to run $ROUNDS rounds"
	exit 0
fi

# --- rounds -------------------------------------------------------------------
k=0   # rounds carrying the wedge signature
n=0   # rounds with a usable verdict

for i in $(seq 1 "$ROUNDS"); do
	before=$ver
	say "=== $PROFILE round $i/$ROUNDS (boot_id before=$before) ===" | tee -a "$OUT"

	# Count the boots journald knows, so an extra boot between the reboot and the
	# probe is visible as a number rather than inferred.
	boots_before=$(rsh 'journalctl --list-boots --no-pager 2>/dev/null | wc -l')

	rsh 'systemctl reboot' >/dev/null 2>&1
	sleep 40

	# Wait for the tablet to answer again.  A wedge that panics reboots itself
	# (softlockup_panic=1, panic=10), so this also waits out a recovery.
	after=""
	for _ in $(seq 1 40); do
		after=$(rsh 'cat /proc/sys/kernel/random/boot_id')
		[ -n "$after" ] && [ "$after" != "$before" ] && break
		sleep 5
	done
	if [ -z "$after" ] || [ "$after" = "$before" ]; then
		say "  round $i UNATTRIBUTED: the tablet did not return with a new boot id" | tee -a "$OUT"
		# Still try to bind whatever it left behind, and keep the raw evidence.
		# The round's boot may or may not be the current one here, so the
		# previous boot is the safest single guess AND the current boot is
		# captured too - an unattributed round must not also lose its evidence.
		rsh "journalctl -b -1 -k -o short-monotonic --no-pager 2>/dev/null | tail -400" \
			>"$RESULTS/$PROFILE/round-$i-last-klog.txt"
		rsh "journalctl -b 0 -k -o short-monotonic --no-pager 2>/dev/null | tail -400" \
			>"$RESULTS/$PROFILE/round-$i-current-klog.txt"
		continue
	fi

	# Watch the window.  A wedge is usually visible well inside it, but the
	# documented onset spread means the window is not shortened.
	sleep "$WINDOW"

	boots_after=$(rsh 'journalctl --list-boots --no-pager 2>/dev/null | wc -l')
	extra_boots=$((boots_after - boots_before - 1))
	now_id=$(rsh 'cat /proc/sys/kernel/random/boot_id')

	# The round's own boot is the one we rebooted into; if something rebooted it
	# again, `now_id` differs and `extra_boots` is positive.  That is the
	# reinvention of the harness's second-presence-outage detector.
	recovery=no
	[ "$now_id" != "$after" ] && recovery=yes

	# WHICH BOOT IS THE ROUND'S BOOT - and this is not always -1.
	#
	# The round's boot is the one the harness rebooted INTO.  Immediately after
	# that reboot it is boot 0, and `-b -1` would be the boot BEFORE the round,
	# which is exactly the off-by-one that would make a wedged round look clean:
	# the markers are in the round's boot, not in the one before it.
	#
	# It is only `-1` when the kernel rebooted itself again during the window -
	# the panic chain - because then the round's boot has become the previous
	# one.  That is the same condition the recovery detector tests, so it is
	# computed once and used for both.
	if [ "$now_id" = "$after" ]; then
		idx=0              # still on the round's boot
	else
		idx=-1             # the round's boot is now the previous one
	fi

	w=$(count "$idx" "$WEDGE_CLASSES")
	s=$(count "$idx" "$SUSPECT_CLASSES")

	verdict=clean
	[ "${s:-0}" -gt 0 ] && verdict=suspect
	[ "${w:-0}" -gt 0 ] && verdict=wedge
	[ "$recovery" = yes ] && verdict=wedge

	rsh "journalctl -b $idx -k -o short-monotonic --no-pager 2>/dev/null" \
		>"$RESULTS/$PROFILE/round-$i-klog.txt"
	rsh "cat /var/lib/systemd/pstore/console-ramoops-0 2>/dev/null" \
		>"$RESULTS/$PROFILE/round-$i-pstore.txt"
	rsh "cat /proc/interrupts 2>/dev/null" >"$RESULTS/$PROFILE/round-$i-interrupts.txt"
	rsh "cat /proc/softirqs 2>/dev/null" >"$RESULTS/$PROFILE/round-$i-softirqs.txt"
	rsh 'for c in /sys/devices/system/cpu/cpu[0-7]; do n=$(basename $c); for st in $c/cpuidle/state*; do [ -d "$st" ] && printf "%s:%s:%s/%s/%s " "$n" "$(basename $st)" "$(cat $st/name 2>/dev/null)" "$(cat $st/usage 2>/dev/null)" "$(cat $st/rejected 2>/dev/null)"; done; done' \
		>"$RESULTS/$PROFILE/round-$i-cpuidle.txt"
	rsh "cat /sys/kernel/debug/pm_genpd/power-domain-cluster/idle_states 2>/dev/null" \
		>"$RESULTS/$PROFILE/round-$i-genpd.txt"

	# The first wedge-class line, with its monotonic timestamp - the onset
	# evidence, and the only thing that identifies WHICH CPU stopped answering.
	first=$(grep -aoE '^\[ *[0-9]+\.[0-9]+\].*(rcu:.*stall|soft lockup|workqueue lockup|haven.t responded|Kernel panic)' \
		"$RESULTS/$PROFILE/round-$i-klog.txt" 2>/dev/null | head -1)

	{
		echo "run_profile=$PROFILE"
		echo "round=$i"
		echo "boot_id_before=$before"
		echo "boot_id_after=$after"
		echo "boot_id_at_probe=$now_id"
		echo "reboot_kind=warm"
		echo "window_s=$WINDOW"
		echo "extra_boots=$extra_boots"
		echo "self_recovery=$recovery"
		echo "detector=boot_id_change+journal_boot_count"
		echo "log_boot_index=$idx"
		echo "wedge_markers=$w"
		echo "suspect_markers=$s"
		echo "verdict=$verdict"
		echo "first_wedge_line=$first"
	} >"$RESULTS/$PROFILE/round-$i.txt"

	[ "$verdict" != unattributed ] && n=$((n + 1))
	[ "$verdict" = wedge ] && k=$((k + 1))

	say "  round $i: verdict=$verdict wedge_markers=$w suspect_markers=$s self_recovery=$recovery extra_boots=$extra_boots" | tee -a "$OUT"
	[ -n "$first" ] && say "    first: $first" | tee -a "$OUT"

	# The rule's first row: one genuine wedge stops the direction.  Do not grind
	# on - the plan says so before the data existed.
	if [ "$verdict" = wedge ]; then
		say "STOPPING: a wedge is a fact; the remaining rounds cannot change it" | tee -a "$OUT"
		break
	fi

	ver=$after
done

say "series complete: n=$n wedge=$k" | tee -a "$OUT"
[ "$k" -eq 0 ] && say "not reproduced in $n boots (this is a bound, not a fix)" | tee -a "$OUT"
say "raw evidence: $RESULTS/$PROFILE/" | tee -a "$OUT"
