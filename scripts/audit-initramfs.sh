#!/usr/bin/env bash
# Audit the contents of a built initramfs tree.
#
# Why this exists: by 2026-09-26 the bring-up initramfs had accumulated the
# features of 200+ physical bring-up tests, and the production Debian boot ran
# through all of it through a `gts9_minimal_rootfs=1` branch inside
# bringup-init.sh.  Deciding what may move out of that path needs the actual
# contents and the actual call graph, not an impression of them - so this prints
# both.
#
# The classification below is derived from the SOURCES, not from filenames:
#
#   production_required  - reachable from the minimal rootfs handoff
#                          (boot/minimal-rootfs-init.sh and what it sources or
#                          execs).  Anything here must stay in a production image
#                          or the handoff breaks.
#   debug_only           - reachable only from boot/bringup-init.sh's diagnostic
#                          paths: hardware report, MSC export, panel recovery,
#                          GPT/BCB, RTC, rescue shells.
#   currently_unreferenced - shipped in the image but not named by any script.
#                          Either dead weight or reached only through the
#                          command line; both are worth knowing.
#
# Usage:
#   scripts/audit-initramfs.sh [TREE] [--profile NAME] [--image FILE]
#
# Defaults: TREE=out/bringup-initramfs, IMAGE=out/boot-bundle/initramfs-bringup.img
#
# Read-only: it never writes to the tree or the image.
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)

tree=${GTS9_INITRAMFS_TREE:-$repo_root/out/bringup-initramfs}
profile=${GTS9_INITRAMFS_PROFILE:-bringup}
image=${GTS9_INITRAMFS_IMAGE:-$repo_root/out/boot-bundle/initramfs-bringup.img}

while [ $# -gt 0 ]; do
	case "$1" in
	--profile) profile=${2:?--profile needs a name}; shift 2 ;;
	--image) image=${2:?--image needs a path}; shift 2 ;;
	-h | --help)
		sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'
		exit 0
		;;
	-*) echo "unknown option: $1" >&2; exit 2 ;;
	*) tree=$1; shift ;;
	esac
done

[ -d "$tree" ] || {
	echo "audit-initramfs: no such tree: $tree" >&2
	echo "  build one first: ./scripts/build-bringup-initramfs.sh" >&2
	exit 1
}

# ---------------------------------------------------------------------------
# The sources that define the two call graphs.
# ---------------------------------------------------------------------------
minimal_sources=(
	"$repo_root/boot/minimal-rootfs-init.sh"
	"$repo_root/boot/minimal-rootfs-state.sh"
)
debug_sources=(
	"$repo_root/boot/bringup-init.sh"
)

# Grep a set of sources for a real reference to a name, and report the first file
# that has one.
#
# The match has to be a reference rather than a substring.  An earlier version of
# this script grepped plainly for "init" and matched `minimal_state_init`,
# `initialized` and every `init-found` stage marker, which classified nearly every
# file as production_required and made the whole table useless.
#
# The allowed leading characters cover the ways these scripts actually name a
# sibling: an absolute path (`/minimal-rootfs-state.sh`), a command argument
# (`cp /sbin/gts9-minimal-pid1 ...`), and a variable default
# (`MINIMAL_STATE_LIB=${...:-/minimal-rootfs-state.sh}`) - that last one is why
# `=`, `:` and the closing `}` are in the trailing class, and without them the
# state library was reported as unreferenced even though the initramfs sources it.
mentions() {
	local name=$1
	shift
	grep -lE "(^|[[:space:]/=:\"'])${name}([[:space:]]|\$|\"|'|}|;)" "$@" 2>/dev/null | head -1
}

classify() {
	local name=$1
	if mentions "$name" "${minimal_sources[@]}" >/dev/null; then
		echo production_required
	elif mentions "$name" "${debug_sources[@]}" >/dev/null; then
		echo debug_only
	else
		echo currently_unreferenced
	fi
}

# ---------------------------------------------------------------------------
# Size accounting.
# ---------------------------------------------------------------------------
compressed_bytes=0
if [ -f "$image" ]; then
	compressed_bytes=$(stat -c %s "$image")
fi
unpacked_bytes=$(du -sb "$tree" | awk '{print $1}')
regular_files=$(find "$tree" -type f | wc -l)
symlinks=$(find "$tree" -type l | wc -l)
directories=$(find "$tree" -type d | wc -l)

dir_bytes() {
	# dir_bytes RELATIVE_PATH -> bytes, or nothing when absent
	[ -e "$tree/$1" ] || return 0
	du -sb "$tree/$1" 2>/dev/null | awk '{print $1}'
}

firmware_bytes=$(dir_bytes lib/firmware)
modules_bytes=$(dir_bytes lib/modules)

echo "profile=$profile"
echo "tree=$tree"
echo "image=$image"
echo "compressed_bytes=$compressed_bytes"
echo "unpacked_bytes=$unpacked_bytes"
echo "regular_files=$regular_files"
echo "symlinks=$symlinks"
echo "directories=$directories"
echo "firmware_bytes=${firmware_bytes:-0}"
echo "modules_bytes=${modules_bytes:-0}"

# ---------------------------------------------------------------------------
# Whole-file inventory, largest first.  Symlinks are counted but not listed:
# they are BusyBox applets and cost nothing.
# ---------------------------------------------------------------------------
echo
echo "largest_files:"
find "$tree" -type f -printf '%s %P\n' | sort -rn | head -20 |
	awk -v root="$tree" '{printf "  %9d  %s\n", $1, $2}'

