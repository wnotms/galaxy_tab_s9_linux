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
minimal_init_src="$repo_root/boot/minimal-rootfs-init.sh"
minimal_state_src="$repo_root/boot/minimal-rootfs-state.sh"
minimal_pid1_src="$repo_root/boot/gts9-minimal-pid1.c"
download_dir=${BRINGUP_DOWNLOAD_DIR:-$workdir/downloads}

# The shared library owns the pinned BusyBox, the static-ELF checks, the applet
# symlink logic and the manifest writer, so this debug builder and the production
# one cannot drift apart in how they are built.
# shellcheck source=lib/initramfs-common.sh
. "$repo_root/scripts/lib/initramfs-common.sh"

# Applets the bring-up shell must have.  Anything missing here is a build
# failure, because this image's whole purpose is the diagnostic shell and report.
#
# This list is the DEBUG image's, and it is deliberately much longer than the
# production one in scripts/build-minimal-initramfs.sh: everything here exists for
# a bring-up capability (raw block reads, GPT parsing, checksummed reports, RTC
# telemetry, module handling) that the production handoff must not be able to
# reach.  Keep the two lists separate; sharing one would drag the debug set back
# into production.
required_applets='sh mount umount switch_root cat echo dmesg uname ls mkdir ln cp mv rm chmod sync sleep reboot poweroff grep tail'
# Applets the report channel needs on top of that: it parses GPT headers off a
# raw disk, and then persists the report either through a filesystem or as a
# raw, checksummed block.  A missing applet would silently disable the only
# evidence channel a boot without network has, so these are required as well.
report_applets='dd od awk sha256sum basename wc cut tr head printf date hwclock timeout'
# Convenience applets; missing ones are reported and skipped, not fatal.
optional_applets='lsmod insmod modprobe rmmod mdev switch_root head tail grep cut tr wc sort sed awk find printf test [ true false date uptime free ps kill sync hexdump od gunzip tar modinfo nproc clear vi less more halt'
# Applets that belong in /sbin rather than /bin.
sbin_applets='mount umount reboot poweroff halt switch_root insmod modprobe rmmod lsmod mdev modinfo'

busybox_arg=
modules=
keyboard_firmware=
while [ $# -gt 0 ]; do
    case "$1" in
        --busybox) busybox_arg=$2; shift 2 ;;
        --tree) tree=$2; shift 2 ;;
        --out) out=$2; shift 2 ;;
        --modules) modules=$2; shift 2 ;;
        --keyboard-firmware) keyboard_firmware=$2; shift 2 ;;
        -h|--help)
            sed -n '2,30p' "$0"
            exit 0
            ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
bb_bin=
gts9_obtain_busybox "${busybox_arg:-}"
gts9_busybox_applets "$bb_bin" "$tmp/applets.txt"
gts9_require_applets "$tmp/applets.txt" "$required_applets $report_applets" "the pinned BusyBox"

echo "assembling initramfs tree: $tree"
rm -rf "$tree"
mkdir -p "$tree/bin" "$tree/sbin" "$tree/proc" "$tree/sys" "$tree/dev" \
         "$tree/tmp" "$tree/run" "$tree/etc"
chmod 1777 "$tree/tmp"
install -m 0755 "$bb_bin" "$tree/bin/busybox"
install -m 0755 "$init_src" "$tree/init"
install -m 0755 "$minimal_init_src" "$tree/minimal-rootfs-init"
# Sourced by /minimal-rootfs-init: it owns the persistent stage record written
# to the Debian root filesystem.  It is deliberately a separate file so host
# tests can exercise the record format without an initramfs.
install -m 0644 "$minimal_state_src" "$tree/minimal-rootfs-state.sh"
install -m 0755 "$repo_root/boot/gts9-to-recovery.sh" "$tree/sbin/gts9-to-recovery"

