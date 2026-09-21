#!/bin/sh
# Read-only audit of the SM-X710 boot-chain partition sizes.
#
# Run this ON THE TABLET (TWRP/recovery, or any root shell) before flashing
# anything:
#
#	sh check-device-layout.sh | tee /external_sd/gts9-layout.txt
#
# It resolves every boot-chain partition and reports its exact size, then says
# whether those sizes match what scripts/build-boot-bundle.sh pads its images
# to.  The sizes in this repository were taken from the sibling SM-X910 port;
# they are an assumption about the X710 until this script confirms them on the
# real device.
#
# This script only reads.  It opens no block device for writing, runs no
# flash tool, and refuses to run if such a command ever appears in it.
#
# On a build host it can be exercised against a synthetic tree:
#	sh check-device-layout.sh --root /tmp/fake-device

root=
while [ $# -gt 0 ]; do
    case "$1" in
        --root) root=$2; shift 2 ;;
        -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

# Safety self-check, same idea as scripts/validate-boot-bundle.sh.
for forbidden in dd fastboot heimdall odin adb; do
    if grep -qE "(^|[;&|(]|\\\$\()[[:space:]]*${forbidden}([[:space:]]|\\\$)" "$0" 2>/dev/null; then
        echo "refusing to run: $0 references the command '$forbidden'" >&2
        exit 1
    fi
done

partitions='boot init_boot vendor_boot dtbo vbmeta'

expected_size() {
    case "$1" in
        boot) echo 100663296 ;;
        init_boot) echo 8388608 ;;
        vendor_boot) echo 100663296 ;;
        dtbo) echo 16777216 ;;
        vbmeta) echo 131072 ;;
        *) echo 0 ;;
    esac
}

by_name_dir="$root/dev/block/by-name"

size_of() {
    # size_of <path> -> bytes on stdout, non-zero if unknown
    dev=$1
    if [ -b "$dev" ]; then
        if command -v blockdev >/dev/null 2>&1; then
            blockdev --getsize64 "$dev" && return 0
        fi
        real=$(readlink -f "$dev" 2>/dev/null)
        name=$(basename "${real:-$dev}")
        if [ -r "/sys/class/block/$name/size" ]; then
            sectors=$(cat "/sys/class/block/$name/size" 2>/dev/null)
            case "$sectors" in
                ''|*[!0-9]*) return 1 ;;
            esac
            echo $((sectors * 512))
            return 0
        fi
        return 1
    fi
    # Host dry run against a synthetic tree of regular files.
    if [ -f "$dev" ]; then
        if size=$(stat -c %s "$dev" 2>/dev/null); then
            echo "$size"
        else
            wc -c < "$dev" | tr -d ' '
        fi
        return 0
    fi
    return 1
}

[ -d "$by_name_dir" ] || {
    echo "cannot find $by_name_dir" >&2
    echo 'run this on the tablet (TWRP/recovery) or pass --root for a dry run' >&2
    exit 2
}

echo '=== SM-X710 boot-chain partition layout (read-only) ==='
if [ -n "$root" ]; then
    echo "root: $root (dry run against regular files)"
fi
if command -v getprop >/dev/null 2>&1; then
    for prop in ro.product.device ro.build.display.id ro.build.fingerprint; do
        value=$(getprop "$prop" 2>/dev/null)
        [ -n "$value" ] && echo "$prop: $value"
    done
fi
echo

mismatch=0
missing=0
for part in $partitions; do
    link=$by_name_dir/$part
    want=$(expected_size "$part")
    printf '===== %s =====\n' "$part"
    if [ ! -e "$link" ]; then
        echo "  MISSING: $link does not exist"
        missing=$((missing + 1))
        echo
        continue
    fi
    echo "  path    : $(readlink -f "$link" 2>/dev/null || echo "$link")"
    size=$(size_of "$link")
    if [ -z "$size" ]; then
        echo '  size    : UNKNOWN (no blockdev and no sysfs size)'
        missing=$((missing + 1))
        echo
        continue
    fi
    echo "  size    : $size bytes"
    echo "  expected: $want bytes (repository bundle padding)"
    if [ "$size" -eq "$want" ]; then
        echo '  status  : MATCH'
    else
        echo '  status  : MISMATCH'
        mismatch=$((mismatch + 1))
    fi
    echo
done

echo '=== summary ==='
echo "partitions checked : $(echo $partitions | wc -w)"
echo "size mismatches    : $mismatch"
echo "missing/unreadable : $missing"
echo

if [ "$missing" -gt 0 ]; then
    echo 'DO NOT FLASH: the layout could not be read completely.'
    echo 'Capture the output above and compare it with the bundle first.'
    exit 1
fi
if [ "$mismatch" -gt 0 ]; then
    echo 'DO NOT FLASH: at least one partition size differs from the bundle padding.'
    echo 'Update scripts/build-boot-bundle.sh (and the validator) to the real sizes'
    echo 'before writing anything.'
    exit 1
fi

echo 'Layout matches the repository bundle padding.'
echo 'This is a prerequisite, not permission: follow docs/FIRST_BOOT_TEST.md,'
echo 'back up the stock boot chain first, and keep the recovery path ready.'
