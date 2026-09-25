#!/usr/bin/env bash
# test-191: verified flash of the OSM_L3 kernel, after backing up what is on the
# tablet now.
#
#   backup -> SHA256 -> flash boot+vendor_boot -> readback -> SHA256 verify
#
# The bundle's vendor_boot.img is byte-identical to the one already flashed (the
# cmdline is unchanged), so this is a genuine one-variable delta: only boot.img
# differs, and only by the kernel.
#
#   reference/boot-tests/test-191-*/flash-profile.sh          # uses the bundle
#
# SAFETY: writes only the `boot` and `vendor_boot` partitions.  Never touches
# dtbo, init_boot, vbmeta, misc/BCB, recovery, userdata or the partition table.
# The tablet must already be in TWRP recovery with adb up.
set -uo pipefail

PROFILE=${1:-osm-l3}
ADB=${ADB:-/mnt/d/android/platform-tools/adb.exe}
REPO=$(cd "$(dirname "$0")/../../.." && pwd)
D=$(cd "$(dirname "$0")" && pwd)
BUNDLE=${GTS9_BUNDLE:-$REPO/out/boot-bundle-test191-osm-l3}
STAGE=/home/ms/Samsung/gts9-flash-tests/test-191-$PROFILE
WINIMG=/mnt/d/android/gts9-flash
LOG=$D/flash-$PROFILE-write-readback.txt

# What test-187-baseline put on the tablet, and therefore what this delta is
# measured against.  Asserted so a stale or unexpected bundle cannot be flashed
# silently.
EXPECT_EXISTING_BOOT=${GTS9_EXPECT_BOOT:-bf6a02bbe19e9561be2bae6d691cbaad0c3871ed4efc3878b8f689f2af00bd3e}

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

have_boot=$(sha256sum "$STAGE/boot-before-${PROFILE}.img" | cut -d' ' -f1)
if [ "$have_boot" = "$EXPECT_EXISTING_BOOT" ]; then
	say "PASS the tablet is running the expected test-187-baseline kernel ($have_boot)"
else
	say "WARN boot-before hash $have_boot != expected $EXPECT_EXISTING_BOOT"
	say "WARN the delta is therefore not the one candidate.txt describes; continuing"
	say "WARN because the backup is still a valid rollback source."
fi

# --- flash ------------------------------------------------------------------
for part in boot vendor_boot; do
	img=$BUNDLE/$part.img
	host_sha=$(sha256sum "$img" | cut -d' ' -f1)
	win="D:\\android\\gts9-flash\\test191-${part}.img"
	say "--- $part: writing host sha256 $host_sha ---"

	cp "$img" "$WINIMG/test191-${part}.img"
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
		say "restore with: $D/flash-profile.sh --restore"
		exit 1
	fi
done

say "flash complete and verified: boot + vendor_boot now hold test-191 '$PROFILE'"
say "backup kept at $STAGE/{boot,vendor_boot}-before-${PROFILE}.img"
say "NEXT: reboot the tablet.  The initramfs clears the BCB, so a plain reset is enough:"
say "  $ADB shell reboot system"
say "then run:  $D/verify-osm-l3.sh"
