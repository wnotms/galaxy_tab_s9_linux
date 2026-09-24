#!/usr/bin/env bash
# test-183: verified flash of the watchdog-debug vendor_boot.
#
#   backup -> SHA256 -> flash -> readback -> SHA256 verify
#
# Only vendor_boot changes: the command line lives there, and the bundle's
# boot.img/dtbo/init_boot/vbmeta are byte-identical to the flashed ones (this
# was checked before flashing, see bundle-compare.txt).  The DTB does not move,
# so the pair does not have to move together this time.
#
#   before: 3c88b36b7b3f1703ccd751b77522fa6d16596650e627893e3131848c96731dec
#   after:  3d65d076bcefdbac8df0bd9e5725616886bc55c92ce4316e67cd82abb13c6095
set -uo pipefail

ADB=${ADB:-/mnt/d/android/platform-tools/adb.exe}
REPO=/home/ms/Samsung/galaxy_tab_s9_linux
D=$REPO/$(cd "$(dirname "$0")" && pwd | sed "s|$REPO/||")
STAGE=/home/ms/Samsung/gts9-flash-tests/$(basename "$D")
WINIMG=/mnt/d/android/gts9-flash
IMG=$REPO/out/boot-bundle-watchdog-debug/vendor_boot.img
LOG=$D/flash-write-readback.txt
BEFORE=3c88b36b7b3f1703ccd751b77522fa6d16596650e627893e3131848c96731dec

mkdir -p "$STAGE" "$WINIMG"
exec > >(tee "$LOG") 2>&1

say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
adbstate() { "$ADB" get-state 2>/dev/null | tr -d '\r' | tail -1; }

say "=== test-183 watchdog-debug vendor_boot flash ==="
host_sha=$(sha256sum "$IMG" | cut -d' ' -f1)
say "image: $IMG"
say "host sha256: $host_sha"
[ "$host_sha" = 3d65d076bcefdbac8df0bd9e5725616886bc55c92ce4316e67cd82abb13c6095 ] ||
	say "WARNING: image hash is not the recorded 3d65d076..."

if [ "$(adbstate)" != "recovery" ]; then
	say "asking the tablet for TWRP over the console"
	powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$REPO/scripts/console-run.ps1" \
		-Out 'C:\gts9-work\wd\twrp-trigger-183.log' \
		-Commands 'echo TRIGGER183; sync; gts9-debian-to-recovery --yes' \
		-WaitReadySeconds 10 -ReadSeconds 4 | tail -4
	timeout 300 "$ADB" wait-for-recovery 2>/dev/null || true
fi
say "adb state: $(adbstate)"
[ "$(adbstate)" = "recovery" ] || { say "FATAL: no adb recovery"; exit 1; }

part=vendor_boot
say "--- backup /dev/block/by-name/$part ---"
"$ADB" shell "rm -f /tmp/$part-before.img /tmp/$part-new.img /tmp/$part-after.img" >/dev/null 2>&1
"$ADB" shell "dd if=/dev/block/by-name/$part of=/tmp/$part-before.img bs=1M" 2>&1 | tail -1
"$ADB" pull "/tmp/$part-before.img" "$STAGE/$part-before.img" 2>&1 | tail -1
before=$(sha256sum "$STAGE/$part-before.img" | cut -d' ' -f1)
if [ "$before" = "$BEFORE" ]; then
	say "PASS backup matches the recorded known-good image ($before)"
else
	say "FATAL backup is $before, expected $BEFORE - stopping"
	exit 1
fi

say "--- flash ---"
cp "$IMG" "$WINIMG/vendor_boot-watchdog-debug.img"
"$ADB" push "D:\\android\\gts9-flash\\vendor_boot-watchdog-debug.img" "/tmp/$part-new.img" 2>&1 | tail -1
"$ADB" shell "sha256sum /tmp/$part-new.img" | tr -d '\r' | tee "$STAGE/$part-new.sha256.txt"
"$ADB" shell "dd if=/tmp/$part-new.img of=/dev/block/by-name/$part bs=4096" 2>&1 | tail -1
"$ADB" shell sync
"$ADB" shell "dd if=/dev/block/by-name/$part of=/tmp/$part-after.img bs=1M" 2>&1 | tail -1
"$ADB" pull "/tmp/$part-after.img" "$STAGE/$part-after.img" 2>&1 | tail -1
after=$(sha256sum "$STAGE/$part-after.img" | cut -d' ' -f1)
if [ "$after" = "$host_sha" ]; then
	say "PASS $part readback verifies ($after)"
else
	say "FATAL $part readback $after != $host_sha - not rebooting"
	exit 1
fi

say "--- clear BCB, reboot to system ---"
"$ADB" shell "dd if=/dev/zero of=/dev/block/by-name/misc bs=2048 count=1 conv=notrunc" >/dev/null 2>&1
"$ADB" shell reboot system >/dev/null 2>&1 || true
sleep 5
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$REPO/scripts/console-run.ps1" \
	-Out 'C:\gts9-work\wd\post-flash-183.log' -WaitReadySeconds 300 -ReadSeconds 12 \
	-Commands 'echo POST183;echo cmdline=$(cat /proc/cmdline | tr " " "\n" | grep -c gts9_watchdog_debug);echo slp=$(cat /proc/sys/kernel/softlockup_panic) wd=$(cat /proc/sys/kernel/watchdog) htp=$(cat /proc/sys/kernel/hung_task_panic) wq=$(cat /sys/module/workqueue/parameters/panic_on_stall_time) panic=$(cat /proc/sys/kernel/panic);echo mirror=$(systemctl is-active gts9-kmsg-console.service);echo collector=$(systemctl is-active gts9-prev-boot-evidence.service);echo evidence=$(ls -1d /var/log/gts9-boot-evidence/*/ 2>/dev/null | wc -l);head -3 /var/log/gts9-watchdog-debug.txt;systemctl is-system-running' | tail -14
say "=== flash done ==="
