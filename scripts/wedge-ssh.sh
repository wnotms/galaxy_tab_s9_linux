#!/usr/bin/env bash
# Run explicitly authorized warm-reboot rounds over SSH.
# Verdicts are replayed locally from immutable boot IDs and archived journals.
# No power flag means a LIVE read-only arming gate, not an offline dry run.
# Offline usage: scripts/wedge-ssh.sh --replay OUT/PROFILE/RUN/round-N
# See docs/STALL_TEST_WORKFLOW.md for evidence and stop rules.

set -uo pipefail

REPO=$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)
SSH=${GTS9_SSH:-$REPO/scripts/gts9-ssh.sh}
EVIDENCE=$REPO/scripts/wedge-evidence.py
if [ "${1:-}" = --replay ]; then
    exec python3 "$EVIDENCE" replay "${2:?round directory required}"
fi
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
PROFILE is one of: baseline, cpuidle-off, csd-lock
Set GTS9_ALLOW_POWER=1 to actually reboot; without it, only the arming gate runs.
EOF
	exit 2
}

case "$PROFILE" in baseline|cpuidle-off|csd-lock) ;; *) usage ;; esac
case "$ROUNDS" in ''|*[!0-9]*) usage ;; esac
[ "$ROUNDS" -ge 1 ] || usage
case "$WINDOW" in ''|*[!0-9]*) usage ;; esac
[ "$WINDOW" -ge 150 ] || { echo 'GTS9_WINDOW must be at least 150 seconds' >&2; exit 2; }

say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { say "FATAL: $*" >&2; exit 1; }

rsh() { timeout 180 "$SSH" "$@" | tr -d '\r'; }

# --- identity, read once before anything --------------------------------------
mkdir -p "$RESULTS/$PROFILE"
RUN=$(mktemp -d "$RESULTS/$PROFILE/run-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX") || exit 1
OUT=$RUN/run.txt
say "wedge-ssh profile=$PROFILE rounds=$ROUNDS allow_power=$ALLOW window=${WINDOW}s" | tee -a "$OUT"

ver=$(rsh 'cat /proc/sys/kernel/random/boot_id')
[ -n "$ver" ] || die "no ssh to the tablet at $DEV"
say "starting boot_id=$ver" | tee -a "$OUT"
say "cmdline=$(rsh 'cat /proc/cmdline' | cut -c1-90)..." | tee -a "$OUT"

arming_gate() {
# --- the arming gate, before any round is counted -----------------------------
# Same logic as stall-ab.sh's: a profile that is silently NOT armed looks exactly
# like a healthy boot, and would make the whole series a no-op.
cmdline=$(rsh 'cat /proc/cmdline') || die "cannot read command line"
gate_log=$(rsh 'journalctl -b 0 -k --no-pager') || die "cannot read arming journal"
[ -n "$gate_log" ] || die "empty arming journal"
# Samsung appends nowatchdog. Cmdline panic tokens alone cannot prove that
# Debian's gts9-watchdog-debug helper actually re-enabled the detector.
recovery_runtime=$(rsh 'set -e; for node in watchdog soft_watchdog softlockup_panic panic; do cat "/proc/sys/kernel/$node"; done') || die "cannot read runtime recovery state"
[ "$recovery_runtime" = $'1\n1\n1\n10' ] || die "runtime watchdog/recovery gate failed: $recovery_runtime"
say "runtime recovery gate PASSED: watchdog=1 soft_watchdog=1 softlockup_panic=1 panic=10" | tee -a "$OUT"
case "$PROFILE" in
cpuidle-off)
	grep -qE '(^| )cpuidle\.off=1( |$)' <<<"$cmdline" || die "cpuidle-off: the cmdline lacks cpuidle.off=1 - NOT armed"
	sysfs=$(rsh 'test -d /sys/devices/system/cpu/cpuidle && echo present || echo ABSENT')
	[ "$sysfs" = "ABSENT" ] || die "cpuidle-off: /sys/devices/system/cpu/cpuidle EXISTS - the framework is running, NOT armed"
	gov=$(grep -ac "cpuidle: using governor" <<<"$gate_log")
	[ "${gov:-x}" = "0" ] || die "cpuidle-off: 'cpuidle: using governor' appeared $gov time(s) on this boot - NOT armed"
	driver=$(rsh 'cat /sys/devices/system/cpu/cpuidle/current_driver 2>/dev/null || echo NONE')
	say "arming gate PASSED: framework off (sysfs ABSENT, governor never registered, driver=$driver)" | tee -a "$OUT"
	;;
baseline)
	grep -qE '(^| )cpuidle\.off=1( |$)' <<<"$cmdline" && die "baseline: the cmdline carries cpuidle.off=1 - this is not the baseline profile"
	driver=$(rsh 'cat /sys/devices/system/cpu/cpuidle/current_driver 2>/dev/null || echo NONE')
	[ "$driver" = "psci_idle" ] || die "baseline: current_driver is '$driver', expected psci_idle - NOT armed"
	say "arming gate PASSED: psci_idle active" | tee -a "$OUT"
	;;
