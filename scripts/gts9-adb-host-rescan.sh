#!/usr/bin/env bash
# Reopen the computer's ADB server; never restart device services or reset USB.
set -euo pipefail
if [ "$#" -ne 0 ]; then
  echo 'usage: gts9-adb-host-rescan.sh (optional GTS9_ADB_EXE override)' >&2
  exit 2
fi
adb_exe=${GTS9_ADB_EXE:-/mnt/d/android/platform-tools/adb.exe}
"$adb_exe" kill-server
"$adb_exe" start-server
"$adb_exe" devices -l
