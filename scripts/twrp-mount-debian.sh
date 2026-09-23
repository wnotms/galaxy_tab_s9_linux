#!/bin/sh
# Safely identify and mount the Debian microSD root from TWRP.
#
# TWRP is the official offline channel for this device: the minimal profile can
# boot with a black panel and no USB console, and the only remaining evidence
# is /var/log/gts9-minimal-last-boot on the Debian root filesystem.  Recovery
# block numbering is not guaranteed to match the running system, so this script
# never assumes /dev/mmcblk1p1: it enumerates the MMC partitions, reads their
# filesystem type, label, UUID and size, and verifies the Debian userspace
# before it claims success.
#
# Guarantees:
#   * only MMC partitions are considered; UFS devices (/dev/sd*) are refused
#   * ext4 is confirmed through blkid, with a superblock-magic fallback
#   * a candidate is only accepted when it contains Debian (/etc/debian_version
#     or ID=debian), unless --force is given
#   * nothing is ever formatted, created or repaired; no fsck runs at all
#   * the default mount is read-only (-o ro,noload) for inspecting logs
#   * --rw exists only for deliberate maintenance
#
# Usage:
#   twrp-mount-debian.sh [--list] [--rw] [--device DEV | --uuid UUID | --label LABEL]
#                        [--force] [--umount] [-h]
#
# Typical use:
#   sh /tmp/twrp-mount-debian.sh --list
#   sh /tmp/twrp-mount-debian.sh
#   cat /mnt/debian/var/log/gts9-minimal-last-boot
#   sh /tmp/twrp-mount-debian.sh --umount
#
# GTS9_TWRP_MOUNTPOINT, GTS9_TWRP_DEV_DIRS and GTS9_TWRP_ALLOW_REGULAR exist so
# the host tests can drive the detection against temporary fixtures.

MOUNTPOINT=${GTS9_TWRP_MOUNTPOINT:-/mnt/debian}
DEV_DIRS=${GTS9_TWRP_DEV_DIRS:-/dev/block /dev}
ALLOW_REGULAR=${GTS9_TWRP_ALLOW_REGULAR:-0}
RECORD_NAME=gts9-minimal-last-boot

MODE=ro
EXPLICIT_DEVICE=
WANT_UUID=
WANT_LABEL=
DO_LIST=0
DO_UMOUNT=0
DO_FORCE=0

die() { echo "twrp-mount-debian: $*" >&2; exit 1; }
note() { echo "twrp-mount-debian: $*"; }

usage() {
	sed -n '2,32p' "$0"
}

while [ $# -gt 0 ]; do
	case "$1" in
	--list) DO_LIST=1; shift ;;
	--rw) MODE=rw; shift ;;
	--device) EXPLICIT_DEVICE=${2:?--device needs a device}; shift 2 ;;
	--uuid) WANT_UUID=${2:?--uuid needs a value}; shift 2 ;;
	--label) WANT_LABEL=${2:?--label needs a value}; shift 2 ;;
	--force) DO_FORCE=1; shift ;;
	--umount) DO_UMOUNT=1; shift ;;
	-h | --help) usage; exit 0 ;;
	*) die "unknown argument: $1 (see --help)" ;;
	esac
done

umount_debian() {
	if grep -q " $MOUNTPOINT " /proc/mounts 2>/dev/null; then
		umount "$MOUNTPOINT" || die "could not unmount $MOUNTPOINT"
		sync
		note "unmounted $MOUNTPOINT"
	else
		note "$MOUNTPOINT is not mounted"
	fi
}

if [ "$DO_UMOUNT" = 1 ]; then
	umount_debian
	exit 0
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

is_mmc_partition() {
	# mmcblk0p1, mmcblk1p2, ... - never a whole disk and never /dev/sd*
	case "$1" in
	*/mmcblk*p*) return 0 ;;
	*) return 1 ;;
	esac
}

block_ok() {
	[ -b "$1" ] && return 0
	# Test seam only: the host cannot create block device nodes.
	[ "$ALLOW_REGULAR" = 1 ] && [ -f "$1" ]
}

dev_name() { basename "$1"; }

