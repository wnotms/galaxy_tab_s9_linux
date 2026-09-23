#!/usr/bin/env bash
# Build the minimal BusyBox initramfs used for the first physical boot test.
#
# It assembles a self-contained userspace tree
#
#	/init            boot/bringup-init.sh, prints the GTS9 milestone
#	/bin/busybox     statically linked aarch64 BusyBox
#	/bin/* /sbin/*   applet symlinks
#	/proc /sys /dev /tmp /run
#
# and then hands the tree to scripts/make-initramfs.sh, which packs it as the
# legacy-LZ4 stream the boot chain expects and enforces the init_boot budget.
#
# The first boot test intentionally does NOT include kernel modules: every
# provider it needs (storage, console, pinctrl, PMIC, ...) is built in, and a
# 150 MiB module tree would only hide packaging mistakes.  Use --modules once
# a test actually needs loadable drivers.
#
# BusyBox is pinned: no "latest" is ever fetched, the download is verified
# against a pinned SHA-256, and a mismatch or an unreachable mirror fails
# closed.  A local binary may be supplied with --busybox instead, in which case
# it must still be a statically linked aarch64 ELF.
#
# Nothing here writes to a device.
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
workdir=${GTS9_WORKDIR:-$repo_root/.work}
out_dir=${BUNDLE_OUT_DIR:-$repo_root/out/boot-bundle}
tree=${BRINGUP_TREE:-$repo_root/out/bringup-initramfs}
out=${BRINGUP_INITRAMFS:-$out_dir/initramfs-bringup.img}
init_src="$repo_root/boot/bringup-init.sh"
download_dir=${BRINGUP_DOWNLOAD_DIR:-$workdir/downloads}

# Ubuntu 24.04 arm64 busybox-static (1.36.1-6ubuntu3.1).  Pinned by URL and by
# the SHA-256 of both the .deb and the extracted /bin/busybox inside it.
busybox_url=https://ports.ubuntu.com/ubuntu-ports/pool/main/b/busybox/busybox-static_1.36.1-6ubuntu3.1_arm64.deb
busybox_deb_sha256=d96535e0402c011e0ee43449799df2f4504d44b842e4f2b3a6cbc845508eaafc
busybox_bin_sha256=52151e7f322f926b64049cdaa1410dc3ea6485525e0624b05813791c219ae933

busybox_arg=
modules=
while [ $# -gt 0 ]; do
    case "$1" in
        --busybox) busybox_arg=$2; shift 2 ;;
        --tree) tree=$2; shift 2 ;;
        --out) out=$2; shift 2 ;;
        --modules) modules=$2; shift 2 ;;
        -h|--help)
            sed -n '2,25p' "$0"
            exit 0
            ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

# Applets the bring-up shell must have.  Anything missing here is a build
# failure, because the first boot test depends on it.
required_applets='sh mount umount cat echo dmesg uname ls mkdir ln cp mv chmod sync sleep reboot poweroff grep tail'
# Applets the report channel needs on top of that: it parses GPT headers off a
# raw disk, and then persists the report either through a filesystem or as a
# raw, checksummed block.  A missing applet would silently disable the only
# evidence channel this board has, so these are required as well.
report_applets='dd od awk sha256sum basename wc cut tr head printf date hwclock timeout'
# Convenience applets; missing ones are reported and skipped, not fatal.
optional_applets='lsmod insmod modprobe rmmod mdev switch_root head tail grep cut tr wc sort sed awk find printf test [ true false date uptime free ps kill sync hexdump od gunzip tar modinfo nproc clear vi less more halt'
# Applets that belong in /sbin rather than /bin.
sbin_applets='mount umount reboot poweroff halt switch_root insmod modprobe rmmod lsmod mdev modinfo'

fail() { echo "error: $*" >&2; exit 1; }

[ -f "$init_src" ] || fail "missing /init source: $init_src"
command -v readelf >/dev/null || fail 'readelf is required (apt install binutils)'
command -v strings >/dev/null || fail 'strings is required (apt install binutils)'
command -v sha256sum >/dev/null || fail 'sha256sum is required'

