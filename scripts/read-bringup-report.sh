#!/usr/bin/env bash
# Read back the bring-up report that boot/bringup-init.sh persisted on the
# tablet, either from the internal cache partition or from a local image.
#
# Why this exists: the report is the only copy of the mainline dmesg that the
# boot can produce - the persistent ring, USB and the panel have all failed as
# log channels for the SM-X710.  /init therefore writes it to a medium that
# survives the power-off, and this script is the host half of that channel.
#
# Two layouts are understood:
#
#   raw block    "GTS9RPT1 total=<8d> body=<8d> sha256=<hex> release=<rel>"
#                followed by the report, at offset 0 of the partition.  The
#                body is verified against the SHA-256 recorded by /init.
#   filesystem   <mountpoint>/gts9-bringup-report.txt, written when the cache
#                filesystem mounted read-write during boot.
#
#	ADB=/mnt/d/android/platform-tools/adb.exe ./scripts/read-bringup-report.sh \
#	    --out reference/boot-tests/test-017-.../bringup-report.txt
#
#	# offline check of a partition dump instead of a tablet:
#	./scripts/read-bringup-report.sh --image /tmp/cache.img --out /tmp/report.txt
#
# Read-only on the tablet: it only runs dd/cat that read the partition, and the
# only thing it mounts is the cache partition, read-only.
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
adb=${ADB:-adb}
device=${REPORT_DEVICE:-/dev/block/by-name/cache}
mount_points=${REPORT_MOUNTS:-/tmp/gts9-report-mnt}
out=
image=
wait_seconds=${WAIT_TIMEOUT:-1800}
block_bytes=4096

usage() {
    sed -n '2,30p' "$0"
}

while [ $# -gt 0 ]; do
    case "$1" in
        --out) out=$2; shift 2 ;;
        --device) device=$2; shift 2 ;;
        --image) image=$2; shift 2 ;;
        --wait) wait_seconds=$2; shift 2 ;;
        --adb) adb=$2; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

# This tool must never write to a partition.  Fail closed if an edit ever adds
# a write path: the pattern is assembled from pieces so that the check cannot
# match its own source line.
write_pattern='of[[:space:]]*=[[:space:]]*/dev'
if grep -qE "dd[[:space:]].*${write_pattern}" "$0"; then
    echo "refusing to run: $0 contains what looks like a write to a block device" >&2
    exit 1
fi

if [ -z "$image" ]; then
    command -v "$adb" >/dev/null 2>&1 || {
        echo "adb not found: $adb (set ADB=/path/to/adb)" >&2
        exit 2
    }
fi

# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------
device_present() {
    "$adb" devices 2>/dev/null | tr -d '\r' \
        | awk 'NR > 1 && $2 ~ /^(device|recovery)$/ { found = 1 } END { exit !found }'
}

fetch_blocks() {
    # fetch_blocks <count> -> <count> * 4096 bytes on stdout
    if [ -n "$image" ]; then
        dd if="$image" bs="$block_bytes" count="$1" 2>/dev/null
    else
        # exec-out is binary clean, unlike `adb shell`.
        timeout 300 "$adb" exec-out dd if="$device" bs="$block_bytes" count="$1" 2>/dev/null
    fi
}

fetch_file() {
    # fetch_file <path on the tablet>
    if [ -n "$image" ]; then
        cat "$1"
    else
        timeout 300 "$adb" exec-out cat "$1" 2>/dev/null
    fi
}

wait_for_device() {
    [ -n "$image" ] && return 0
    echo "waiting up to ${wait_seconds}s for the tablet..."
    local deadline=$((SECONDS + wait_seconds))
    while [ "$SECONDS" -lt "$deadline" ]; do
        device_present && return 0
        sleep 3
    done
    echo 'timed out waiting for adb to see the tablet' >&2
    return 1
}

# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
# GTS9RPT1 total=00058971 body=00058821 sha256=<64 hex> release=<release>
parse_header() {
    # parse_header <file with the first block> -> "total body sha256 release"
    local hdr
    # tr also drops the NUL bytes of a filesystem superblock, so bash never
    # has to warn about ignoring them.
    hdr=$(head -c 512 "$1" | tr -d '\0\r' | head -1)
    case "$hdr" in
        GTS9RPT1*) ;;
        *) return 1 ;;
    esac
    local total body sha release
    total=$(sed -n 's/.* total=0*\([0-9][0-9]*\).*/\1/p' <<<"$hdr")
    body=$(sed -n 's/.* body=0*\([0-9][0-9]*\).*/\1/p' <<<"$hdr")
    sha=$(sed -n 's/.* sha256=\([0-9a-f][0-9a-f]*\).*/\1/p' <<<"$hdr")
    release=$(sed -n 's/.* release=\([^ ]*\).*/\1/p' <<<"$hdr")
    [ -n "$total" ] && [ -n "$body" ] && [ -n "$sha" ] || return 1
    [ "$body" -gt 0 ] && [ "$total" -gt "$body" ] || return 1
    printf '%s %s %s %s\n' "$total" "$body" "$sha" "${release:-unknown}"
}

sanity_limits() {
    # sanity_limits <total> <body>
    [ "$1" -le $((64 * 1024 * 1024)) ] && [ "$2" -le $((64 * 1024 * 1024)) ] || {
        echo "refusing: implausible sizes total=$1 body=$2" >&2
        return 1
    }
}

