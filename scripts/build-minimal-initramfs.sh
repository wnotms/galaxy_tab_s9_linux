#!/usr/bin/env bash
# Build the PRODUCTION initramfs: hand PID 1 to the Debian root on the microSD.
#
# This image exists to do one thing, and it is the only thing its /init can do:
#
#	mount /proc, /sys, /dev, /run
#	read gts9_rootfs= from the command line
#	wait for that block device
#	mount it as ext4
#	check /newroot/sbin/init exists and is executable
#	record the stage history on the Debian root
#	move /dev /proc /sys /run into it
#	exec switch_root
#
# and, when any of that fails, drop to a rescue shell on tty1.  Nothing else.
#
# What is deliberately NOT here, and why
# --------------------------------------
# Everything the bring-up initramfs accumulated over 200+ physical tests moved to
# either scripts/build-bringup-initramfs.sh (the debug image) or to the Debian
# root filesystem, which now owns it:
#
#   USB gadget (NCM/MSC/ACM)  Debian's gts9-usb-acm creates ncm.usb0 after
#                             switch_root.  Creating a gadget here and having
#                             Debian tear it down and rebuild it costs a UDC
#                             bind/unbind and a USB re-enumeration on every boot,
#                             and the serial functions no longer exist in the
#                             kernel at all.
#   display recovery, RTC,    debug capabilities, kept in the bring-up image.
#   GPT/BCB, hardware report,
#   UFS/mmc diagnostics
#   kernel modules            live on the rootfs in /usr/lib/modules/<release>.
#   firmware                  lives on the rootfs in /usr/lib/firmware.  Wi-Fi
#                             works from there now; staging it into init_boot was
#                             the single biggest footgun in the old builder.
#   panel shell helper        (gts9-exec-default) is dead code - nothing has
#                             invoked it since the panel shell switched to `set -m`.
#   the minimal-rootfs branch bringup-init.sh branched on gts9_minimal_rootfs=1
#                             and exec'd the handoff.  This image IS the handoff,
#                             so there is no branch to take.
#
# BusyBox is pinned and verified exactly as the debug image does it, via
# scripts/lib/initramfs-common.sh, so the two cannot drift.
#
# Nothing here writes to a device.
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
workdir=${GTS9_WORKDIR:-$repo_root/.work}
out_dir=${BUNDLE_OUT_DIR:-$repo_root/out/boot-bundle}
tree=${MINIMAL_TREE:-$repo_root/out/minimal-initramfs}
out=${MINIMAL_INITRAMFS:-$out_dir/initramfs-minimal.img}
init_src="$repo_root/boot/minimal-rootfs-init.sh"
state_src="$repo_root/boot/minimal-rootfs-state.sh"
download_dir=${GTS9_DOWNLOAD_DIR:-$workdir/downloads}
with_trampoline=${MINIMAL_WITH_TRAMPOLINE:-0}

# shellcheck source=lib/initramfs-common.sh
. "$repo_root/scripts/lib/initramfs-common.sh"

fail() { echo "error: $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Applets, derived from what boot/minimal-rootfs-init.sh and
# boot/minimal-rootfs-state.sh actually invoke - not copied from the debug list.
#
# The scan that produced this list is in
# reference/initramfs-audit/2026-09-26-production-applets.txt.  Every entry is a
# command the production pair uses in command position:
#
#   mount umount   pseudo filesystems and the root
#   switch_root    the handoff itself
#   cat            /proc/cmdline, /proc/mounts, /proc/uptime, /proc/sys/...
#   cut date uname /proc/uptime, the record timestamp, the kernel release
#   mkdir rm mv    /proc /sys /dev /run, and the record's atomic replace
#   chmod          the record's mode
#   printf echo    the record and the console messages
#   ls             /sys/class/block diagnostics in the rescue shell
#   sleep          the bounded root-device wait and the rescue loop's backoff
#   sync           the record's durability flushes
#   grep           "is it already mounted", and the stage-history dedup
#   timeout        the bounded trampoline selftest (opt-in path only)
#   sh             the rescue shell and the handoff exec
#   test [         every condition in both scripts
#   reboot poweroff  THE RESCUE ESCAPE HATCH
#
# reboot and poweroff are a fix found by running the failure test on the device
# rather than by reading this script.  With gts9_rootfs=/dev/does-not-exist the
# handoff correctly stopped in the rescue shell - and then nothing inside it could
# leave: this image has no network (no gadget, no Wi-Fi), there is no serial port,
# and there was no `reboot` applet, so recovering the tablet required a physical
# key combination that the owner could not perform.  A rescue shell that cannot be
# left is a trap, not a rescue.
#
# The BCB recovery path then needs five more, and each is there because the
# bootloader-control-block write cannot be done without it:
#
#   head tr        read back the first bytes of misc to see whether it already
#                  asks for recovery, and whether the write landed
#   dd             write the 13-byte command into misc at offset 0
#   sed            extract PARTNAME= from the partition's sysfs uevent, which is
#                  how the misc partition is identified
#   basename       turn /sys/class/block/sda10 into sda10 and then /dev/sda10
#
# They are small and they are the whole safety story: identifying the partition by
# the kernel's own GPT label is what keeps this from writing a BCB into somebody
# else's partition.  `od` is deliberately still absent - the debug image uses it
# for raw GPT parsing, and this path needs no GPT parser because the kernel has
# already parsed one.
#
# Everything else on the debug list stays out, because those are the capabilities
# that made the old image risky: no od (raw GPT work), no dmesg, no hwclock or
# date-driven RTC state, no awk for report formatting, no sha256sum, no find, no
# setsid/chvt.
required_applets='sh mount umount switch_root cat echo mkdir cp chmod sync sleep grep ls mv rm timeout cut date uname printf head test [ reboot poweroff dd tr sed basename'
# Applets that belong in /sbin rather than /bin.
sbin_applets='mount umount switch_root reboot poweroff'

while [ $# -gt 0 ]; do
    case "$1" in
        --busybox) bb_arg=$2; shift 2 ;;
        --tree) tree=$2; shift 2 ;;
        --out) out=$2; shift 2 ;;
        --with-trampoline) with_trampoline=1; shift ;;
        --modules) fail 'the production initramfs does not take --modules: kernel modules live on the Debian root in /usr/lib/modules/<release>. Use scripts/build-bringup-initramfs.sh --modules for a debug image.' ;;
        -h|--help)
            sed -n '2,45p' "$0"
            exit 0
            ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

