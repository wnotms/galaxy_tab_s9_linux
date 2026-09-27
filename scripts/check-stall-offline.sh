#!/usr/bin/env bash
# Host-only checks. No SSH, adb, flashing, reboot or live preflight.
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo"
scope=${1:---focused}
case "$scope" in
    --focused|--full) ;;
    *) echo 'usage: bash scripts/check-stall-offline.sh [--focused|--full]' >&2; exit 2 ;;
esac

# bash -n scripts/*.sh only parses the FIRST file; pass each file separately.
for script in scripts/*.sh scripts/lib/*.sh boot/*.sh; do
    bash -n "$script"
done
python3 scripts/prepare-csd-trace.py \
    --output "${GTS9_OFFLINE_OUT:-out/csd-trace-next}/offline-report.json"
if [ "$scope" = --full ]; then
    python3 -m unittest discover -s tests -v
else
    python3 -m unittest discover -s tests -p 'test_wedge_evidence.py' -v
fi
echo 'Offline checks passed; this does not establish physical capture readiness.'