fetch_raw_report() {
    # fetch_raw_report <total> <body> <sha256> <destination>
    local total=$1 body=$2 want=$3 dest=$4
    local blocks=$(( (total + block_bytes - 1) / block_bytes ))
    local hlen got size

    echo "reading $total bytes ($blocks blocks of $block_bytes) from $source_name"
    fetch_blocks "$blocks" > "$tmp/block.bin"
    size=$(stat -c %s "$tmp/block.bin")
    [ "$size" -ge "$total" ] || {
        echo "short read: got $size bytes, expected at least $total" >&2
        return 1
    }
    hlen=$((total - body))
    tail -c +$((hlen + 1)) "$tmp/block.bin" | head -c "$body" > "$tmp/body.bin"
    got=$(sha256sum "$tmp/body.bin" | cut -d' ' -f1)
    if [ "$got" != "$want" ]; then
        echo "SHA-256 mismatch: report says $want, the bytes read back hash to $got" >&2
        echo "the partition was probably rewritten since the boot" >&2
        return 1
    fi
    mv "$tmp/body.bin" "$dest"
    echo "sha256 verified: $got"
    return 0
}

# Where recovery exposes a card.  TWRP uses /external_sd; the others are here
# because the mount point is recovery's choice, not ours.
removable_paths='/external_sd /sdcard1 /mnt/sdcard1 /mnt/media_rw /usb_otg /storage'

fetch_removable_report() {
    # fetch_removable_report <destination>
    local dest=$1 mp got want
    if [ -n "$image" ]; then
        echo 'an image was given: removable media cannot be searched' >&2
        return 1
    fi
    for mp in $removable_paths /storage/*; do
        if timeout 60 "$adb" shell "test -r $mp/gts9-bringup-report.txt" >/dev/null 2>&1; then
            echo "reading $mp/gts9-bringup-report.txt"
            fetch_file "$mp/gts9-bringup-report.txt" > "$dest" || return 1
            [ -s "$dest" ] || { echo "read nothing from $mp" >&2; return 1; }
            want=$(timeout 60 "$adb" shell "cat $mp/gts9-bringup-report.txt.sha256" 2>/dev/null                    | tr -d '\r' | awk '{print $1}')
            if [ -n "$want" ]; then
                got=$(sha256sum "$dest" | cut -d' ' -f1)
                if [ "$got" = "$want" ]; then
                    echo "sha256 verified: $got"
                else
                    echo "WARNING: sidecar says $want, the copy hashes to $got" >&2
                fi
            else
                echo "note: no .sha256 sidecar on the card, the copy is unverified"
            fi
            return 0
        fi
    done
    return 1
}

fetch_mounted_report() {
    # fetch_mounted_report <destination>
    local dest=$1 mp
    if [ -n "$image" ]; then
        echo 'an image was given: only the raw layout can be read from it' >&2
        return 1
    fi
    for mp in /cache ${mount_points//,/ }; do
        if timeout 60 "$adb" shell "test -r $mp/gts9-bringup-report.txt" >/dev/null 2>&1; then
            echo "reading $mp/gts9-bringup-report.txt"
            fetch_file "$mp/gts9-bringup-report.txt" > "$dest"
            [ -s "$dest" ] || { echo "read nothing from $mp" >&2; return 1; }
            return 0
        fi
    done
    echo "no raw header and no mounted report; trying a read-only mount of $device"
    for mp in ${mount_points//,/ }; do
        if timeout 60 "$adb" shell "mkdir -p $mp; mount -t ext4 -o ro $device $mp 2>/dev/null; test -r $mp/gts9-bringup-report.txt" >/dev/null 2>&1; then
            fetch_file "$mp/gts9-bringup-report.txt" > "$dest"
            [ -s "$dest" ] || { echo "read nothing from $mp" >&2; return 1; }
            return 0
        fi
    done
    return 1
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
[ -n "$out" ] || { echo 'an --out path is required' >&2; exit 2; }
source_name=${image:-$device}

wait_for_device
mkdir -p "$(dirname "$out")"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

fetch_blocks 1 > "$tmp/head.bin"
if [ ! -s "$tmp/head.bin" ]; then
    echo "could not read $device" >&2
    exit 1
fi

if header=$(parse_header "$tmp/head.bin"); then
    set -- $header
    total=$1 body=$2 sha=$3 release=$4
    sanity_limits "$total" "$body"
    echo "raw report block found: release=$release body=$body sha256=$sha"
    if fetch_raw_report "$total" "$body" "$sha" "$out"; then
        :
    else
        exit 1
    fi
elif fetch_mounted_report "$out"; then
    :                   # cache carried the report as a file
else
    echo 'nothing on the internal cache partition: searching removable media'
    fetch_removable_report "$out" || {
        echo 'no bring-up report found on the tablet' >&2
        exit 1
    }
fi

size=$(stat -c %s "$out")
echo
echo "report   : $out"
echo "size     : $size bytes"
echo "sha256   : $(sha256sum "$out" | cut -d' ' -f1)"
echo
echo 'markers:'
marker() {
    local n
    n=$(grep -ac -- "$2" "$out" 2>/dev/null || true)
    printf '  %-34s %s\n' "$1" "${n:-0}"
}
marker 'ufshcd lines' 'ufshcd'
marker 'scsi disk lines' 'sd [0-9]'
marker 'dwc3 lines' 'dwc3'
marker 'USB PHY lines' 'phy'
marker 'gts9-init lines' 'gts9-init:'
marker 'report written' 'report written to'
marker 'no medium accepted' 'no medium accepted'
marker 'Kernel panic' 'Kernel panic'
echo
echo "Read the tail of $out for the last thing the boot did."