case "$with_trampoline" in 0|1) ;; *) fail 'MINIMAL_WITH_TRAMPOLINE must be 0 or 1' ;; esac

[ -f "$init_src" ] || fail "missing handoff init source: $init_src"
[ -f "$state_src" ] || fail "missing state library: $state_src"
command -v readelf >/dev/null || fail 'readelf is required (apt install binutils)'
command -v strings >/dev/null || fail 'strings is required (apt install binutils)'
command -v sha256sum >/dev/null || fail 'sha256sum is required'

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

bb_bin=
gts9_obtain_busybox "${bb_arg:-}"
gts9_busybox_applets "$bb_bin" "$tmp/applets.txt"
gts9_require_applets "$tmp/applets.txt" "$required_applets" "the pinned BusyBox"

echo "assembling production initramfs tree: $tree"
rm -rf "$tree"
mkdir -p "$tree/bin" "$tree/sbin" "$tree/proc" "$tree/sys" "$tree/dev" \
         "$tree/tmp" "$tree/run" "$tree/etc"
chmod 1777 "$tree/tmp"
install -m 0755 "$bb_bin" "$tree/bin/busybox"

# /init IS the handoff.  There is no trampoline script, no branch on a command
# line token, and no second stage: the old path was
#     /init -> bringup-init.sh -> inspect gts9_minimal_rootfs -> exec handoff
# and the production image has no use for the middle two steps.
install -m 0755 "$init_src" "$tree/init"
# Sourced by /init.  A separate file so host tests can exercise the record format
# without an initramfs.
install -m 0644 "$state_src" "$tree/minimal-rootfs-state.sh"

missing=$(gts9_link_applets "$tree" "$required_applets" "$sbin_applets")
if [ -n "$missing" ]; then
    fail "the pinned BusyBox is missing applets the handoff needs:$missing"
fi

# ---------------------------------------------------------------------------
# The trampoline is opt-in, and the default image does not contain it at all.
#
# It is a post-switch_root watchdog, and test 178 boot #3 showed it can hang the
# tablet hard enough that no key combination reaches TWRP, so the direct
# /sbin/init path is the proven one.  Requiring an explicit --with-trampoline to
# ship it means a normal image cannot be talked into using it by a command-line
# token, and the handoff script skips all staging when it is absent.
# ---------------------------------------------------------------------------
if [ "$with_trampoline" = 1 ]; then
    tramp_src="$repo_root/boot/gts9-minimal-pid1.c"
    [ -f "$tramp_src" ] || fail "missing trampoline source: $tramp_src"
    command -v clang >/dev/null || fail 'clang is required for --with-trampoline'
    tramp="$tree/sbin/gts9-minimal-pid1"
    clang --target=aarch64-linux-gnu -nostdlib -static -ffreestanding \
          -fno-stack-protector -fno-builtin -fuse-ld=lld \
          -Wl,--build-id=none -Wl,-n \
          -o "$tramp" "$tramp_src" || fail 'cannot build the trampoline'
    readelf -h "$tramp" | grep -q 'Machine:.*AArch64' || \
        fail 'the trampoline is not an aarch64 ELF'
    if readelf -l "$tramp" 2>/dev/null | grep -q INTERP; then
        fail 'the trampoline is dynamically linked'
    fi
    chmod 0755 "$tramp"
    echo "including the opt-in trampoline: $tramp ($(stat -c %s "$tramp") bytes)"
    echo "  it is only used when the command line also asks for it:"
    echo "    gts9_minimal_init=/run/gts9-minimal-pid1"
else
    echo "no trampoline (opt-in): the handoff uses /sbin/init directly"
fi

# ---------------------------------------------------------------------------
# There is no firmware and no module staging here, by construction.  The commands
# are absent rather than merely unused, so this cannot regress by someone adding a
# copy "for a test": the production image has no code path that puts a blob in
# init_boot, and the manifest records contains_firmware=no.
# ---------------------------------------------------------------------------
"$repo_root/scripts/make-initramfs.sh" --root "$tree" --out "$out"

gts9_write_manifest "$out" minimal "$tree" "$bb_bin" "" ""

cat <<EOF

Production initramfs ready: $out
tree kept for inspection  : $tree

Package and check a bundle with:
  ./scripts/build-boot-bundle.sh --initramfs $out \\
    --cmdline boot/cmdline.example.txt --bootconfig boot/bootconfig.example.txt
  ./scripts/validate-boot-bundle.sh

Nothing was flashed and no device was touched.
EOF
