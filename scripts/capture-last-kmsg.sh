#!/usr/bin/env bash
# Capture the persistent console ring the moment the tablet appears on adb.
#
# Boot test 1 lost evidence to timing: TWRP's own kernel log fills the 2 MiB
# sec_log_buf ring within a couple of minutes, so a manual dump taken "shortly
# after" recovery is up can already have overwritten the failed boot's log.
#
# Run this on the host before starting a boot attempt, with the tablet
# connected. It blocks until adb sees the device, then immediately pulls
# /proc/last_kmsg and reports whether the ring contains a mainline boot.
#
#	ADB=/mnt/d/android/platform-tools/adb.exe ./scripts/capture-last-kmsg.sh
#
# Read-only: it runs `cat` on a proc file and writes the copy on the host. It
# touches no block device and no partition.
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
adb=${ADB:-adb}
out_dir=${CAPTURE_DIR:-${GTS9_WORKDIR:-$repo_root/.work}/boot-logs}
wait_seconds=${WAIT_TIMEOUT:-1800}
label=${CAPTURE_LABEL:-boot}

# Safety self-check, same idea as the other read-only tools in this repository.
for forbidden in dd fastboot heimdall odin; do
    if grep -qE "(^|[;&|(]|\\\$\()[[:space:]]*${forbidden}([[:space:]]|\\\$)" "$0"; then
        echo "refusing to run: $0 references the command '$forbidden'" >&2
        exit 1
    fi
done

command -v "$adb" >/dev/null 2>&1 || {
    echo "adb not found: $adb (set ADB=/path/to/adb)" >&2
    exit 2
}

mkdir -p "$out_dir"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
out=$out_dir/last_kmsg-$label-$stamp.txt

# `adb wait-for-device` never returns for a tablet sitting in TWRP, because
# TWRP reports its adb state as "recovery" rather than "device". Poll the
# device list instead, then probe the file that is actually needed.
wait_for_ring() {
    local deadline=$((SECONDS + wait_seconds))
    while [ "$SECONDS" -lt "$deadline" ]; do
        if "$adb" devices 2>/dev/null | tr -d '\r' \
                | awk 'NR > 1 && $2 ~ /^(device|recovery)$/ { found = 1 } END { exit !found }'; then
            if timeout 60 "$adb" shell 'test -r /proc/last_kmsg' >/dev/null 2>&1; then
                return 0
            fi
        fi
        sleep 3
    done
    return 1
}

echo "waiting up to ${wait_seconds}s for the tablet and /proc/last_kmsg..."
if ! wait_for_ring; then
    echo "timed out waiting for a readable /proc/last_kmsg" >&2
    exit 1
fi

echo "capturing /proc/last_kmsg to $out"
if ! timeout 300 "$adb" exec-out cat /proc/last_kmsg > "$out" 2>/dev/null; then
    echo "capture failed" >&2
    exit 1
fi

size=$(stat -c %s "$out")
sha=$(sha256sum "$out" | cut -d' ' -f1)

echo
echo "captured : $out"
echo "size     : $size bytes"
echo "sha256   : $sha"
echo

report() {
    # report <description> <pattern>
    local n
    n=$(grep -ac -- "$2" "$out" 2>/dev/null || true)
    printf '  %-34s %s\n' "$1" "${n:-0}"
}

echo 'markers:'
report 'Linux version' 'Linux version'
report 'sec_log early console line' 'gts9wifi-sec-log:'
report 'GTS9 MAINLINE INITRAMFS REACHED' 'GTS9 MAINLINE INITRAMFS REACHED'
report 'gts9-init userspace lines' 'gts9-init:'
report 'Kernel panic' 'Kernel panic'
report 'Unable to handle kernel' 'Unable to handle'
echo

if grep -aq 'GTS9 MAINLINE INITRAMFS REACHED' "$out"; then
    echo 'RESULT: initramfs milestone present -> case A (booted, initramfs reached)'
elif grep -aq 'Linux version' "$out"; then
    echo 'RESULT: kernel started -> read the last lines before the reset (case B/D)'
else
    echo 'RESULT: no kernel markers in the ring (case C-like, or already overwritten)'
fi
echo
echo 'Keep this file with the test record; it is the primary evidence.'
