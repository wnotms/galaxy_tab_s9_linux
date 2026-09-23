#!/bin/sh
# Reboot the tablet from a running Debian system into TWRP.
#
# Run this on the tablet, as root:
#
#	gts9-debian-to-recovery              show what it found, then ask
#	gts9-debian-to-recovery --yes        write the BCB and reboot
#	gts9-debian-to-recovery --check      inspect only, change nothing
#	gts9-debian-to-recovery --clear      remove a recovery request
#
# How it works, and why it is not `reboot recovery`:
#
# Android's boot chain picks the boot mode from the bootloader control block -
# the first bytes of the `misc` partition, which is a *UFS* write.  Writing
# "boot-recovery" there makes ABL start recovery on the next boot.
#
# `reboot recovery` cannot be used on this board instead.  It reaches
# nvmem-reboot-mode, which writes the PMK8550's SPMI SDAM cell, and an SPMI
# write blocks this kernel uninterruptibly (tests 024/025, see
# docs/REBOOT_MODES.md).  A plain reboot is safe: the kernel passes a NULL
# command, reboot-mode substitutes "normal", that matches no declared mode and
# the driver never touches the SDAM.  So: write the BCB, then ask for an
# ordinary restart.
#
# Getting back to Debian needs nothing extra.  The initramfs clears a stale BCB
# before every mainline handoff (clear_stale_bcb in boot/bringup-init.sh, before
# boot_rootfs), so the request is consumed by exactly one boot: TWRP once, and
# the next reset returns here.
#
# If ABL ignores the request, the tablet boots mainline again and the BCB is
# cleared on the way - a failed attempt costs one ordinary boot, not a dead
# tablet.  Holding Volume Up during power-on still selects TWRP by hand.
set -eu

PROG=${0##*/}
MISC_LABEL=misc
BCB_COMMAND='boot-recovery'
BCB_BYTES=2048
# The recorded layout for this board: GPT index 9, 256 sectors, /dev/sda10.
# Used only as a cross-check, never as the way the device is found.
EXPECTED_SECTORS=256

action=write
assume_yes=0
do_reboot=1
dev=

die() {
	echo "$PROG: $*" >&2
	exit 1
}
warn() {
	echo "$PROG: WARNING: $*" >&2
}
info() {
	echo "$PROG: $*"
}

usage() {
	# Print this file's own header comment, and nothing else.
	sed -n '2,/^set -eu$/p' "$0" | sed '$d; s/^# \{0,1\}//'
	exit 0
}

while [ $# -gt 0 ]; do
	case "$1" in
	--check | --dry-run) action=check ;;
	--clear) action=clear ;;
	--yes | -y) assume_yes=1 ;;
	--no-reboot) do_reboot=0 ;;
	--device) shift; [ $# -gt 0 ] || die "--device needs a path"; dev=$1 ;;
	--help | -h) usage ;;
	*) die "unknown argument '$1' (try --help)" ;;
	esac
	shift
done

[ "$(id -u)" = 0 ] || die "must run as root (try: sudo $PROG)"

# ---------------------------------------------------------------------------
# Finding `misc`, and refusing to write anywhere else.
#
# A wrong device here means writing a bootloader control block into somebody
# else's partition, so every check fails closed.  The label alone is not
# enough: the parent must be a SCSI/UFS disk (this excludes the microSD, which
# is mmcblk), and the kernel's own size for the partition is cross-checked.
# ---------------------------------------------------------------------------

find_misc_by_symlink() {
	[ -L "/dev/disk/by-partlabel/$MISC_LABEL" ] || return 1
	resolved=$(readlink -f "/dev/disk/by-partlabel/$MISC_LABEL" 2>/dev/null) || return 1
	[ -b "$resolved" ] || return 1
	echo "$resolved"
}

find_misc_by_scan() {
	for disk in /dev/sd?; do
		[ -b "$disk" ] || continue
		for part in "$disk"[0-9]*; do
			[ -b "$part" ] || continue
			base=${part##*/}
			name=$(sed -n 's/^PARTNAME=//p' "/sys/class/block/$base/uevent" 2>/dev/null) || continue
			[ "$name" = "$MISC_LABEL" ] || continue
			echo "$part"
			return 0
		done
	done
	return 1
}

partition_label() {
	sed -n 's/^PARTNAME=//p' "/sys/class/block/${1##*/}/uevent" 2>/dev/null
}

validate_misc() {
	candidate=$1
	base=${candidate##*/}

	[ -b "$candidate" ] || die "$candidate is not a block device"

	case "$base" in
	mmcblk* | nvme* | loop* | dm-* | md* | ram*)
		die "refusing $candidate: $base is not a UFS partition"
		;;
	sd[0-9]*) : ;;
	*) die "refusing $candidate: unexpected partition name" ;;
	esac

	label=$(partition_label "$candidate")
	[ -n "$label" ] || die "$candidate has no GPT partition label; refusing to guess"
	[ "$label" = "$MISC_LABEL" ] || die "$candidate is labelled '$label', not '$MISC_LABEL'"

	link=$(readlink -f "/sys/class/block/$base")
	parent=$(basename "$(dirname "$link")")
	case "$parent" in
	sd?) : ;;
	*) die "refusing $candidate: parent '$parent' is not a SCSI/UFS disk" ;;
	esac

	sectors=$(cat "/sys/class/block/$base/size" 2>/dev/null) || die "cannot read the size of $candidate"
	case "$sectors" in '' | *[!0-9]*) die "unreadable size for $candidate" ;; esac
	[ "$sectors" -ge 4 ] || die "$candidate is too small for a BCB"
	if [ "$sectors" != "$EXPECTED_SECTORS" ]; then
		warn "$candidate is $sectors sectors, expected $EXPECTED_SECTORS; continuing, the label is authoritative"
	fi

	mounted=$(awk -v d="$candidate" '$1 == d { print $2; exit }' /proc/mounts)
	[ -z "$mounted" ] || die "$candidate is mounted at $mounted; refusing to write to a mounted partition"

	rootdev=$(findmnt -no SOURCE / 2>/dev/null || true)
	if [ -n "$rootdev" ] && [ "$(readlink -f "$rootdev")" = "$candidate" ]; then
		die "$candidate is the running root filesystem"
	fi
}

