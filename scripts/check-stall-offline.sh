#!/usr/bin/env bash
# Host-only checks. No SSH, adb, flashing, reboot or live preflight.
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo"
scope=${1:---changed}
case "$scope" in
    --changed|--focused|--core|--artifacts|--archive|--full) ;;
    *) echo 'usage: bash scripts/check-stall-offline.sh [--changed [--base REV]|--core|--focused|--artifacts|--archive|--full]' >&2; exit 2 ;;
esac
if [ "$scope" = --changed ]; then
    [ "$#" -eq 0 ] || shift
    if [ "$#" -eq 0 ]; then
        args=()
    elif [ "$#" -eq 2 ] && [ "$1" = --base ]; then
        args=(--base "$2")
    else
        echo 'usage: bash scripts/check-stall-offline.sh --changed [--base REV]' >&2; exit 2
    fi
else
    [ "$#" -le 1 ] || { echo 'expected at most one scope' >&2; exit 2; }
    args=()
fi

# bash -n scripts/*.sh only parses the FIRST file; pass each file separately.
for script in scripts/*.sh scripts/lib/*.sh boot/*.sh; do
    bash -n "$script"
done
# Trace feasibility depends on the recorded kernel tree and capture artifacts.
if [ "$scope" = --focused ] || [ "$scope" = --artifacts ] || [ "$scope" = --full ]; then
    python3 scripts/prepare-csd-trace.py \
        --output "${GTS9_OFFLINE_OUT:-out/csd-trace-next}/offline-report.json"
fi
if [ "$scope" = --focused ]; then
    python3 -m unittest discover -s tests -p 'test_wedge_evidence.py' -v
else
    suite=${scope#--}
    [ "$suite" != full ] || suite=all
    python3 scripts/run-host-tests.py "$suite" "${args[@]}"
fi
echo 'Offline checks completed for the reported scope; this does not establish physical capture readiness.'
