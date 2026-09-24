#!/usr/bin/env bash
# test-187: run the X710 GPU/ACD/AOSS stall A/B across profiles A, B and C.
#
# This is a thin wrapper over scripts/stall-ab.sh, which does the booting and
# per-round metric collection.  The wrapper exists to run the three profiles in
# the agreed order, keep their summaries in one place, and write the round
# README from what was actually observed.
#
# SAFETY: nothing is flashed here and no partition or BCB is written.  Rebooting
# only happens with GTS9_ALLOW_POWER=1, which is also what scripts/stall-ab.sh
# requires.  Without it this script runs the three preflights and stops.
#
# The operator is responsible for flashing the right pair between profiles:
#
#	profile A : boot.img + vendor_boot.img from out/boot-bundle-test187-baseline
#	profile B : vendor_boot.img from out/boot-bundle-test187-no-acd
#	profile C : vendor_boot.img from out/boot-bundle-test187-no-gpu
#
# Only vendor_boot changes for B and C; boot.img is identical for all three.
#
#   reference/boot-tests/test-187-*/ab-run.sh 5
#   GTS9_ALLOW_POWER=1 reference/boot-tests/test-187-*/ab-run.sh 5
set -uo pipefail

REPO=$(cd "$(dirname "$0")/../../.." && pwd)
D=$(cd "$(dirname "$0")" && pwd)
AB=$REPO/scripts/stall-ab.sh
ROUNDS=${1:-5}
ALLOW=${GTS9_ALLOW_POWER:-0}
RESULTS=${GTS9_AB_RESULTS:-$REPO/out/stall-ab}
OUT=$D/ab-run.txt

say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$OUT"; }

[ -x "$AB" ] || { echo "missing $AB" >&2; exit 1; }
case "$ROUNDS" in ''|*[!0-9]*) echo "usage: ab-run.sh [rounds]" >&2; exit 2 ;; esac

say "test-187 stall A/B: rounds=$ROUNDS allow_power=$ALLOW"
say "profiles are run in the order A (baseline, = profile D), B (no-ACD), C (no-GPU)"
say "each profile needs its boot.img/vendor_boot.img flashed first - see candidate.txt"

for profile in baseline no-acd no-gpu; do
	say "=============================================================="
	say "profile: $profile"
	say "expected vendor_boot.img from out/boot-bundle-test187-$profile/"
	say "=============================================================="

	if [ "$ALLOW" != "1" ]; then
		# Preflight only, through the harness itself so the profile-token
		# checks run and a mismatch is reported now rather than mid-series.
		"$AB" "$profile" "$ROUNDS" 2>&1 | sed 's/^/  /' | tee -a "$OUT"
		continue
	fi

	"$AB" "$profile" "$ROUNDS" 2>&1 | sed 's/^/  /' | tee -a "$OUT"

	# Stop the series if the tablet did not come back: continuing would
	# attribute the next profile's results to a machine that never rebooted.
	if grep -aq "did not come back" "$RESULTS/$profile/ab-$profile.txt" 2>/dev/null; then
		say "STOP: $profile did not return; operator action needed before continuing"
		break
	fi

	if [ "$profile" != "no-gpu" ]; then
		say "flash the next profile's vendor_boot.img, then re-run for that profile"
		say "(this wrapper does not flash anything)"
		break
	fi
done

if [ "$ALLOW" != "1" ]; then
	say "dry run complete: nothing was flashed and nothing was rebooted"
	say "re-run with GTS9_ALLOW_POWER=1, one profile per flash, to collect data"
	exit 0
fi

say "=============================================================="
say "aggregate summary"
say "=============================================================="
"$AB" --summary 2>&1 | sed 's/^/  /' | tee -a "$OUT"

# Per-profile verdict lines, so the README can be written from data.
for profile in baseline no-acd no-gpu; do
	dir=$RESULTS/$profile
	[ -d "$dir" ] || continue
	rounds=$(ls "$dir"/round-*.txt 2>/dev/null | wc -l)
	stalls=$(cat "$dir"/round-*.txt 2>/dev/null | sed -n 's/^stall=//p' | paste -sd+ - | bc 2>/dev/null)
	rpmh=$(cat "$dir"/round-*.txt 2>/dev/null | sed -n 's/^rpmh_timeout=//p' | paste -sd+ - | bc 2>/dev/null)
	bound=$(cat "$dir"/round-*.txt 2>/dev/null | sed -n 's/^gpu_bound=//p' | sort -u | paste -sd, -)
	say "profile=$profile rounds=$rounds total_stalls=${stalls:-0} total_rpmh_timeouts=${rpmh:-0} gpu_bound_seen=${bound:-unknown}"
done

say "done.  Read $OUT, $RESULTS/*/round-*.txt and the --summary table."