# ---------------------------------------------------------------------------
# The files that carry behaviour, classified by reachability.
# ---------------------------------------------------------------------------
echo
echo "classified:"
for name in init minimal-rootfs-init minimal-rootfs-state.sh \
	sbin/gts9-minimal-pid1 sbin/gts9-exec-default sbin/gts9-to-recovery \
	bin/gts9-reboot-recovery bin/busybox; do
	[ -e "$tree/$name" ] || continue
	size=$(stat -c %s "$tree/$name")
	kind=$(classify "$(basename "$name")")
	printf '  %-26s %9d  %s\n' "/$name" "$size" "$kind"
done

# Firmware and modules are whole-tree facts rather than single files.
if [ -n "${firmware_bytes:-}" ]; then
	while IFS= read -r f; do
		printf '  %-26s %9d  %s\n' "/${f#"$tree"/}" "$(stat -c %s "$f")" debug_only
	done < <(find "$tree/lib/firmware" -type f 2>/dev/null)
fi
if [ -n "${modules_bytes:-}" ]; then
	printf '  %-26s %9d  %s\n' "/lib/modules" "$modules_bytes" debug_only
fi

# ---------------------------------------------------------------------------
# Summary counts per class, for a quick before/after comparison.
# ---------------------------------------------------------------------------
echo
echo "classification_summary:"
for kind in production_required debug_only currently_unreferenced; do
	n=0
	for name in init minimal-rootfs-init minimal-rootfs-state.sh \
		sbin/gts9-minimal-pid1 sbin/gts9-exec-default sbin/gts9-to-recovery \
		bin/gts9-reboot-recovery bin/busybox; do
		[ -e "$tree/$name" ] || continue
		[ "$(classify "$(basename "$name")")" = "$kind" ] && n=$((n + 1))
	done
	printf '  %-24s %d\n' "$kind" "$n"
done

# ---------------------------------------------------------------------------
# Capability probes.  These are the facts a production image must be able to
# state as "no", so they are printed rather than inferred from the file list.
# ---------------------------------------------------------------------------
has() {
	# has RELATIVE_PATH -> yes/no
	[ -e "$tree/$1" ] && echo yes || echo no
}

# Does any shipped script CREATE a configfs gadget?  A grep for the word would
# match the comments that explain why it no longer does, so this looks for the
# directory-creation and UDC-binding commands that actually do it.
creates_gadget=no
while IFS= read -r f; do
	if grep -qE 'mkdir[^\n]*usb_gadget|>\s*\$?\{?G\}?/UDC|> "\$GADGET/UDC"' "$f" 2>/dev/null; then
		creates_gadget=yes
	fi
done < <(find "$tree" -maxdepth 2 -type f \( -name 'init' -o -name '*.sh' \) 2>/dev/null)

# Same discipline for the other capabilities: match the operation, not the noun.
creates_msc=no
grep -qE 'mass_storage\.usb0' "$tree/init" 2>/dev/null && creates_msc=yes

has_gpt_parser=$(grep -qE '/dev/disk/by-partlabel|PARTNAME|by-name' "$tree/init" 2>/dev/null && echo yes || echo no)
has_rtc=$(grep -qE '/dev/rtc|rtc-state|hwclock' "$tree/init" 2>/dev/null && echo yes || echo no)
has_bcb=$(grep -qE 'boot-recovery|BCB|/dev/block/by-name' "$tree/init" 2>/dev/null && echo yes || echo no)
has_display=$(grep -qE 'fb0/blank|fb0|display_recover' "$tree/init" 2>/dev/null && echo yes || echo no)
has_report=$(grep -qE 'regulator_summary|devices_deferred|bringup-report' "$tree/init" 2>/dev/null && echo yes || echo no)

echo
echo "capabilities:"
printf '  %-26s %s\n' "contains_modules" "$(has lib/modules)"
printf '  %-26s %s\n' "contains_firmware" "$(has lib/firmware)"
printf '  %-26s %s\n' "contains_usb_gadget_creator" "$creates_gadget"
printf '  %-26s %s\n' "contains_msc_setup" "$creates_msc"
printf '  %-26s %s\n' "contains_gpt_parser" "$has_gpt_parser"
printf '  %-26s %s\n' "contains_rtc_telemetry" "$has_rtc"
printf '  %-26s %s\n' "contains_bcb_write" "$has_bcb"
printf '  %-26s %s\n' "contains_display_recovery" "$has_display"
printf '  %-26s %s\n' "contains_hardware_report" "$has_report"

# Which script is /init, by CONTENT rather than by name.  The builders copy or
# install a source file to /init, so the filename in the image is always exactly
# "init" and tells you nothing - an earlier version of this probe compared
# basename(readlink /init) to bringup-init.sh, which is never true and reported
# "no" for a bringup image that plainly was one.
#
# Both candidate sources are identified by a marker unique to each, so this keeps
# working if either is renamed.
init_source=unknown
if grep -q 'MINIMAL_ROOTFS=' "$tree/init" 2>/dev/null &&
	grep -q 'setup_usb_gadget\|display_recover' "$tree/init" 2>/dev/null; then
	init_source=bringup-init.sh
elif grep -q 'ROOTFS_DEVICE=' "$tree/init" 2>/dev/null &&
	grep -q 'minimal_state_stage' "$tree/init" 2>/dev/null; then
	init_source=minimal-rootfs-init.sh
fi
printf '  %-26s %s\n' "init_source" "$init_source"

# Does /init create a USB gadget, by operation rather than by noun?
init_gadget=no
grep -qE 'mkdir[^\n]*usb_gadget|> "\$G/UDC"|> "\$GADGET/UDC"' "$tree/init" 2>/dev/null && init_gadget=yes
printf '  %-26s %s\n' "init_creates_usb_gadget" "$init_gadget"

exit 0
