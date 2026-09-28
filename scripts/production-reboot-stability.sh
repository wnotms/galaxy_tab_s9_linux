#!/usr/bin/env bash
# Test250 only: read-only production checks plus explicitly requested normal reboots.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
exec python3 "$HERE/production_reboot_stability.py" "$@"
