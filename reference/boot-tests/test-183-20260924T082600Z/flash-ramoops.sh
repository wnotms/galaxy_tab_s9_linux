#!/usr/bin/env bash
# test-183: verified flash of the ramoops boot pair.
#
#   backup -> SHA256 -> flash -> readback -> SHA256 verify
#
# Both partitions carry the board DTB (boot.img appends it to the kernel
# payload, vendor_boot ships it as its vendor DTB), so they move together:
#
#   boot.img        822ca9dc... -> dfbe70f4779564948cb8d9ce22049c779a8fb271a64795b8131d96e3b1bf5a7b
#   vendor_boot.img 3d65d076... -> eb8f2b211e7a4c4d33a25b542d6c225ea15965e7a9a40890838b7bc7a4de71fb
#
# dtbo/init_boot/vbmeta are byte-identical to the flashed ones and stay put.
set -uo pipefail

ADB=${ADB:-/mnt/d/android/platform-tools/adb.exe}
REPO=/home/ms/Samsung/galaxy_tab_s9_linux
D=$REPO/$(cd "$(dirname "$0")" && pwd | sed "s|$REPO/||")
STAGE=/home/ms/Samsung/gts9-flash-tests/$(basename "$D")
WINIMG=/mnt/d/android/gts9-flash
BUNDLE=$REPO/out/boot-bundle-watchdog-ramoops
LOG=$D/flash-ramoops-write-readback.txt

mkdir -p "$STAGE" "$WINIMG"
exec > >(tee "$LOG") 2>&1

say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
adbstate() { "$ADB" get-state 2>/dev/null | tr -d '\r' | tail -1; }

# partition:expected-current-hash:image
flash_one() {
	local part=$1 expect=$2 img=$3
	local win="D:\\android\\gts9-flash\\${part}-ramoops.img"
	local host_sha
	host_sha=$(sha256sum "$img" | cut -d' ' -f1)
	say "--- $part: host sha256 $host_sha (expected current $expect) ---"

	"$ADB" shell "rm -f /tmp/${part}-before.img /tmp/${part}-new.img /tmp/${part}-after.img" >/dev/null 2>&1
	"$ADB" shell "dd if=/dev/block/by-name/$part of=/tmp/${part}-before.img bs=1M" 2>&1 | tail -1
	"$ADB" pull "/tmp/${part}-before.img" "$STAGE/${part}-ramoops-before.img" 2>&1 | tail -1
	local before
	before=$(sha256sum "$STAGE/${part}-ramoops-before.img" | cut -d' ' -f1)
	if [ "$before" = "$expect" ]; then
		say "PASS $part backup matches the recorded current image ($before)"
	else
		say "FATAL $part backup is $before, expected $expect - stopping"
		return 1
	fi

	cp "$img" "$WINIMG/${part}-ramoops.img"
	"$ADB" push "$win" "/tmp/${part}-new.img" 2>&1 | tail -1
	"$ADB" shell "sha256sum /tmp/${part}-new.img" | tr -d '\r' | tee -a "$LOG"

	"$ADB" shell "dd if=/tmp/${part}-new.img of=/dev/block/by-name/$part bs=4096" 2>&1 | tail -1
	"$ADB" shell sync
	"$ADB" shell "dd if=/dev/block/by-name/$part of=/tmp/${part}-after.img bs=1M" 2>&1 | tail -1
	"$ADB" pull "/tmp/${part}-after.img" "$STAGE/${part}-ramoops-after.img" 2>&1 | tail -1
	local after
	after=$(sha256sum "$STAGE/${part}-ramoops-after.img" | cut -d' ' -f1)
	if [ "$after" = "$host_sha" ]; then
		say "PASS $part readback verifies ($after)"
	else
		say "FATAL $part readback $after != $host_sha - not rebooting"
		return 1
	fi
	return 0
}

say "=== test-183 ramoops boot pair flash ==="

if [ "$(adbstate)" != "recovery" ]; then
	say "asking the tablet for TWRP over the console"
	powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$REPO/scripts/console-run.ps1" \
		-Out 'C:\gts9-work\wd\twrp-trigger-ramoops.log' \
		-Commands 'echo TRIGGER-RAMOOPS; sync; gts9-debian-to-recovery --yes' \
		-WaitReadySeconds 10 -ReadSeconds 4 | tail -4
	timeout 300 "$ADB" wait-for-recovery 2>/dev/null || true
fi
say "adb state: $(adbstate)"
[ "$(adbstate)" = "recovery" ] || { say "FATAL: no adb recovery"; exit 1; }

flash_one boot 822ca9dcf404de83e79f085a5509ec761bf0234359a5fae166c5d1c849e1df86 "$BUNDLE/boot.img" || exit 1
flash_one vendor_boot 3d65d076bcefdbac8df0bd9e5725616886bc55c92ce4316e67cd82abb13c6095 "$BUNDLE/vendor_boot.img" || exit 1

say "--- clear BCB, reboot to system ---"
"$ADB" shell "dd if=/dev/zero of=/dev/block/by-name/misc bs=2048 count=1 conv=notrunc" >/dev/null 2>&1
"$ADB" shell reboot system >/dev/null 2>&1 || true
sleep 5
say "=== flash done ==="
