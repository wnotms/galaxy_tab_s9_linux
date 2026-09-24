#!/usr/bin/env bash
# test-187: verified flash of one A/B profile, after backing up whatever the
# tablet currently has.
#
#   backup -> SHA256 -> flash -> readback -> SHA256 verify -> (operator reboots)
#
# Unlike test-183's flash-ramoops.sh this does NOT assert a pre-recorded
# expected-current hash: the tablet may be carrying any earlier profile, and
# asserting a stale expectation would abort for the wrong reason. Instead it
# records whatever it finds, keeps it, and that backup becomes the rollback
# source. The flash itself is still verified by readback.
#
# Both partitions carry the board DTB (boot.img has it appended, vendor_boot.img
# ships it as the vendor DTB), so they are always written as a pair.
#
#   reference/boot-tests/test-187-*/flash-profile.sh baseline
#   reference/boot-tests/test-187-*/flash-profile.sh late-deferred
#
# SAFETY: writes only the `boot` and `vendor_boot` partitions. Never touches
# dtbo, init_boot, vbmeta, misc/BCB, recovery, userdata or the partition table.
# The tablet must already be in TWRP recovery with adb up.
set -uo pipefail

PROFILE=${1:?usage: flash-profile.sh <baseline|no-acd|no-gpu|late-deferred>}
ADB=${ADB:-/mnt/d/android/platform-tools/adb.exe}
REPO=$(cd "$(dirname "$0")/../../.." && pwd)
D=$(cd "$(dirname "$0")" && pwd)
BUNDLE=$REPO/out/boot-bundle-test187-$PROFILE
STAGE=/home/ms/Samsung/gts9-flash-tests/test-187-$PROFILE
WINIMG=/mnt/d/android/gts9-flash
LOG=$D/flash-$PROFILE-write-readback.txt

case "$PROFILE" in
	baseline|no-acd|no-gpu|late-deferred) ;;
	*) echo "unknown profile: $PROFILE" >&2; exit 2 ;;
esac
[ -d "$BUNDLE" ] || { echo "missing bundle: $BUNDLE" >&2; exit 1; }

mkdir -p "$STAGE" "$WINIMG"
exec > >(tee "$LOG") 2>&1

say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
adbstate() { "$ADB" get-state 2>/dev/null | tr -d '\r' | tail -1; }

[ "$(adbstate)" = "recovery" ] || { say "FATAL: adb state is '$(adbstate)', not recovery"; exit 1; }

say "profile=$PROFILE bundle=$BUNDLE"
say "host boot.img        $(sha256sum "$BUNDLE/boot.img" | cut -d' ' -f1)"
say "host vendor_boot.img $(sha256sum "$BUNDLE/vendor_boot.img" | cut -d' ' -f1)"

# --- backup whatever is currently flashed (rollback source) -------------------
for part in boot vendor_boot; do
	"$ADB" shell "rm -f /tmp/${part}-current.img" >/dev/null 2>&1
	"$ADB" shell "dd if=/dev/block/by-name/$part of=/tmp/${part}-current.img bs=1M" 2>&1 | tail -1
	"$ADB" pull "/tmp/${part}-current.img" "$STAGE/${part}-before-${PROFILE}.img" 2>&1 | tail -1
	if [ -s "$STAGE/${part}-before-${PROFILE}.img" ]; then
		say "BACKUP $part -> $STAGE/${part}-before-${PROFILE}.img $(sha256sum "$STAGE/${part}-before-${PROFILE}.img" | cut -d' ' -f1)"
	else
		say "FATAL: $part backup is empty - stopping before any write"
		exit 1
	fi
done

# --- flash ------------------------------------------------------------------
for part in boot vendor_boot; do
	img=$BUNDLE/$part.img
	host_sha=$(sha256sum "$img" | cut -d' ' -f1)
	win="D:\\android\\gts9-flash\\test187-${part}.img"
	say "--- $part: writing host sha256 $host_sha ---"

	cp "$img" "$WINIMG/test187-${part}.img"
	"$ADB" push "$win" "/tmp/${part}-new.img" 2>&1 | tail -1
	pushed=$("$ADB" shell "sha256sum /tmp/${part}-new.img" 2>/dev/null | tr -d '\r' | cut -c1-64)
	if [ "$pushed" = "$host_sha" ]; then
		say "PASS $part push verified on device ($pushed)"
	else
		say "FATAL $part push hash $pushed != $host_sha - stopping"
		exit 1
	fi

	"$ADB" shell "dd if=/tmp/${part}-new.img of=/dev/block/by-name/$part bs=4096" 2>&1 | tail -1
	"$ADB" shell sync
	"$ADB" shell "rm -f /tmp/${part}-after.img" >/dev/null 2>&1
	"$ADB" shell "dd if=/dev/block/by-name/$part of=/tmp/${part}-after.img bs=1M" 2>&1 | tail -1
	"$ADB" pull "/tmp/${part}-after.img" "$STAGE/${part}-after-${PROFILE}.img" 2>&1 | tail -1
	after=$(sha256sum "$STAGE/${part}-after-${PROFILE}.img" | cut -d' ' -f1)
	if [ "$after" = "$host_sha" ]; then
		say "PASS $part readback verifies ($after)"
	else
		say "FATAL $part readback $after != $host_sha - the pair is now INCONSISTENT"
		say "restore with: $D/rollback.sh"
		exit 1
	fi
done

say "flash complete and verified: boot + vendor_boot now hold test-187 profile '$PROFILE'"
say "backup kept at $STAGE/{boot,vendor_boot}-before-${PROFILE}.img"
say "NEXT: reboot the tablet.  The initramfs clears the BCB, so a plain reset is enough:"
say "  $ADB shell reboot system"
say "then run:  GTS9_ALLOW_POWER=1 $REPO/scripts/stall-ab.sh $PROFILE 5"