verify_busybox() {
    # verify_busybox <path> <expected-sha256|-> [<label>]
    local bin=$1 expected=$2 label=${3:-$1}

    [ -f "$bin" ] || fail "busybox not found: $bin"
    if [ "$expected" != - ]; then
        local actual
        actual=$(sha256sum "$bin" | cut -d' ' -f1)
        [ "$actual" = "$expected" ] || {
            fail "$label SHA-256 mismatch (expected $expected, got $actual)"
        }
    fi
    readelf -h "$bin" | grep -q 'Machine:.*AArch64' || \
        fail "$label is not an aarch64 ELF"
    if readelf -l "$bin" 2>/dev/null | grep -q 'INTERP'; then
        fail "$label is dynamically linked; a static BusyBox is required"
    fi
    # BusyBox keeps its applet names in a packed string table, so this is a
    # static presence check that works even though aarch64 cannot be executed
    # on the build host.
    strings -a -n 1 "$bin" > "$tmp/applets.txt"
    local applet
    for applet in $required_applets $report_applets; do
        grep -Fqx -- "$applet" "$tmp/applets.txt" || \
            fail "$label does not provide the required applet '$applet'"
    done
}

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

if [ -n "$busybox_arg" ]; then
    echo "using local busybox: $busybox_arg"
    verify_busybox "$busybox_arg" - "$busybox_arg"
    bb_bin=$busybox_arg
else
    deb=$download_dir/$(basename "$busybox_url")
    mkdir -p "$download_dir"
    if [ -f "$deb" ] && \
       [ "$(sha256sum "$deb" | cut -d' ' -f1)" = "$busybox_deb_sha256" ]; then
        echo "using cached $(basename "$deb")"
    else
        command -v curl >/dev/null || fail 'curl is required to download BusyBox'
        echo "downloading $(basename "$busybox_url")"
        curl -fsSL -o "$deb.tmp" "$busybox_url" || \
            fail "cannot download $busybox_url (failing closed)"
        actual=$(sha256sum "$deb.tmp" | cut -d' ' -f1)
        [ "$actual" = "$busybox_deb_sha256" ] || {
            rm -f "$deb.tmp"
            fail "downloaded BusyBox archive has SHA-256 $actual, expected $busybox_deb_sha256"
        }
        mv "$deb.tmp" "$deb"
    fi

    mkdir -p "$tmp/deb"
    if command -v dpkg-deb >/dev/null 2>&1; then
        dpkg-deb -x "$deb" "$tmp/deb"
    else
        command -v ar >/dev/null || fail 'need dpkg-deb or ar to unpack the BusyBox archive'
        member=$(ar t "$deb" | grep '^data\.tar' | head -1)
        [ -n "$member" ] || fail "no data.tar member in $deb"
        ar p "$deb" "$member" | tar -x -C "$tmp/deb"
    fi

    bb_bin=$(find "$tmp/deb" -type f -path '*/bin/busybox' | head -1)
    [ -n "$bb_bin" ] || fail "no */bin/busybox inside $deb"
    verify_busybox "$bb_bin" "$busybox_bin_sha256" "packaged busybox"
fi

echo "assembling initramfs tree: $tree"
rm -rf "$tree"
mkdir -p "$tree/bin" "$tree/sbin" "$tree/proc" "$tree/sys" "$tree/dev" \
         "$tree/tmp" "$tree/run" "$tree/etc"
chmod 1777 "$tree/tmp"
install -m 0755 "$bb_bin" "$tree/bin/busybox"
install -m 0755 "$init_src" "$tree/init"
install -m 0755 "$repo_root/boot/gts9-to-recovery.sh" "$tree/sbin/gts9-to-recovery"
# A freestanding aarch64 helper that clears the SIGINT/SIGQUIT dispositions a shell
# cannot clear itself (see boot/gts9-exec-default.c).  Without it the background
# panel shell inherits SIG_IGN and Ctrl-C does nothing.
if command -v clang >/dev/null 2>&1 && command -v ld.lld >/dev/null 2>&1; then
    if clang --target=aarch64-linux-gnu -nostdlib -static -ffreestanding \
             -fno-stack-protector -fno-builtin -fuse-ld=lld -Wl,--build-id=none -Wl,-n \
             -o "$tree/sbin/gts9-exec-default" "$repo_root/boot/gts9-exec-default.c" 2>/dev/null; then
        chmod 0755 "$tree/sbin/gts9-exec-default"
        echo "initramfs: installed gts9-exec-default ($(stat -c %s "$tree/sbin/gts9-exec-default") bytes)"
    else
        echo "initramfs: WARNING could not build gts9-exec-default; the panel shell falls back" >&2
    fi