csd-lock)
	# --- a POSITIVE capability test --------------------------------------
	# docs/CSD_IPI_WEDGE_PLAN.md section 2.5.  Both CSD module_params live
	# inside `#ifdef CONFIG_CSD_LOCK_WAIT_DEBUG`, so their sysfs files exist
	# ONLY in a kernel built with the option.  That file appearing cannot be
	# produced by a stale image or by a cmdline that failed to take - which is
	# what makes this a real gate rather than an absence test, and what the
	# plan's Case D needs in order to tell "the instrument was not running"
	# apart from "CSD is not involved".
	grep -qE '(^| )csdlock_debug=1( |$)' <<<"$cmdline" || \
		die "csd-lock: the cmdline lacks csdlock_debug=1 - NOT armed"
	params=$(rsh 'ls /sys/module/smp/parameters/ 2>/dev/null | tr "\n" " "')
	case " $params " in
	*" csd_lock_timeout "*) ;;
	*) die "csd-lock: /sys/module/smp/parameters/csd_lock_timeout is absent, so this kernel was NOT built with CONFIG_CSD_LOCK_WAIT_DEBUG. The instrument would never run and a wedge would produce no CSD output - this is a profile failure, not a result (plan Case D). Parameters seen: '${params:-<none>}'" ;;
	esac
	case " $params " in
	*" panic_on_ipistall "*) ;;
	*) die "csd-lock: panic_on_ipistall parameter absent - CONFIG_CSD_LOCK_WAIT_DEBUG is not fully built in" ;;
	esac
	# The __setup handler must have CONSUMED the token: a token nothing reads
	# stays in the kernel's own unknown-parameter list.  Same gate the project
	# already applies to gts9_rpmh_debug.
	unknown=$(grep -a "Unknown kernel command line parameters" <<<"$gate_log")
	case "$unknown" in
	*csdlock_debug*)
		die "csd-lock: csdlock_debug is in the kernel's unknown-parameter list, so no __setup handler consumed it - the switch is dead" ;;
	esac
	tmo=$(rsh 'cat /sys/module/smp/parameters/csd_lock_timeout 2>/dev/null')
	stop=$(rsh 'cat /sys/module/smp/parameters/panic_on_ipistall 2>/dev/null')
	[ "$tmo" = "5000" ] || die "csd_lock_timeout is '$tmo', expected the 5000 ms default"
	[ "$stop" = "0" ] || die "panic_on_ipistall is '$stop', expected 0 (round one collects, it does not panic)"
	# The recovery chain must still be armed, or an unattended round strands it.
	for tok in softlockup_panic=1 panic=10; do
		grep -qE "(^| )$tok( |$)" <<<"$cmdline" || die "csd-lock: the cmdline lacks $tok - the tablet would not recover by itself"
	done
	say "arming gate PASSED: CSD instrument live (csd_lock_timeout=${tmo}ms panic_on_ipistall=${stop}), token consumed, recovery chain armed" | tee -a "$OUT"
	;;
esac

printf '%s\n' "$gate_log" | python3 -c 'import runpy,sys; m=runpy.run_path(sys.argv[1]); sys.exit(0 if m["profile_matches"](sys.argv[2], sys.stdin.read()) else 1)' "$EVIDENCE" "$PROFILE" || die "profile command line is missing, conflicting or unrecognized"
}
arming_gate

if [ "$ALLOW" != "1" ]; then
	say "live read-only preflight: arming gate passed; set GTS9_ALLOW_POWER=1 to run $ROUNDS rounds"
	exit 0
fi

# Capture the raw input once, then derive every verdict on the host. Failed
# commands keep stderr/status and are never converted to zero anomaly counts.
capture_file() {
    local path=$1
    shift
    rsh "$@" >"$path" 2>"$path.stderr"
    local status=$?
    echo "$status" >"$path.status"
    return "$status"
}
json_field() {
    python3 -c 'import json,sys; v=json.load(open(sys.argv[1])).get(sys.argv[2]); print("" if v is None else v)' "$1" "$2"
}

