#!/usr/bin/env bash
# test-183 rollback: put the tablet back on the known-good boot pair.
#
#   boot.img         dfbe70f4... -> 822ca9dc...
#   vendor_boot.img  eb8f2b21... -> 3c88b36b...
#
# Both are the images this repository already had on disk and had flashed
# before this test; the copies used here are the ones pulled back off the
# tablet during the test-183 flashes, so the rollback writes exactly what was
# there.
#
# The device-side additions (three enabled units and their helpers) are inert
# without gts9_watchdog_debug=1, so they do not have to be removed for the
# tablet to behave as before; `systemctl disable --now gts9-kmsg-console
# gts9-watchdog-debug gts9-prev-boot-evidence` removes them as well.
#
#   reference/boot-tests/test-183-*/rollback.sh
set -uo pipefail

ADB=${ADB:-/mnt/d/android/platform-tools/adb.exe}
REPO=/home/ms/Samsung/galaxy_tab_s9_linux
D=$REPO/$(cd "$(dirname "$0")" && pwd | sed "s|$REPO/||")
STAGE=/home/ms/Samsung/gts9-flash-tests/$(basename "$D")
WINIMG=/mnt/d/android/gts9-flash
LOG=$D/rollback-write-readback.txt

mkdir -p "$STAGE" "$WINIMG"
exec > >(tee "$LOG") 2>&1

say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
adbstate() { "$ADB" get-state 2>/dev/null | tr -d '\r' | tail -1; }

# partition:current-hash:known-good-image:known-good-hash
flash_one() {
	local part=$1 expect=$2 img=$3 want=$4
	[ -f "$img" ] || { say "FATAL $part: $img is missing"; return 1; }
	local sha
	sha=$(sha256sum "$img" | cut -d' ' -f1)
	if [ "$sha" != "$want" ]; then
		say "FATAL $part: $img hashes $sha, expected $want"
		return 1
	fi
	say "--- $part: rolling back to $sha ---"
	"$ADB" shell "rm -f /tmp/$part-rb.img" >/dev/null 2>&1
	cp "$img" "$WINIMG/$part-rollback.img"
	"$ADB" push "D:\\android\\gts9-flash\\$part-rollback.img" "/tmp/$part-rb.img" 2>&1 | tail -1
	"$ADB" shell "sha256sum /tmp/$part-rb.img" | tr -d '\r' | tee -a "$LOG"
	"$ADB" shell "dd if=/tmp/$part-rb.img of=/dev/block/by-name/$part bs=4096" 2>&1 | tail -1
	"$ADB" shell sync
	"$ADB" shell "dd if=/dev/block/by-name/$part of=/tmp/$part-rb-after.img bs=1M" 2>&1 | tail -1
	"$ADB" pull "/tmp/$part-rb-after.img" "$STAGE/$part-rollback-after.img" 2>&1 | tail -1
	local after
	after=$(sha256sum "$STAGE/$part-rollback-after.img" | cut -d' ' -f1)
	if [ "$after" = "$want" ]; then
		say "PASS $part readback verifies the known-good image ($after)"
	else
		say "FATAL $part readback $after != $want"
		return 1
	fi
	return 0
}

say "=== test-183 rollback to the known-good boot pair ==="
if [ "$(adbstate)" != "recovery" ]; then
	powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$REPO/scripts/console-run.ps1" \
		-Out 'C:\gts9-work\wd\twrp-trigger-rollback.log' \
		-Commands 'echo TRIGGER-ROLLBACK; sync; gts9-debian-to-recovery --yes' \
		-WaitReadySeconds 10 -ReadSeconds 4 | tail -4
	timeout 300 "$ADB" wait-for-recovery 2>/dev/null || true
fi
say "adb state: $(adbstate)"
[ "$(adbstate)" = "recovery" ] || { say "FATAL: no adb recovery"; exit 1; }

flash_one boot dfbe70f4779564948cb8d9ce22049c779a8fb271a64795b8131d96e3b1bf5a7b \
	"$STAGE/boot-ramoops-before.img" 822ca9dcf404de83e79f085a5509ec761bf0234359a5fae166c5d1c849e1df86 || exit 1
# The full rollback also drops the watchdog profile command line, so this is the
# vendor_boot pulled back during the *first* test-183 flash (3c88b36b), not the
# one pulled during the ramoops flash (3d65d076, which still carries the
# profile).  To keep the profile and only drop ramoops, use
# vendor_boot-ramoops-before.img with expected hash 3d65d076... instead.
flash_one vendor_boot eb8f2b211e7a4c4d33a25b542d6c225ea15965e7a9a40890838b7bc7a4de71fb \
	"$STAGE/vendor_boot-before.img" 3c88b36b7b3f1703ccd751b77522fa6d16596650e627893e3131848c96731dec || exit 1

say "--- clear BCB, reboot to system ---"
"$ADB" shell "dd if=/dev/zero of=/dev/block/by-name/misc bs=2048 count=1 conv=notrunc" >/dev/null 2>&1
"$ADB" shell reboot system >/dev/null 2>&1 || true
say "=== rollback done ==="
