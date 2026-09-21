#!/usr/bin/env bash
# Assemble Samsung Android boot header v4 images. This script NEVER flashes.
#
# APPEND_DTB=1 (default) concatenates Image.gz with the board DTB inside
# boot.img, the layout the SM-X910 port validates. APPEND_DTB=0 keeps boot.img
# payload pure Image.gz and lets the bootloader use the DTB it already selects
# out of vendor_boot. Boot test 3 showed the kernel never reaching
# setup_arch(), and the appended DTB starts at an offset equal to the Image.gz
# size (21,805,353 bytes, not 8-byte aligned) - arm64 rejects a misaligned FDT
# pointer outright. APPEND_DTB=0 removes that variable; it is also what the
# stock SM-X710 boot.img does (raw kernel, no appended DTB).
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
kernel_out=${KERNEL_OUT_DIR:-$repo_root/out/kernel-gts9wifi}
out=${BUNDLE_OUT_DIR:-$repo_root/out/boot-bundle}
mkbootimg=${MKBOOTIMG:-}
avbtool=${AVBTOOL:-}
append_dtb=${APPEND_DTB:-1}

case "$append_dtb" in 0|1) ;; *) echo "APPEND_DTB must be 0 or 1" >&2; exit 2 ;; esac

boot_size=100663296
init_boot_size=8388608
vendor_boot_size=100663296
dtbo_size=16777216
vbmeta_size=131072

initramfs=
cmdline_file=
bootconfig_file=
while [ $# -gt 0 ]; do
    case "$1" in
        --initramfs) initramfs=$2; shift 2 ;;
        --cmdline) cmdline_file=$2; shift 2 ;;
        --bootconfig) bootconfig_file=$2; shift 2 ;;
        --out) out=$2; shift 2 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

: "${initramfs:?--initramfs is required}"
: "${cmdline_file:?--cmdline is required}"
: "${bootconfig_file:?--bootconfig is required}"
: "${mkbootimg:?set MKBOOTIMG=/path/to/mkbootimg.py}"
: "${avbtool:?set AVBTOOL=/path/to/avbtool.py}"

image="$kernel_out/Image.gz"
dtb="$kernel_out/sm8550-samsung-gts9wifi.dtb"
for f in "$image" "$dtb" "$initramfs" "$cmdline_file" "$bootconfig_file" "$mkbootimg" "$avbtool"; do
    [ -f "$f" ] || { echo "missing input: $f" >&2; exit 1; }
done
command -v lz4 >/dev/null || { echo 'lz4 is required' >&2; exit 1; }
command -v cpio >/dev/null || { echo 'cpio is required' >&2; exit 1; }

mkdir -p "$out"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

add_footer() {
    local file=$1 name=$2 size=$3 salt
    salt=$(sha256sum "$file" | cut -d' ' -f1)
    python3 "$avbtool" add_hash_footer --image "$file" \
        --partition_name "$name" --partition_size "$size" --salt "$salt"
}

if [ "$append_dtb" = 1 ]; then
    cat "$image" "$dtb" > "$tmp/boot-kernel"
    echo "boot.img payload: Image.gz + appended board DTB"
else
    cp "$image" "$tmp/boot-kernel"
    echo "boot.img payload: Image.gz only (DTB comes from vendor_boot)"
fi
echo "  payload size: $(stat -c %s "$tmp/boot-kernel") bytes"

mkdir -p "$tmp/empty"
touch -d '@0' "$tmp/empty"
(
    cd "$tmp/empty"
    find . -print0 | LC_ALL=C sort -z | cpio --reproducible --null -o --format=newc 2>/dev/null
) | lz4 -l -12 - "$tmp/empty.lz4" >/dev/null

case $(head -c4 "$initramfs" | od -An -tx1 | tr -d ' \n') in
    1f8b*) gzip -dc "$initramfs" | lz4 -l -12 - "$tmp/initramfs.lz4" >/dev/null ;;
    02214c18) cp "$initramfs" "$tmp/initramfs.lz4" ;;
    *) echo 'initramfs must be gzip or legacy LZ4' >&2; exit 1 ;;
esac

cmdline=$(tr '\n' ' ' < "$cmdline_file" | sed 's/[[:space:]]*$//')

python3 "$mkbootimg" --kernel "$tmp/boot-kernel" --cmdline '' \
    --header_version 4 --os_version 13 --os_patch_level 2025-07 \
    -o "$out/boot.img"
add_footer "$out/boot.img" boot "$boot_size"

python3 "$mkbootimg" --ramdisk "$tmp/empty.lz4" --header_version 4 \
    -o "$out/init_boot.img"
add_footer "$out/init_boot.img" init_boot "$init_boot_size"

python3 "$mkbootimg" \
    --ramdisk_type platform --ramdisk_name '' \
    --vendor_ramdisk_fragment "$tmp/initramfs.lz4" \
    --dtb "$dtb" --vendor_cmdline "$cmdline" --header_version 4 \
    --vendor_boot "$out/vendor_boot.img" \
    --base 0x80000000 --kernel_offset 0x8000 \
    --ramdisk_offset 0x02000000 --tags_offset 0x01e00000 \
    --pagesize 4096 --dtb_offset 0x1f00000 \
    --vendor_bootconfig "$bootconfig_file"
add_footer "$out/vendor_boot.img" vendor_boot "$vendor_boot_size"

truncate -s 4096 "$out/dtbo.img"
add_footer "$out/dtbo.img" dtbo "$dtbo_size"

python3 "$avbtool" make_vbmeta_image --output "$out/vbmeta.img" \
    --flags 2 --padding_size "$vbmeta_size"

for spec in \
    "boot.img:$boot_size" "init_boot.img:$init_boot_size" \
    "vendor_boot.img:$vendor_boot_size" "dtbo.img:$dtbo_size" \
    "vbmeta.img:$vbmeta_size"; do
    name=${spec%%:*}; expected=${spec##*:}
    actual=$(stat -c %s "$out/$name")
    [ "$actual" -eq "$expected" ] || {
        echo "$name size mismatch: expected $expected, got $actual" >&2
        exit 1
    }
done

(
    cd "$out"
    sha256sum *.img > SHA256SUMS
)

# Machine-readable record of how the images were built, so the validator can
# check the layout that was actually requested instead of assuming one.
{
    printf 'append_dtb=%s\n' "$append_dtb"
    printf 'boot_payload=%s\n' "$( [ "$append_dtb" = 1 ] && echo 'image.gz+dtb' || echo 'image.gz' )"
    printf 'image_gz_sha256=%s\n' "$(sha256sum "$image" | cut -d' ' -f1)"
    printf 'dtb_sha256=%s\n' "$(sha256sum "$dtb" | cut -d' ' -f1)"
    printf 'initramfs_sha256=%s\n' "$(sha256sum "$initramfs" | cut -d' ' -f1)"
    printf 'kernel_release=%s\n' "$(cat "$kernel_out/kernel.release" 2>/dev/null || echo unknown)"
} > "$out/BUNDLE_INFO"
cat "$out/BUNDLE_INFO"

cat "$out/SHA256SUMS"
echo "bundle assembled only; nothing was flashed"