blkid_field() {
	# blkid_field DEVICE FIELD
	blkid "$1" 2>/dev/null | sed -n "s/.*$2=\"\([^\"]*\)\".*/\1/p" | head -n 1
}

has_blkid() { command -v blkid >/dev/null 2>&1; }

ext4_magic_ok() {
	# ext4 superblock magic 0xEF53 at offset 1080 (little endian bytes 53 ef)
	[ "$(dd if="$1" bs=1 skip=1080 count=2 2>/dev/null | od -An -tx1 | tr -d ' \n')" = "53ef" ]
}

fs_type() {
	# fs_type DEVICE -> filesystem type, or an empty string
	if has_blkid; then
		type=$(blkid_field "$1" TYPE)
		if [ -n "$type" ]; then
			echo "$type"
			return 0
		fi
	fi
	if ext4_magic_ok "$1"; then
		echo ext4
	fi
}

device_size() {
	# device_size DEVICE -> size in 512-byte sectors
	name=$(dev_name "$1")
	if [ -r "/sys/class/block/$name/size" ]; then
		cat "/sys/class/block/$name/size"
		return 0
	fi
	if [ -f "$1" ]; then
		bytes=$(wc -c < "$1" 2>/dev/null || echo 0)
		echo $((bytes / 512))
		return 0
	fi
	echo 0
}

list_partitions() {
	for dir in $DEV_DIRS; do
		[ -d "$dir" ] || continue
		for dev in "$dir"/mmcblk*p*; do
			[ -e "$dev" ] || continue
			block_ok "$dev" || continue
			echo "$dev"
		done
	done | sort -u
}

candidate_line() {
	# candidate_line DEVICE -> "device|fstype|label|uuid|sectors"
	dev=$1
	type=$(fs_type "$dev")
	label=$(blkid_field "$dev" LABEL)
	uuid=$(blkid_field "$dev" UUID)
	[ -n "$label" ] || label=-
	[ -n "$uuid" ] || uuid=-
	printf '%s|%s|%s|%s|%s\n' "$dev" "$type" "$label" "$uuid" "$(device_size "$dev")"
}

verify_debian() {
	# verify_debian MOUNTPOINT
	[ -f "$MOUNTPOINT/etc/debian_version" ] && return 0
	if [ -f "$MOUNTPOINT/etc/os-release" ] && \
	   grep -qi '^ID=debian' "$MOUNTPOINT/etc/os-release" 2>/dev/null; then
		return 0
	fi
	return 1
}

mount_candidate() {
	# mount_candidate DEVICE MODE
	dev=$1
	mode=$2
	[ "$mode" = rw ] || mode=ro,noload
	mount -t ext4 -o "$mode" "$dev" "$MOUNTPOINT" 2>/dev/null
}

# ---------------------------------------------------------------------------
# Enumerate
# ---------------------------------------------------------------------------

[ -d "$MOUNTPOINT" ] || mkdir -p "$MOUNTPOINT" 2>/dev/null || \
	die "cannot create $MOUNTPOINT"
[ "$MOUNTPOINT" != "/" ] || die 'refusing to mount over /'

tmpdir=$(mktemp -d 2>/dev/null || echo "/tmp/gts9-twrp-mount.$$")
mkdir -p "$tmpdir" 2>/dev/null || die "cannot create $tmpdir"
trap 'rm -rf "$tmpdir"' EXIT

lines=
for dev in $(list_partitions); do
	line=$(candidate_line "$dev")
	lines="${lines}${line}
"
done

if [ "$DO_LIST" = 1 ]; then
	printf '%-24s %-8s %-16s %-38s %s\n' DEVICE FSTYPE LABEL UUID SECTORS
	# IFS='|' read, not ${line%%|*}: TWRP's /system/bin/sh (mksh) treats the
	# unquoted '|' inside a parameter expansion as a pipe and expands to "".
	printf '%s' "$lines" | while IFS='|' read -r dev type label uuid sectors; do
		[ -n "$dev" ] || continue
		[ -n "$type" ] || type=-
		[ -n "$label" ] || label=-
		[ -n "$uuid" ] || uuid=-
		printf '%-24s %-8s %-16s %-38s %s\n' \
			"$dev" "$type" "$label" "$uuid" "$sectors"
	done
	[ -n "$lines" ] || note 'no MMC partitions found'
	if ! has_blkid; then
		note 'blkid is unavailable here; LABEL/UUID are shown as -'
	fi
	echo
	note 'UFS devices (/dev/sd*) are never listed or mounted'
	exit 0
