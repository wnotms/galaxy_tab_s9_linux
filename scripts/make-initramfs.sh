#!/usr/bin/env bash
# Assemble the initramfs that scripts/build-boot-bundle.sh packages into
# vendor_boot, and check that it is a stream Samsung's ABL and Linux accept.
#
# The bundle script deliberately puts an empty generic ramdisk in init_boot and
# the real initramfs into vendor_boot as a platform fragment (the appended-DTB
# fallback route documented in docs/MAINLINE_PORT_PLAN.md).  That means the
# budget this script enforces is the vendor_boot partition, not init_boot.
#
# Two inputs are needed:
#   --root DIR       an initramfs tree that contains /init (a distro initramfs
#                    tree, a postmarketOS initramfs, or a hand-built busybox
#                    tree).  Nothing is generated for you: this script packs
#                    and verifies, it does not invent userspace.
#   --modules DIR    optional modules-root produced by scripts/build-kernel.sh
#                    (out/kernel-gts9wifi/modules-root); its lib/modules/<release>
#                    tree is copied in and depmod'ed.
#
# It writes only into --out (and a temporary directory).  Nothing is flashed.
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
kernel_out=${KERNEL_OUT_DIR:-$repo_root/out/kernel-gts9wifi}
out_dir=${BUNDLE_INITRAMFS_DIR:-$repo_root/out/boot-bundle}

root=
modules=
release=
out=
# vendor_boot is 100663296 bytes; keep 8 MiB of headroom for the boot header,
# the DTB, the cmdline and the bootconfig.
max_size=92274688

while [ $# -gt 0 ]; do
    case "$1" in
        --root) root=$2; shift 2 ;;
        --modules) modules=$2; shift 2 ;;
        --release) release=$2; shift 2 ;;
        --out) out=$2; shift 2 ;;
        --max-size) max_size=$2; shift 2 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

: "${root:?--root is required (an initramfs tree containing /init)}"
[ -d "$root" ] || { echo "missing initramfs root: $root" >&2; exit 1; }
[ -e "$root/init" ] || {
    echo "initramfs root has no /init: $root" >&2
    echo 'the kernel needs an executable /init in the root of the archive' >&2
    exit 1
}

if [ -z "$release" ] && [ -f "$kernel_out/kernel.release" ]; then
    release=$(cat "$kernel_out/kernel.release")
fi
: "${release:?--release is required when $KERNEL_OUT_DIR/kernel.release is absent}"

if [ -n "$modules" ]; then
    [ -d "$modules" ] || { echo "missing modules root: $modules" >&2; exit 1; }
    [ -d "$modules/lib/modules/$release" ] || {
        echo "modules root has no lib/modules/$release: $modules" >&2
        echo "build with BUILD_MODULES=1 and the same kernel release" >&2
        exit 1
    }
fi

out=${out:-$out_dir/initramfs-$release.img}
command -v cpio >/dev/null || { echo 'cpio is required' >&2; exit 1; }
command -v lz4 >/dev/null || {
    echo 'lz4 is required (apt install lz4)' >&2
    echo 'Samsung ABL and the kernel expect the legacy LZ4 stream format' >&2
    exit 1
}

mkdir -p "$(dirname "$out")"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
stage=$tmp/root
mkdir -p "$stage"

echo "staging $root" >&2
cp -a "$root/." "$stage/"

if [ -n "$modules" ]; then
    echo "adding modules for $release" >&2
    mkdir -p "$stage/lib/modules"
    cp -a "$modules/lib/modules/$release" "$stage/lib/modules/"
    if command -v depmod >/dev/null 2>&1; then
        # depmod reads the module ELF headers, so a host depmod handles a
        # foreign architecture correctly.
        depmod -b "$stage" "$release"
    else
        echo 'warning: depmod not found, module dependencies are not resolved' >&2
    fi
fi

# cpio --reproducible normalises device and inode numbers but not mtimes, so
# without this the archive changes hash on every run.
find "$stage" -exec touch -h -d '@0' {} +

echo "packing $out" >&2
(
    cd "$stage"
    find . -print0 | LC_ALL=C sort -z \
        | cpio --reproducible --null -o --format=newc 2>/dev/null
) | lz4 -q -f -l -12 - "$out" >/dev/null

magic=$(head -c4 "$out" | od -An -tx1 | tr -d ' \n')
if [ "$magic" != 02214c18 ]; then
    echo "initramfs is not legacy LZ4 (magic $magic)" >&2
    exit 1
fi

size=$(stat -c %s "$out")
if [ "$size" -gt "$max_size" ]; then
    echo "initramfs is $size bytes, budget is $max_size" >&2
    echo 'trim the tree or move modules to the root filesystem' >&2
    exit 1
fi

printf 'initramfs: %s\n' "$out"
printf 'release  : %s\n' "$release"
printf 'size     : %s bytes (budget %s)\n' "$size" "$max_size"
printf 'sha256   : %s\n' "$(sha256sum "$out" | cut -d' ' -f1)"
