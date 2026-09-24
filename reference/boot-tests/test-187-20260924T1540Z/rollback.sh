#!/usr/bin/env bash
# test-187: restore the boot + vendor_boot pair backed up by flash-profile.sh.
#
#   backup -> SHA256 -> flash -> readback -> SHA256 verify
#
# The backup is whatever the tablet was carrying before the first test-187
# flash, so this returns the device to its pre-test state exactly.
#
#   reference/boot-tests/test-187-*/rollback.sh baseline
#   reference/boot-tests/test-187-*/rollback.sh late-deferred
#
# SAFETY: writes only `boot` and `vendor_boot`, from the recorded backup, with a
# readback check. Requires adb in recovery.
set -uo pipefail

PROFILE=${1:?usage: rollback.sh <baseline|no-acd|no-gpu|late-deferred>}
ADB=${ADB:-/mnt/d/android/platform-tools/adb.exe}
REPO=$(cd "$(dirname "$0")/../../.." && pwd)
D=$(cd "$(dirname "$0")" && pwd)
STAGE=/home/ms/Samsung/gts9-flash-tests/test-187-$PROFILE
WINIMG=/mnt/d/android/gts9-flash
LOG=$D/rollback-$PROFILE-write-readback.txt

mkdir -p "$WINIMG"
exec > >(tee "$LOG") 2>&1

say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
adbstate() { "$ADB" get-state 2>/dev/null | tr -d '\r' | tail -1; }

[ "$(adbstate)" = "recovery" ] || { say "FATAL: adb state is '$(adbstate)', not recovery"; exit 1; }

for part in boot vendor_boot; do
	src=$STAGE/${part}-before-${PROFILE}.img
	[ -s "$src" ] || { say "FATAL: missing backup $src"; exit 1; }
done

for part in boot vendor_boot; do
	src=$STAGE/${part}-before-${PROFILE}.img
	host_sha=$(sha256sum "$src" | cut -d' ' -f1)
	win="D:\\android\\gts9-flash\\rollback-${part}.img"
	say "--- $part: restoring $host_sha ---"

	cp "$src" "$WINIMG/rollback-${part}.img"
	"$ADB" push "$win" "/tmp/${part}-rb.img" 2>&1 | tail -1
	pushed=$("$ADB" shell "sha256sum /tmp/${part}-rb.img" 2>/dev/null | tr -d '\r' | cut -c1-64)
	[ "$pushed" = "$host_sha" ] || { say "FATAL $part push hash mismatch - stopping"; exit 1; }

	"$ADB" shell "dd if=/tmp/${part}-rb.img of=/dev/block/by-name/$part bs=4096" 2>&1 | tail -1
	"$ADB" shell sync
	"$ADB" shell "rm -f /tmp/${part}-rbchk.img" >/dev/null 2>&1
	"$ADB" shell "dd if=/dev/block/by-name/$part of=/tmp/${part}-rbchk.img bs=1M" 2>&1 | tail -1
	"$ADB" pull "/tmp/${part}-rbchk.img" "$STAGE/${part}-rolledback.img" 2>&1 | tail -1
	after=$(sha256sum "$STAGE/${part}-rolledback.img" | cut -d' ' -f1)
	if [ "$after" = "$host_sha" ]; then
		say "PASS $part restored and verified ($after)"
	else
		say "FATAL $part readback $after != $host_sha"
		exit 1
	fi
done

say "rollback complete: boot + vendor_boot restored to the pre-test-187 pair"
say "reboot with: $ADB shell reboot system"