else
    echo "initramfs: WARNING clang/ld.lld missing; the panel shell falls back" >&2
fi

link_applet() {
    # link_applet <applet>
    local applet=$1 dir=bin target=busybox
    case " $sbin_applets " in
        *" $applet "*) dir=sbin; target=../bin/busybox ;;
    esac
    ln -sf "$target" "$tree/$dir/$applet"
}

missing_optional=
for applet in $required_applets $report_applets $optional_applets; do
    if grep -Fqx -- "$applet" "$tmp/applets.txt"; then
        link_applet "$applet"
    else
        missing_optional="$missing_optional $applet"
    fi
done
if [ -n "$missing_optional" ]; then
    echo "note: this BusyBox build does not provide:$missing_optional"
fi

# Reboot helper: busybox can only ask for a plain restart, and the bootloader
# mode is chosen by the *string* passed to reboot(2) RESTART2.  Compiled here
# for the target, freestanding (no libc), one binary per mode.
reboot_helper_src="$repo_root/boot/gts9-reboot-mode.c"
command -v clang >/dev/null || fail 'clang is required to build the reboot helper'
for mode in recovery; do
    out_bin="$tree/bin/gts9-reboot-$mode"
    clang --target=aarch64-linux-gnu -nostdlib -static -O2 -fuse-ld=lld \
          -DGTS9_REBOOT_MODE="\"$mode\"" -o "$out_bin" "$reboot_helper_src" || \
        fail "cannot build the $mode reboot helper"
    readelf -h "$out_bin" | grep -q 'Machine:.*AArch64' || \
        fail "the $mode reboot helper is not an aarch64 ELF"
    if readelf -l "$out_bin" 2>/dev/null | grep -q INTERP; then
        fail "the $mode reboot helper is dynamically linked"
    fi
    echo "built reboot helper: $out_bin ($(stat -c %s "$out_bin") bytes)"
done

# The pogo keyboard's firmware, when it is available.  The STM32 application is
# only reached by the vendor driver's firmware path, which returns early when
# request_firmware() fails, so a test that wants that path has to carry the file
# the stock ramdisk carries.  It is Samsung's proprietary blob and deliberately
# not tracked in this repository: copy it from the TWRP device tree, e.g.
#   recovery/root/vendor/firmware_mnt/image/keyboard_stm/stm32_gts9family.bin
# into .work/firmware/keyboard_stm/ and it is picked up here.
fw_src="$repo_root/.work/firmware"
if [ -d "$fw_src" ] && [ -n "$(find "$fw_src" -type f 2>/dev/null | head -1)" ]; then
    mkdir -p "$tree/lib/firmware"
    cp -a "$fw_src"/. "$tree/lib/firmware/"
    echo "including firmware from $fw_src:"
    find "$tree/lib/firmware" -type f -printf '  %p (%s bytes)\n'
else
    echo "no firmware under $fw_src; the vendor driver's firmware path will abort"
fi

if [ -n "$modules" ]; then
    echo "including modules from $modules"
    exec_args=(--modules "$modules")
else
    exec_args=()
fi

"$repo_root/scripts/make-initramfs.sh" --root "$tree" --out "$out" "${exec_args[@]}"

cat <<EOF

Bring-up initramfs ready: $out
tree kept for inspection : $tree

Package and check a bundle with:
  ./scripts/build-boot-bundle.sh --initramfs $out \\
    --cmdline boot/cmdline.example.txt --bootconfig boot/bootconfig.example.txt
  ./scripts/validate-boot-bundle.sh

Nothing was flashed and no device was touched.
EOF
