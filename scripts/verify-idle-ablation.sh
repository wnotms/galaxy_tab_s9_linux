#!/usr/bin/env bash
# Verify that an idle-ablation DTB is the device tree it claims to be.
#
# The brief is explicit that this must be checked on the COMPILED DTB rather than
# assumed from the source.  That warning is well earned - this repository already
# shipped a profile whose token the kernel silently ignored (`msm.no_gpu=1`,
# docs/STALL_FIRST_EVENT_ORDERING.md "Corrected inputs"), and an ablation that
# silently did nothing would produce a clean series that appears to prove the
# opposite of what it shows.
#
# The parse itself lives in scripts/lib/dtb-idle-states.py.  An earlier revision
# of this script did it with awk and got the wrong answer twice: it dropped the
# second phandle of `domain-idle-states = <0x30 0x31>`, and it counted lines
# where it needed to count phandles.  Both bugs happened to fail safe, but a
# verifier that reports the wrong thing on a good DTB is one edit away from
# reporting the right thing on a bad one.  The tree is therefore parsed as a
# tree, by phandle, in one auditable place.
#
# Usage:
#   scripts/verify-idle-ablation.sh DTB PROFILE
#
# PROFILE is one of: baseline, no-llcc-off, no-cluster-idle
#
# SAFETY: read-only.  Decompiles a file to a temporary directory; touches no
# device and no partition.

set -euo pipefail

dtb=${1:?usage: verify-idle-ablation.sh DTB PROFILE}
profile=${2:?usage: verify-idle-ablation.sh DTB PROFILE}

[ -f "$dtb" ] || { echo "no such DTB: $dtb" >&2; exit 1; }
command -v dtc >/dev/null || { echo 'dtc is required' >&2; exit 2; }

repo_root=$(cd "$(dirname "$0")/.." && pwd)
parser=$repo_root/scripts/lib/dtb-idle-states.py
[ -f "$parser" ] || { echo "missing parser: $parser" >&2; exit 1; }

case "$profile" in
    baseline|no-llcc-off|no-cluster-idle) ;;
    *) echo "unknown profile: $profile (baseline, no-llcc-off, no-cluster-idle)" >&2; exit 2 ;;
esac

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
report=$tmp/report.txt
if ! python3 "$parser" "$dtb" >"$report" 2>"$tmp/err"; then
    echo "FAIL: cannot parse $dtb" >&2
    sed 's/^/  /' "$tmp/err" >&2
    exit 1
fi

get() { sed -n "s/^$1=//p" "$report" | head -1; }

fails=0
pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; fails=$((fails + 1)); }

echo "verifying $dtb as profile '$profile'"

# --- 1. this is the X710 device tree at all ----------------------------------
# A DTB that lost /psci entirely would otherwise pass a "no cluster state" test.
if [ "$(get cluster_pd_node)" = "/psci/power-domain-cluster" ]; then
    pass '/psci/power-domain-cluster is present'
else
    fail "/psci/power-domain-cluster is missing (got: $(get cluster_pd_node)) - not the X710 device tree"
    echo; echo "IDLE ABLATION VERIFICATION FAILED ($fails check(s))"; exit 1
fi

model=$(get model)
if [ "$model" = "Samsung Galaxy Tab S9 Wi-Fi" ]; then
    pass 'model is the SM-X710 tablet'
else
    fail "model is not the X710 tablet: '$model'"
fi

compatible=$(get compatible)
case "$compatible" in
*qcom,kalama-mtp*) pass 'ABL compatible selector qcom,kalama-mtp present' ;;
*) fail "ABL compatible selector missing: '$compatible'" ;;
esac
[ "$(get board_id)" = present ] && pass 'qcom,board-id present' || fail 'qcom,board-id missing'
[ "$(get msm_id)" = present ] && pass 'qcom,msm-id present' || fail 'qcom,msm-id missing'
for label in qcom_tzlog arch_timer qcom_scm; do
    if [ "$(get symbol:$label)" = present ]; then
        pass "ABL label present in __symbols__: $label"
    else
        fail "ABL label missing from __symbols__: $label - Samsung ABL may reject this DTB"
    fi
done

# --- 2. the cluster layer: exactly what this profile claims ------------------
# 0x41000044 = cluster-sleep-0, 0x4100c344 = cluster-sleep-1
# (docs/SM8550_IDLE_STATE_ANALYSIS.md).
cluster_states=$(get cluster_states)
echo "      cluster_pd references: ${cluster_states:-<none>}"
case "$profile" in
baseline)
    [ "$cluster_states" = "0x41000044 0x4100c344" ] \
        && pass 'both cluster states present (unablated)' \
        || fail "baseline must reference both cluster states, got: ${cluster_states:-<none>}" ;;
no-llcc-off)
    [ "$cluster_states" = "0x41000044" ] \
        && pass 'cluster_sleep_1 (0x4100c344) removed, cluster_sleep_0 kept' \
        || fail "no-llcc-off must reference 0x41000044 only, got: ${cluster_states:-<none>}" ;;
no-cluster-idle)
    [ -z "$cluster_states" ] \
        && pass 'no cluster domain state referenced at all' \
        || fail "no-cluster-idle must reference no cluster state, got: $cluster_states" ;;
esac

# The state DEFINITIONS stay in the tree even when unreferenced, so assert that
# too: if a build ever lost them, the ablation would be hiding a different bug.
if [ "$(get cluster_state_definitions)" = "2" ]; then
    pass 'both cluster state nodes are still defined (only the reference changed)'
else
    fail "expected 2 cluster state definitions, got: $(get cluster_state_definitions)"
fi

# --- 3. the per-CPU layer must be UNTOUCHED ----------------------------------
# This is the guard against the index-0 trap: if an ablation ever cost the CPUs
# their states, psci_idle would fail to register for all eight CPUs and the
# profile would silently be cpuidle.off=1 (docs/SM8550_IDLE_STATE_ANALYSIS.md 5).
if [ "$(get cpu_pd_count)" = "8" ]; then
    pass 'all 8 per-CPU power domains present'
else
    fail "expected 8 per-CPU power domains, got: $(get cpu_pd_count)"
fi

bad_cpu=""
for n in 0 1 2 3 4 5 6 7; do
    c=$(get "cpu_pd_state_count:power-domain-cpu$n")
    [ "$c" = "1" ] || bad_cpu="$bad_cpu cpu$n=${c:-<missing>}"
done
if [ -z "$bad_cpu" ]; then
    pass 'every per-CPU domain still references exactly one idle state'
else
    fail "a per-CPU domain lost or gained states:$bad_cpu - cpuidle would fail for all CPUs"
fi

for name in silver-rail-power-collapse gold-rail-power-collapse goldplus-rail-power-collapse; do
    if [ "$(get "cpu_state_name:$name")" = "present" ]; then
        pass "CPU low-power state still defined: $name"
    else
        fail "CPU low-power state missing: $name"
    fi
done

if [ "$(get cpu_states_with_shared_param)" = "3" ]; then
    pass 'all 3 per-CPU states carry 0x40000004'
else
    fail "expected 3 per-CPU states with 0x40000004, got: $(get cpu_states_with_shared_param)"
fi

echo
if [ "$fails" -eq 0 ]; then
    echo "IDLE ABLATION VERIFICATION PASSED ($profile)"
    echo "Read-only: nothing was written."
    exit 0
fi
echo "IDLE ABLATION VERIFICATION FAILED ($fails check(s))"
echo "Do NOT flash this DTB: the profile it implements is not the one it claims."
exit 1
