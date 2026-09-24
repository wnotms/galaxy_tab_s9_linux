#!/usr/bin/env bash
# test-182: verified A/B flash of the PCIe-disabled DTBs.
#
#   backup -> SHA256 -> flash -> readback -> SHA256 verify
#
# Flashes boot + vendor_boot from the bundle (both carry the board DTB, so the
# pair must move together).  init_boot, dtbo and vbmeta are untouched.
set -uo pipefail

ADB=${ADB:-/mnt/d/android/platform-tools/adb.exe}
REPO=/home/ms/Samsung/galaxy_tab_s9_linux
D=$REPO/$(cd "$(dirname "$0")" && pwd | sed "s|$REPO/||")
STAGE=/home/ms/Samsung/gts9-flash-tests/$(basename "$D")
WINIMG=/mnt/d/android/gts9-flash
LOG=$D/flash-write-readback.txt

mkdir -p "$STAGE" "$WINIMG"
exec > >(tee "$LOG") 2>&1

say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
adbstate() { "$ADB" get-state 2>/dev/null | tr -d '\r' | tail -1; }

# partition:expected-current-hash:image
flash_one() {
	local part=$1 expect=$2 img=$3
	local win="D:\\android\\gts9-flash\\${part}-pcieoff.img"
	local host_sha
	host_sha=$(sha256sum "$img" | cut -d' ' -f1)
	say "--- $part: host sha256 $host_sha (expected current $expect) ---"

	"$ADB" shell "rm -f /tmp/${part}-before.img /tmp/${part}-new.img /tmp/${part}-after.img" >/dev/null 2>&1
	"$ADB" shell "dd if=/dev/block/by-name/$part of=/tmp/${part}-before.img bs=1M" 2>&1 | tail -1
	"$ADB" pull "/tmp/${part}-before.img" "$STAGE/${part}-before.img" 2>&1 | tail -1
	local before
	before=$(sha256sum "$STAGE/${part}-before.img" | cut -d' ' -f1)
	if [ "$before" = "$expect" ]; then
		say "PASS backup matches the recorded current image ($before)"
	else
		say "WARNING backup is $before, expected $expect - stopping"
		return 1
	fi

	cp "$img" "$WINIMG/${part}-pcieoff.img"
	"$ADB" push "$win" "/tmp/${part}-new.img" 2>&1 | tail -1
	"$ADB" shell "sha256sum /tmp/${part}-new.img 2>/dev/null || true" | tr -d '\r'

	"$ADB" shell "dd if=/tmp/${part}-new.img of=/dev/block/by-name/$part bs=4096" 2>&1 | tail -1
	"$ADB" shell sync
	"$ADB" shell "dd if=/dev/block/by-name/$part of=/tmp/${part}-after.img bs=1M" 2>&1 | tail -1
	"$ADB" pull "/tmp/${part}-after.img" "$STAGE/${part}-after.img" 2>&1 | tail -1
	local after
	after=$(sha256sum "$STAGE/${part}-after.img" | cut -d' ' -f1)
	if [ "$after" = "$host_sha" ]; then
		say "PASS $part readback verifies"
	else
		say "FATAL $part readback $after != $host_sha - not rebooting"
		return 1
	fi
	"$ADB" shell "sha256sum /dev/block/by-name/$part 2>/dev/null || true" | tr -d '\r'
	return 0
}

say "=== test-182 PCIe-disabled flash ==="

if [ "$(adbstate)" != "recovery" ]; then
	say "asking the tablet for TWRP over the console"
	powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$REPO/scripts/console-run.ps1" \
		-Out 'C:\gts9-work\twrp-trigger-182.log' \
		-Commands 'echo TRIGGER182; sync; gts9-debian-to-recovery --yes' \
		-WaitReadySeconds 10 -ReadSeconds 4 | tail -4
	timeout 300 "$ADB" wait-for-recovery 2>/dev/null || true
fi
say "adb state: $(adbstate)"
[ "$(adbstate)" = "recovery" ] || { say "FATAL: no adb recovery"; exit 1; }

flash_one boot 822ca9dcf404de83e79f085a5509ec761bf0234359a5fae166c5d1c849e1df86 "$D/bundle-pcie-off/boot.img" || exit 1
flash_one vendor_boot 3c88b36b7b3f1703ccd751b77522fa6d16596650e627893e3131848c96731dec "$D/bundle-pcie-off/vendor_boot.img" || exit 1

say "--- clear BCB, reboot to system ---"
"$ADB" shell "dd if=/dev/zero of=/dev/block/by-name/misc bs=2048 count=1 conv=notrunc" >/dev/null 2>&1
"$ADB" shell reboot system >/dev/null 2>&1 || true
sleep 5
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$REPO/scripts/console-run.ps1" \
	-Out 'C:\gts9-work\post-flash-182.log' -WaitReadySeconds 240 -ReadSeconds 8 \
	-Commands 'echo POST182; cat /proc/cmdline | tr " " "\n" | grep -E "poweroff_trace|console=" | head -3; echo "pcie0=$(cat /proc/device-tree/soc@0/pcie@1c00000/status)"; dmesg | grep -ac pcie; systemctl is-system-running' | tail -8
say "=== flash done ==="
