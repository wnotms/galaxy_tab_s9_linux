#!/usr/bin/env bash
# Read the bring-up state word that /init left in the tablet's RTC.
#
# Why the RTC: on this board the persistent ring is overwritten by the
# bootloader, USB never presents a device, the panel never refreshes, and UFS -
# the only internal storage - does not enumerate, so `cache`, `misc` and every
# other partition are out of reach.  The PMK8550 RTC is battery backed, is
# driven by a mainline driver that is built in, and busybox can set it.  /init
# therefore writes one 16-bit state word there as the time of 2031-01-01, and
# this script reads it back through adb - no timing, no owner, no storage.
#
#	ADB=/mnt/d/android/platform-tools/adb.exe ./scripts/read-rtc-state.sh
#
# Encoding (see docs/RTC_REPORT.md):
#
#	code = (epoch of the RTC clock) - (epoch of 2031-01-01T00:00:00Z)
#
# The value is read from /proc/driver/rtc, which reports the RTC registers
# themselves.  That matters: Samsung's recovery kernel applies an RTC offset
# kept in the PMIC (/proc/driver/rtc shows 1970 while `date` shows 2026), and
# mainline has no offset cell in its DT, so /init writes the registers raw.
# Reading `date` instead of the registers would look at a value shifted by that
# offset.  The corrected clock is only printed for context.
#	bits 0-3    microSD stage      bits 4-7   UFS stage
#	bit  8      USB device controller registered
#	bit  9      sdhc_2 in the deferred-probe list
#	bit  10     ufshc in the deferred-probe list
#	bit  11     the bring-up report was persisted somewhere
#	bits 12-15  checksum = nibble sum of bits 0-11
#
# Read-only on the tablet: one `date` call.
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
adb=${ADB:-adb}
wait_seconds=${WAIT_TIMEOUT:-1800}
base=1924992000          # 2031-01-01T00:00:00Z, the marker date

while [ $# -gt 0 ]; do
    case "$1" in
        --adb) adb=$2; shift 2 ;;
        --wait) wait_seconds=$2; shift 2 ;;
        --epoch) epoch=$2; shift 2 ;;
        -h|--help) sed -n '2,26p' "$0"; exit 0 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

stage_name() {
    case "$1" in
        0) echo 'no platform device (the DT node is missing or disabled)' ;;
        1) echo 'platform device present, no driver bound' ;;
        2) echo 'driver bound, no host registered' ;;
        3) echo 'host registered, no device' ;;
        4) echo 'device present, no block device' ;;
        5) echo 'block device present' ;;
        *) echo "invalid stage $1" ;;
    esac
}

device_present() {
    "$adb" devices 2>/dev/null | tr -d '\r' \
        | awk 'NR > 1 && $2 ~ /^(device|recovery)$/ { found = 1 } END { exit !found }'
}

if [ -z "${epoch:-}" ]; then
    command -v "$adb" >/dev/null 2>&1 || {
        echo "adb not found: $adb (set ADB=/path/to/adb)" >&2
        exit 2
    }
    echo "waiting up to ${wait_seconds}s for the tablet (recovery is enough)..."
    deadline=$((SECONDS + wait_seconds))
    while [ "$SECONDS" -lt "$deadline" ]; do
        device_present && break
        sleep 3
    done
    device_present || { echo 'timed out waiting for adb to see the tablet' >&2; exit 1; }

    rtc=$(timeout 60 "$adb" shell 'cat /proc/driver/rtc' 2>/dev/null | tr -d '\r')
    raw_date=$(sed -n 's/^rtc_date[[:space:]]*:[[:space:]]*//p' <<<"$rtc")
    raw_time=$(sed -n 's/^rtc_time[[:space:]]*:[[:space:]]*//p' <<<"$rtc")
    [ -n "$raw_date" ] && [ -n "$raw_time" ] || {
        echo 'could not read the RTC registers (/proc/driver/rtc)' >&2
        exit 1
    }
    epoch=$(date -u -d "$raw_date $raw_time" +%s 2>/dev/null) || {
        echo "cannot parse the RTC registers: '$raw_date $raw_time'" >&2
        exit 1
    }
    corrected=$(timeout 60 "$adb" shell 'date -u +%Y-%m-%dT%H:%M:%SZ' 2>/dev/null | tr -d '\r')
    echo "RTC registers: $raw_date $raw_time (UTC)"
    echo "system clock : ${corrected:-unknown}  <- recovery applies Samsung's PMIC offset"
fi

code=$((epoch - base))
echo "code     : $code"

if [ "$code" -lt 0 ] || [ "$code" -gt 86399 ]; then
    cat >&2 <<EOF
The clock is not in 2031-01-01, so /init did not leave a state word:
either it never ran (check the power-off telemetry), the RTC write failed,
or the clock has since been set from somewhere else.
EOF
    exit 1
fi

state=$((code & 0xFFF))
chk=$(( (code >> 12) & 0xF ))
want=$(( ( (state & 15) + ((state >> 4) & 15) + ((state >> 8) & 15) ) & 15 ))
if [ "$chk" != "$want" ]; then
    echo "checksum mismatch: frame says $chk, the state nibbles sum to $want" >&2
    echo 'the RTC write was probably rounded: treat this reading as unusable' >&2
    exit 1
fi

mmc_stage=$((state & 15))
ufs_stage=$(((state >> 4) & 15))
echo
printf 'microSD  : stage %s - %s\n' "$mmc_stage" "$(stage_name "$mmc_stage")"
printf 'UFS      : stage %s - %s\n' "$ufs_stage" "$(stage_name "$ufs_stage")"
printf 'USB UDC  : %s\n' "$([ $(( (state >> 8) & 1 )) = 1 ] && echo 'registered' || echo 'absent')"
printf 'sdhc_2   : %s\n' "$([ $(( (state >> 9) & 1 )) = 1 ] && echo 'in the deferred-probe list' || echo 'not deferred')"
printf 'ufshc    : %s\n' "$([ $(( (state >> 10) & 1 )) = 1 ] && echo 'in the deferred-probe list' || echo 'not deferred')"
printf 'report   : %s\n' "$([ $(( (state >> 11) & 1 )) = 1 ] && echo 'persisted somewhere' || echo 'not persisted')"
echo
echo 'stage 2 with "not deferred" means the driver probed and found no card;'
echo 'stage 0/1 with "deferred" means a supplier never arrived - see'
echo '/sys/kernel/debug/devices_deferred and the regulator summary in the report.'