# This trampoline is the new init only for the minimal rootfs profile. It
# execs Debian's /sbin/init and can still report a failed exec while keeping
# PID 1 alive in a BusyBox rescue shell.
minimal_pid1="$tree/sbin/gts9-minimal-pid1"
clang --target=aarch64-linux-gnu -nostdlib -static -ffreestanding \
      -fno-stack-protector -fno-builtin -fuse-ld=lld \
      -Wl,--build-id=none -Wl,-n \
      -o "$minimal_pid1" "$minimal_pid1_src" || \
    fail 'cannot build the minimal rootfs PID 1 helper'
readelf -h "$minimal_pid1" | grep -q 'Machine:.*AArch64' || \
    fail 'the minimal rootfs PID 1 helper is not an aarch64 ELF'
if readelf -l "$minimal_pid1" 2>/dev/null | grep -q INTERP; then
    fail 'the minimal rootfs PID 1 helper is dynamically linked'
fi
chmod 0755 "$minimal_pid1"
echo "built minimal rootfs PID 1 helper: $minimal_pid1 ($(stat -c %s "$minimal_pid1") bytes)"

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

missing_optional=$(gts9_link_applets "$tree" \
    "$required_applets $report_applets $optional_applets" "$sbin_applets")
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

# The pogo keyboard's firmware, when it is explicitly pointed at.
#
# This used to be `cp -a .work/firmware/.` - an arbitrary directory copied whole
# into init_boot.  That is the biggest footgun the old builder had: .work/firmware
# is where the bring-up work stages whatever blob a test needed, so on a host that
# had ever staged Wi-Fi or GPU firmware, every subsequent debug image silently
# carried it into init_boot.  Wi-Fi works from the Debian root now
# (/usr/lib/firmware/ath11k/WCN6855/...), and none of that belongs in an
# initramfs.
#
# It is now an allowlist of exactly one blob, named explicitly, with its
# destination path fixed rather than mirrored.  To include it:
#
#   ./scripts/build-bringup-initramfs.sh \
#       --keyboard-firmware .work/firmware/keyboard_stm/stm32_gts9family.bin
#
# The STM32 application is only reached by the vendor driver's firmware path,
# which returns early when request_firmware() fails, so a test that wants that
# path has to carry the file the stock ramdisk carries.  It is Samsung's
# proprietary blob and deliberately not tracked in this repository; copy it from
# the TWRP device tree, e.g.
#   recovery/root/vendor/firmware_mnt/image/keyboard_stm/stm32_gts9family.bin
firmware_allowlist_dest=keyboard_stm/stm32_gts9family.bin
if [ -n "$keyboard_firmware" ]; then
    [ -f "$keyboard_firmware" ] || \
        fail "--keyboard-firmware does not exist: $keyboard_firmware"
    mkdir -p "$tree/lib/firmware/$(dirname "$firmware_allowlist_dest")"
    install -m 0644 "$keyboard_firmware" "$tree/lib/firmware/$firmware_allowlist_dest"
    echo "included the allowlisted pogo firmware blob:"
    find "$tree/lib/firmware" -type f -printf '  %p (%s bytes)\n'
else
    echo "no firmware staged (use --keyboard-firmware PATH for the pogo blob);"
    echo "firmware for Wi-Fi, GPU and the rest lives on the Debian rootfs"
fi

if [ -n "$modules" ]; then
    echo "including modules from $modules"
    exec_args=(--modules "$modules")
else
    exec_args=()
fi

"$repo_root/scripts/make-initramfs.sh" --root "$tree" --out "$out" "${exec_args[@]}"

# Same manifest key set as the production builder, so the two images can be
# compared mechanically rather than by inferring a profile from a filename.
gts9_write_manifest "$out" bringup "$tree" "$bb_bin" "${modules:-}" "${keyboard_firmware:-}"

cat <<EOF

Bring-up initramfs ready: $out
tree kept for inspection : $tree

Package and check a bundle with:
  ./scripts/build-boot-bundle.sh --initramfs $out \\
    --cmdline boot/cmdline.example.txt --bootconfig boot/bootconfig.example.txt
  ./scripts/validate-boot-bundle.sh

Nothing was flashed and no device was touched.
EOF