k=0
n=0
for i in $(seq 1 "$ROUNDS"); do
    ROUND=$RUN/round-$i
    mkdir "$ROUND" || die "cannot create round directory"
    # Recheck at each round, so the gate on the initial boot cannot silently
    # stand in for a different kernel recovered into midway through a series.
    arming_gate >"$ROUND/preflight.txt" 2>&1 || die "round preflight failed"
    capture_file "$ROUND/before-id.txt" 'cat /proc/sys/kernel/random/boot_id' || die "no boot anchor"
    before=$(cat "$ROUND/before-id.txt")
    capture_file "$ROUND/boots-before.txt" 'LC_ALL=C journalctl --list-boots --no-pager' || die "no journal history"
    # Save the identity/profile consulted by the preflight for review.
    capture_file "$ROUND/preflight-identity.txt" 'uname -a; cat /proc/cmdline' || die "no kernel identity"
    say "round $i/$ROUNDS: requesting warm reboot from $before" | tee -a "$OUT"
    # SSH may disconnect on an accepted reboot; the subsequent boot ID is the
    # evidence that it happened, not this command's exit status.
    capture_file "$ROUND/reboot-request.txt" 'systemctl reboot' || true
    sleep 40
    after=""
    for _ in $(seq 1 40); do
        after=$(rsh 'cat /proc/sys/kernel/random/boot_id' 2>>"$ROUND/poll.stderr")
        [ -n "$after" ] && [ "$after" != "$before" ] && break
        sleep 5
    done
    # A failed return still goes through the same archive/replay path and stops
    # the series. It never silently disappears from the denominator.
    if [ -n "$after" ] && [ "$after" != "$before" ]; then
        sleep "$WINDOW"
    fi
    capture_file "$ROUND/boots-after.txt" 'LC_ALL=C journalctl --list-boots --no-pager' || true
    python3 "$EVIDENCE" select "$ROUND" >"$ROUND/selection.json" || die "cannot select target boot"
    target=$(json_field "$ROUND/selection.json" target_boot_id)
    log_ok=0
    : >"$ROUND/klog.txt"
    if [ -n "$target" ]; then
        # Stable journal ID: later reboots cannot move this query to another boot.
        capture_file "$ROUND/klog.txt" "journalctl -b $target -k -o short-monotonic --no-pager" && log_ok=1
    fi
    sample_ok=0
    capture_file "$ROUND/sample.txt" 'set -e; cat /proc/sys/kernel/random/boot_id; cut -d " " -f 1 /proc/uptime; cat /proc/sys/kernel/random/boot_id' && sample_ok=1
    # These are recovery-boot observations, never target-CPU state at the wedge.
    # pstore can be stale; preserve it, but do not use it for automatic verdicts.
    capture_file "$ROUND/pstore-unattributed.txt" 'cat /var/lib/systemd/pstore/console-ramoops-0' || true
    capture_file "$ROUND/observer-state.txt" 'cat /proc/sys/kernel/random/boot_id; cat /proc/interrupts; cat /proc/softirqs; cat /proc/sys/kernel/random/boot_id' || true
    python3 - "$ROUND" "$PROFILE" "$WINDOW" "$target" "$log_ok" "$sample_ok" <<'PYMETA' || die "cannot save capture metadata"
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
lines = (path / 'sample.txt').read_text().splitlines()
capture = dict(profile=sys.argv[2], window_s=int(sys.argv[3]),
               log_boot_id=sys.argv[4], log_ok=sys.argv[5] == '1',
               sample_ok=sys.argv[6] == '1' and len(lines) == 3)
if len(lines) == 3:
    capture.update(sample_start_boot_id=lines[0], uptime_s=lines[1],
                   sample_end_boot_id=lines[2])
(path / 'capture.json').write_text(json.dumps(capture, indent=2) + '\n')
PYMETA
    python3 "$EVIDENCE" replay "$ROUND" >"$ROUND/verdict.json" || die "invalid round evidence"
    verdict=$(json_field "$ROUND/verdict.json" verdict)
    reason=$(json_field "$ROUND/verdict.json" reason)
    # CSD fields remain convenient for human review; the classifier reads the
    # archived journal directly and includes CSD non-response as a signature.
    if [ "$PROFILE" = csd-lock ]; then
        kf=$ROUND/klog.txt
        {
            echo "csd_timeout_ms=$tmo"
            echo "csd_panic_on_ipistall=$stop"
            echo 'parameter_scope=preflight_boot_only'
            echo "csd_report_lines=$(grep -acE 'csd: (Detected|Continued) non-responsive' "$kf")"
            echo "csd_first_report=$(grep -aE 'csd: (Detected|Continued) non-responsive' "$kf" | head -1)"
            echo "csd_targets=$(grep -aoE 'for CPU#[0-9]+ [^ ]+' "$kf" | sort -u | tr '\n' ';')"
            echo "csd_disposition=$(grep -aoE 'CSD lock \(#[0-9]+\) (unresponsive|handling this request|handling prior[^.]*)' "$kf" | sort -u | tr '\n' ';')"
            echo "csd_resends=$(grep -ac 'Re-sending CSD lock' "$kf")"
            echo "csd_unstuck=$(grep -ac 'got unstuck' "$kf")"
        } >"$ROUND/csd-summary.txt"
    fi
    [ "$verdict" = clean ] && n=$((n + 1))
    [ "$verdict" = wedge ] && k=$((k + 1))
    say "round $i: verdict=$verdict reason=$reason evidence=$ROUND" | tee -a "$OUT"
    # Forensics stops at the first failure; ambiguous capture stops for repair.
    # Neither suspect nor unattributed rounds belong in a clean denominator.
    if [ "$verdict" != clean ]; then
        say "STOPPING: review $verdict evidence before another round" | tee -a "$OUT"
        break
    fi
done
say "series complete: clean=$n wedge=$k; this is not a rate estimate" | tee -a "$OUT"
say "raw evidence: $RUN" | tee -a "$OUT"
case "$verdict" in clean) exit 0 ;; wedge) exit 10 ;; suspect) exit 11 ;; *) exit 12 ;; esac