bcb_command() {
	tmp=$(mktemp) || die "cannot create a temporary file to read the BCB"
	if ! timeout 5 dd if="$1" of="$tmp" bs=32 count=1 2>/dev/null; then
		rm -f "$tmp"
		die "cannot read the BCB from $1"
	fi
	command=$(tr -d '\0' < "$tmp")
	rm -f "$tmp"
	printf '%s' "$command"
}

# ---------------------------------------------------------------------------
# The write itself: one zeroed 2048-byte block with the command at offset 0.
# This is byte-for-byte the sequence boot/gts9-to-recovery.sh uses, which is the
# one that has actually put this tablet into TWRP.
# ---------------------------------------------------------------------------

write_bcb() {
	tmp=$(mktemp) || die "cannot create a temporary file"
	trap 'rm -f "$tmp"' EXIT INT TERM

	dd if=/dev/zero of="$tmp" bs=$BCB_BYTES count=1 2>/dev/null || die "cannot build the BCB"
	printf '%s' "$BCB_COMMAND" | dd of="$tmp" bs=1 seek=0 conv=notrunc 2>/dev/null ||
		die "cannot set the BCB command"

	dd if="$tmp" of="$dev" bs=$BCB_BYTES count=1 conv=notrunc 2>/dev/null ||
		die "cannot write the BCB to $dev"
	sync

	readback=$(bcb_command "$dev")
	[ "$readback" = "$BCB_COMMAND" ] ||
		die "read-back mismatch on $dev (got '$readback'); do not trust this boot"

	rm -f "$tmp"
	trap - EXIT INT TERM
	info "BCB written to $dev and verified: $BCB_COMMAND"
}

clear_bcb() {
	dd if=/dev/zero of="$dev" bs=$BCB_BYTES count=1 conv=notrunc 2>/dev/null ||
		die "cannot clear the BCB in $dev"
	sync
	readback=$(bcb_command "$dev")
	[ -z "$readback" ] || die "read-back after clearing still says '$readback'"
	info "BCB cleared in $dev"
}

reboot_now() {
	# A plain restart only.  Asking the kernel for a mode string would reach
	# nvmem-reboot-mode and write the PMK8550's SPMI SDAM cell, and an SPMI
	# write blocks this kernel uninterruptibly (tests 024/025).
	info "rebooting with a plain restart; the recovery request is in the BCB, not in the kernel"
	if command -v systemctl >/dev/null 2>&1; then
		exec systemctl reboot
	fi
	exec reboot
}

confirm_write() {
	[ "$assume_yes" = 1 ] && return 0
	[ -t 0 ] || die "no terminal to confirm on; re-run with --yes to proceed"

	if [ "$current" = "$BCB_COMMAND" ]; then
		prompt="$dev already asks for recovery; reboot now?"
	elif [ "$do_reboot" = 1 ]; then
		prompt="write $BCB_COMMAND to $dev and reboot?"
	else
		prompt="write $BCB_COMMAND to $dev without rebooting?"
	fi
	printf '%s: %s [y/N] ' "$PROG" "$prompt"
	read -r reply || reply=
	case "$reply" in
	y | Y | yes | YES) : ;;
	*) die "not confirmed; no change made" ;;
	esac
}

# ---------------------------------------------------------------------------

if [ -z "$dev" ]; then
	dev=$(find_misc_by_symlink || find_misc_by_scan) ||
		die "no GPT partition labelled '$MISC_LABEL' found; is the UFS probe up? (lsblk -o NAME,LABEL,PARTLABEL)"
	info "found the $MISC_LABEL partition as $dev"
else
	info "using the requested device $dev"
fi
dev=$(readlink -f "$dev")
validate_misc "$dev"

current=$(bcb_command "$dev")
case "$action" in
check)
	info "device        : $dev ($(cat "/sys/class/block/${dev##*/}/size") sectors)"
	info "partition name: $(partition_label "$dev")"
	info "BCB command   : ${current:-(empty, boots mainline)}"
	info "no change made"
	;;
clear)
	[ -n "$current" ] || die "$dev holds no BCB command; nothing to clear"
	info "current BCB command: $current"
	clear_bcb
	;;
write)
	if [ "$current" = "$BCB_COMMAND" ]; then
		info "$dev already asks for recovery; keeping it"
		if [ "$do_reboot" = 1 ]; then
			confirm_write
		fi
	else
		info "current BCB command: ${current:-(empty)}"
		confirm_write
		write_bcb
	fi
	;;
esac

if [ "$action" = write ] && [ "$do_reboot" = 1 ]; then
	reboot_now
fi
info "done; nothing was rebooted"