fi

# ---------------------------------------------------------------------------
# Select
# ---------------------------------------------------------------------------

selected=
if [ -n "$EXPLICIT_DEVICE" ]; then
	case "$EXPLICIT_DEVICE" in
	/dev/sd*) die "refusing UFS device $EXPLICIT_DEVICE; only the microSD is supported" ;;
	esac
	is_mmc_partition "$EXPLICIT_DEVICE" || \
		die "$EXPLICIT_DEVICE is not an MMC partition (expected mmcblk*p*)"
	block_ok "$EXPLICIT_DEVICE" || die "$EXPLICIT_DEVICE does not exist"
	[ "$(fs_type "$EXPLICIT_DEVICE")" = ext4 ] || \
		die "$EXPLICIT_DEVICE is not ext4; refusing to mount it"
	selected=$EXPLICIT_DEVICE
else
	# Labels first (a Debian/root label is the strongest hint), then the
	# largest partition, and always confirm by mounting read-only.
	printf '%s' "$lines" | while IFS='|' read -r dev type label uuid sectors; do
		[ -n "$dev" ] || continue
		[ "$type" = ext4 ] || continue
		if [ -n "$WANT_UUID" ] && [ "$uuid" != "$WANT_UUID" ]; then
			continue
		fi
		if [ -n "$WANT_LABEL" ] && [ "$label" != "$WANT_LABEL" ]; then
			continue
		fi
		printf '%s|%s|%s|%s|%s\n' "$dev" "$type" "$label" "$uuid" "$sectors"
	done | sort -t'|' -k3,3r -k5,5nr > "$tmpdir/ranked"
	if [ ! -s "$tmpdir/ranked" ]; then
		die 'no ext4 MMC partition found; nothing was mounted and nothing was changed'
	fi
fi

# ---------------------------------------------------------------------------
# Mount and verify
# ---------------------------------------------------------------------------

if grep -q " $MOUNTPOINT " /proc/mounts 2>/dev/null; then
	die "$MOUNTPOINT is already mounted; run --umount first"
fi

try_mount() {
	dev=$1
	if ! mount_candidate "$dev" "$MODE"; then
		note "mount failed for $dev"
		return 1
	fi
	if [ "$DO_FORCE" != 1 ] && ! verify_debian "$MOUNTPOINT"; then
		note "$dev does not contain a Debian userspace; unmounting it"
		umount "$MOUNTPOINT" 2>/dev/null || true
		return 1
	fi
	return 0
}

if [ -n "$selected" ]; then
	try_mount "$selected" || die "could not use $selected"
	final=$selected
else
	: > "$tmpdir/result"
	while IFS='|' read -r dev type label uuid sectors; do
		[ -n "$dev" ] || continue
		note "trying $dev"
		if try_mount "$dev"; then
			printf '%s\n' "$dev" > "$tmpdir/result"
			break
		fi
	done < "$tmpdir/ranked"
	final=$(cat "$tmpdir/result" 2>/dev/null || true)
	[ -n "$final" ] || die 'no candidate contained a Debian userspace; nothing is mounted'
fi

label=$(blkid_field "$final" LABEL)
uuid=$(blkid_field "$final" UUID)
if [ "$MODE" = rw ]; then
	note "mounted $final read-write at $MOUNTPOINT (maintenance mode)"
else
	note "mounted $final read-only at $MOUNTPOINT (logs only; no journal replay)"
fi
note "device=$final label=${label:--} uuid=${uuid:--}"
note "run 'sh $0 --umount' when done; nothing was formatted and no fsck ran"

record=$MOUNTPOINT/var/log/$RECORD_NAME
if [ -f "$record" ]; then
	echo
	echo "--- $record ---"
	cat "$record"
	echo '--- end ---'
else
	note "no $RECORD_NAME in $MOUNTPOINT/var/log"
fi
