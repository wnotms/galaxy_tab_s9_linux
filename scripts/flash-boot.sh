#!/usr/bin/env bash
#
# Flash one image to a by-name partition and come back to mainline, with every
# wait either event-driven or measured.
#
#   scripts/flash-boot.sh out/boot-bundle-testNNN/boot.img [partition]
#
# Phases are timestamped and printed as a table at the end, because the two legs of
# a cycle cost very different amounts: the tablet's own boot into TWRP (~2.5 min,
# measured: 14:01:02 trigger -> ~14:03:40 recovery in test 098) and its boot back
# into mainline (~26 s, measured).
#
# The recovery leg is only used because mainline's initramfs has no adbd.  If the
# owner opts into a data channel in mainline (see the note at the end), this script
# gains a --direct mode and the whole TWRP leg disappears.
set -euo pipefail

IMG=${1:?usage: flash-boot.sh <image> [partition]}
PART=${2:-boot}
ADB=${ADB:-/mnt/d/android/platform-tools/adb.exe}
PORT=${PORT:-COM17}
REPO=$(cd "$(dirname "$0")/.." && pwd)
STAGE=${STAGE:-/mnt/d/android/gts9-flash}
LOG=${LOG:-$STAGE/flash.log}
WIN_LOG=${WIN_LOG:-D:\\android\\gts9-flash\\flash.log}
RECOVERY_TIMEOUT=${RECOVERY_TIMEOUT:-300}
SHELL_TIMEOUT=${SHELL_TIMEOUT:-120}

mkdir -p "$STAGE"
cp "$IMG" "$STAGE/$(basename "$PART").img"
WIN_IMG="D:\\android\\gts9-flash\\$(basename "$PART").img"
HOST_SHA=$(sha256sum "$STAGE/$(basename "$PART").img" | cut -d' ' -f1)

phase() { echo "$(date -u +%T) $*"; }
declare -a TIMES=()
mark() { TIMES+=("$1=$(( $(date +%s) - T0 ))s"); }

T0=$(date +%s)
# adb.exe is a Windows binary: its output arrives with CRLF, and an unstripped
# trailing CR makes "recovery\r" compare unequal to "recovery".
state=$($ADB get-state 2>/dev/null | tr -d '\r' | tail -1 || true)
phase "device state: ${state:-none}"

if [ "$state" != "recovery" ]; then
	phase "asking the tablet for recovery over the console (BCB, no sleep, no polling)"
	"$REPO/scripts/console-run.sh" \
		-Out "$WIN_LOG" -Commands 'gts9-to-recovery' -WaitReadySeconds 10 -ReadSeconds 3 >/dev/null
fi
mark trigger

phase "waiting for adbd in recovery (blocking, single adb process)"
if ! timeout "$RECOVERY_TIMEOUT" "$ADB" wait-for-recovery 2>/dev/null; then
	# Older platform-tools lack wait-for-recovery: fall back to a one-second poll.
	deadline=$(( $(date +%s) + RECOVERY_TIMEOUT ))
	while [ "$(date +%s)" -lt "$deadline" ]; do
		if [ "$($ADB get-state 2>/dev/null | tr -d '\r' | tail -1)" = "recovery" ]; then
			break
		fi
		sleep 1
	done
fi
[ "$($ADB get-state 2>/dev/null | tr -d '\r' | tail -1)" = "recovery" ] || { phase "no adb recovery"; exit 1; }
mark recovery

phase "pushing and writing $PART"
"$ADB" push "$WIN_IMG" "/tmp/$(basename "$PART").img" | tail -1
"$ADB" shell "dd if=/tmp/$(basename "$PART").img of=/dev/block/by-name/$PART bs=4096" 2>&1 | tail -1
readback=$($ADB shell "sha256sum /dev/block/by-name/$PART | cut -c1-64" 2>/dev/null | tr -d '\r')
phase "read-back $readback"
[ "$readback" = "$HOST_SHA" ] || { phase "READ-BACK MISMATCH (expected $HOST_SHA) - not rebooting"; exit 1; }
mark write

phase "clearing the BCB and rebooting to system"
"$ADB" shell "dd if=/dev/zero of=/dev/block/by-name/misc bs=2048 count=1 conv=notrunc" >/dev/null 2>&1
"$ADB" shell 'reboot system' >/dev/null 2>&1 || true
mark reboot

phase "waiting for the mainline shell (console heartbeat)"
"$REPO/scripts/console-run.sh" \
	-Out "$WIN_LOG" -Commands 'uname -a' -WaitReadySeconds "$SHELL_TIMEOUT" -ReadSeconds 4 \
	| grep -aE "shell answered|Linux \(none\)" | tail -2 || true
mark shell

phase "phase table"
for t in "${TIMES[@]}"; do echo "  $t"; done
