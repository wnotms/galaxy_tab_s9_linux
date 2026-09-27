#!/usr/bin/env bash
# Host-only checks. No SSH, adb, flashing, reboot or live preflight.
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo"
scope=${1:---core}
case "$scope" in
    --focused|--core|--artifacts|--archive|--full) ;;
    *) echo 'usage: bash scripts/check-stall-offline.sh [--core|--focused|--artifacts|--archive|--full]' >&2; exit 2 ;;
esac
[ "$#" -le 1 ] || { echo 'expected at most one scope' >&2; exit 2; }

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
    python3 scripts/run-host-tests.py "$suite"
fi
echo 'Offline checks passed; this does not establish physical capture readiness.'
