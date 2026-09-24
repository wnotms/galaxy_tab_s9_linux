#!/usr/bin/env bash
# test-183: verified flash of the two-port gadget command line (vendor_boot only).
#
#   backup -> SHA256 -> flash -> readback -> SHA256 verify
#
# Only the command line moves this time: console=ttyGS1 instead of ttyGS0, so
# the kernel console lands on the second ACM port and ttyGS0 stays free for the
# login shell.  boot.img is byte-identical to the flashed one (2e8a693f) and is
# left alone.
#
#   vendor_boot.img c9d75311... -> 123f35f2...
#
# dtbo/init_boot/vbmeta are byte-identical to the flashed ones and stay put.
set -uo pipefail

ADB=${ADB:-/mnt/d/android/platform-tools/adb.exe}
REPO=/home/ms/Samsung/galaxy_tab_s9_linux
D=$REPO/$(cd "$(dirname "$0")" && pwd | sed "s|$REPO/||")
STAGE=/home/ms/Samsung/gts9-flash-tests/$(basename "$D")
WINIMG=/mnt/d/android/gts9-flash
BUNDLE=$REPO/out/boot-bundle-watchdog-console2
LOG=$D/flash-console2-write-readback.txt

mkdir -p "$STAGE" "$WINIMG"
exec > >(tee "$LOG") 2>&1

say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
adbstate() { "$ADB" get-state 2>/dev/null | tr -d '\r' | tail -1; }

# partition:expected-current-hash:image
flash_one() {
	local part=$1 expect=$2 img=$3
	local win="D:\\android\\gts9-flash\\${part}-console.img"
	local host_sha
	host_sha=$(sha256sum "$img" | cut -d' ' -f1)
	say "--- $part: host sha256 $host_sha (expected current $expect) ---"

	"$ADB" shell "rm -f /tmp/${part}-before.img /tmp/${part}-new.img /tmp/${part}-after.img" >/dev/null 2>&1
	"$ADB" shell "dd if=/dev/block/by-name/$part of=/tmp/${part}-before.img bs=1M" 2>&1 | tail -1
	"$ADB" pull "/tmp/${part}-before.img" "$STAGE/${part}-console-before.img" 2>&1 | tail -1
	local before
	before=$(sha256sum "$STAGE/${part}-console-before.img" | cut -d' ' -f1)
	if [ "$before" = "$expect" ]; then
		say "PASS $part backup matches the recorded current image ($before)"
	else
		say "FATAL $part backup is $before, expected $expect - stopping"
		return 1
	fi

	cp "$img" "$WINIMG/${part}-console.img"
	"$ADB" push "$win" "/tmp/${part}-new.img" 2>&1 | tail -1
	"$ADB" shell "sha256sum /tmp/${part}-new.img" | tr -d '\r' | tee -a "$LOG"

	"$ADB" shell "dd if=/tmp/${part}-new.img of=/dev/block/by-name/$part bs=4096" 2>&1 | tail -1
	"$ADB" shell sync
	"$ADB" shell "dd if=/dev/block/by-name/$part of=/tmp/${part}-after.img bs=1M" 2>&1 | tail -1
	"$ADB" pull "/tmp/${part}-after.img" "$STAGE/${part}-console-after.img" 2>&1 | tail -1
	local after
	after=$(sha256sum "$STAGE/${part}-console-after.img" | cut -d' ' -f1)
	if [ "$after" = "$host_sha" ]; then
		say "PASS $part readback verifies ($after)"
	else
		say "FATAL $part readback $after != $host_sha - not rebooting"
		return 1
	fi
	return 0
}

say "=== test-183 two-port console command line flash ==="

if [ "$(adbstate)" != "recovery" ]; then
	say "asking the tablet for TWRP over the console"
	powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$REPO/scripts/console-run.ps1" \
		-Out 'C:\gts9-work\wd\twrp-trigger-console.log' \
		-Commands 'echo TRIGGER-CONSOLE; sync; gts9-debian-to-recovery --yes' \
		-WaitReadySeconds 10 -ReadSeconds 4 | tail -4
	timeout 300 "$ADB" wait-for-recovery 2>/dev/null || true
fi
say "adb state: $(adbstate)"
[ "$(adbstate)" = "recovery" ] || { say "FATAL: no adb recovery"; exit 1; }

flash_one vendor_boot c9d7531116ba0e4424a0b059eaa683815f39bf479894eadd8556327fb7c53242 "$BUNDLE/vendor_boot.img" || exit 1

say "--- clear BCB, reboot to system ---"
"$ADB" shell "dd if=/dev/zero of=/dev/block/by-name/misc bs=2048 count=1 conv=notrunc" >/dev/null 2>&1
"$ADB" shell reboot system >/dev/null 2>&1 || true
sleep 5
say "=== flash done ==="
