#!/usr/bin/env bash
# Install the gts9 Debian userspace on a mounted Debian root filesystem, or
# build the same tree as a tarball that TWRP can extract offline.
#
# Direct install (host, with the card mounted):
#
#	sudo ./scripts/install-debian-rootfs.sh /mnt/debian
#
# Offline deploy through TWRP (recommended: the tablet's recovery has no repo):
#
#	./scripts/install-debian-rootfs.sh --tar out/gts9-debian-overlay.tar
#	adb push out/gts9-debian-overlay.tar /tmp/
#	# in TWRP:
#	cd /mnt/debian && tar -xpf /tmp/gts9-debian-overlay.tar && sync
#	sh /mnt/debian/usr/libexec/gts9-enable-units /mnt/debian
#
# Both modes install the same files from the same sources, and both enable the
# units with the same helper, so a deployed tarball and a direct install end up
# identical.  Everything is idempotent: running it again over an existing rootfs
# replaces the managed files and leaves the rest of Debian alone.
#
# Installed content:
#   * rootfs-overlay/ (units, helpers, logind and getty configuration; regular
#     files only - the tarball carries no symlinks, see gts9-enable-units)
#   * enablement symlinks created by usr/libexec/gts9-enable-units from each
#     unit's own WantedBy= (no systemctl needed, works in TWRP)
#   * kernel modules under lib/modules/<release> plus a basedir depmod
#   * firmware under lib/firmware/
#
# It never formats, never runs fsck, never writes outside the target and
# refuses to operate on /.
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
overlay=$repo_root/rootfs-overlay
modules_root=${GTS9_MODULES_ROOT:-$repo_root/out/kernel-gts9wifi/modules-root}
firmware_root=${GTS9_FIRMWARE_ROOT:-$repo_root/.work/firmware}
target=
tar_file=
do_modules=1
do_firmware=1
depmod=${GTS9_DEPMOD:-depmod}

usage() {
	sed -n '2,30p' "$0"
}

fail() { echo "install-debian-rootfs: $*" >&2; exit 1; }
note() { echo "install-debian-rootfs: $*"; }

while [ $# -gt 0 ]; do
	case "$1" in
	--tar) tar_file=${2:?--tar needs a path}; shift 2 ;;
	--modules) modules_root=${2:?--modules needs a directory}; shift 2 ;;
	--firmware) firmware_root=${2:?--firmware needs a directory}; shift 2 ;;
	--skip-modules) do_modules=0; shift ;;
	--skip-firmware) do_firmware=0; shift ;;
	-h | --help) usage; exit 0 ;;
	-*) fail "unknown option: $1" ;;
	*) target=$1; shift ;;
	esac
done

[ -d "$overlay" ] || fail "missing overlay tree: $overlay"
if [ -n "$tar_file" ] && [ -n "$target" ]; then
	fail 'use either TARGET or --tar FILE, not both'
fi
if [ -z "$tar_file" ] && [ -z "$target" ]; then
	usage >&2
	fail 'a TARGET mountpoint or --tar FILE is required'
fi

copy_overlay() {
	local dest=$1
	# The overlay contains regular files and directories only: enablement
	# symlinks are created by usr/libexec/gts9-enable-units below, because
	# TWRP's busybox tar refuses to replace an existing symlink that points
	# outside the extraction root and would then exit non-zero.
	cp -a "$overlay"/. "$dest"/
}

install_units_and_enablement() {
	local dest=$1
	local helper=$dest/usr/libexec/gts9-enable-units
	[ -f "$helper" ] || fail "missing $helper in the overlay"
	# Same helper the TWRP procedure runs after extraction, so a direct
	# install and a deployed tarball enable exactly the same units.
	sh "$helper" "$dest" || fail 'could not create the unit enablement symlinks'
}

module_release() {
	# module_release MODULES_ROOT -> the single <release> under lib/modules
	local root=$1 release
	local -a releases=()
	for path in "$root"/lib/modules/*/; do
		[ -d "$path" ] || continue
		releases+=("$(basename "$path")")
	done
	[ "${#releases[@]}" -eq 1 ] || {
		fail "$root does not contain exactly one kernel release (${releases[*]:-none})"
	}
	release=${releases[0]}
	# The build writes kernel.release next to modules-root; a mismatch means the
	# modules do not belong to the kernel that is being booted.
	local recorded
	recorded=$(dirname "$root")/kernel.release
	if [ -f "$recorded" ]; then
		local expected
		expected=$(cat "$recorded")
		[ "$expected" = "$release" ] || fail \
			"module release $release does not match kernel.release $expected"
	fi
	printf '%s' "$release"
}

install_modules() {
	local dest=$1 release src tmp
	[ "$do_modules" = 1 ] || { note 'kernel modules skipped'; return 0; }
	if [ ! -d "$modules_root" ]; then
		note "no kernel modules at $modules_root; skipping"
		return 0
	fi
	release=$(module_release "$modules_root")
	src=$modules_root/lib/modules/$release
	[ -d "$src" ] || fail "missing module directory: $src"
	# usr/lib/modules, never lib/modules: Debian is usr-merged, and an archive
	# entry below lib/ makes TWRP's busybox tar replace the /lib symlink with a
	# real directory.  That is what broke /sbin/init and panicked the kernel in
	# test 178.  /lib/modules resolves here through the symlink anyway.
	mkdir -p "$dest/usr/lib/modules"
	tmp=$dest/usr/lib/modules/.$release.gts9-tmp
	rm -rf "$tmp"
	cp -a "$src" "$tmp"
	rm -rf "$dest/usr/lib/modules/$release"
	mv "$tmp" "$dest/usr/lib/modules/$release"
	note "installed modules for $release"
}

install_firmware() {
	local dest=$1
	[ "$do_firmware" = 1 ] || { note 'firmware skipped'; return 0; }
	if [ ! -d "$firmware_root" ] || \
	   [ -z "$(find "$firmware_root" -type f -print -quit 2>/dev/null)" ]; then
		note "no firmware at $firmware_root; skipping"
		return 0
	fi
	# Same usr-merge rule as the modules above.
	mkdir -p "$dest/usr/lib/firmware"
	cp -a "$firmware_root"/. "$dest/usr/lib/firmware"/
	note 'installed firmware'
}

run_depmod() {
	local dest=$1 release
	[ "$do_modules" = 1 ] || return 0
	[ -d "$dest/usr/lib/modules" ] || return 0
	command -v "$depmod" >/dev/null 2>&1 || {
		note 'depmod is unavailable; module dependencies were not generated'
		return 0
	}
	for path in "$dest"/usr/lib/modules/*/; do
		release=$(basename "$path")
		if "$depmod" -b "$dest" "$release" 2>/dev/null; then
			note "generated module dependencies for $release"
		else
			note "WARNING: depmod -b $dest $release failed; Debian will not modprobe by alias"
		fi
	done
}

verify_usr_merge() {
	# verify_usr_merge DEST
	# Debian is usr-merged: /lib, /bin and /sbin are symlinks into /usr.  If one
	# of them is a real directory the layout is already broken and booting it
	# fails at execve(/sbin/init) with a kernel panic, so refuse to pretend the
	# install succeeded.  Fixtures without systemd are not a Debian rootfs and
	# are skipped.
	local dest=$1 link
	[ -e "$dest/usr/lib/systemd/systemd" ] || return 0
	for link in lib bin sbin; do
		if [ -e "$dest/$link" ] && [ ! -L "$dest/$link" ]; then
			fail "$dest/$link is a real directory, not a symlink into usr/: the rootfs is not usr-merged and /sbin/init would not resolve"
		fi
	done
	[ -x "$dest/usr/lib/systemd/systemd" ] || \
		fail "$dest/usr/lib/systemd/systemd is missing or not executable"
}

install_tree() {
	# install_tree DEST [enablement]
	# The tarball is built without the enablement symlinks: TWRP creates them
	# with gts9-enable-units after extracting, because busybox tar refuses to
	# replace an existing link that points outside the extraction root.
	local dest=$1 enablement=${2:-yes}
	[ -d "$dest" ] || fail "not a directory: $dest"
	copy_overlay "$dest"
	if [ "$enablement" = yes ]; then
		install_units_and_enablement "$dest"
	fi
	install_modules "$dest"
	install_firmware "$dest"
	run_depmod "$dest"
	verify_usr_merge "$dest"
}

if [ -n "$tar_file" ]; then
	command -v tar >/dev/null 2>&1 || fail 'tar is required'
	staging=$(mktemp -d)
	trap 'rm -rf "$staging"' EXIT
	install_tree "$staging" no
	mkdir -p "$(dirname "$tar_file")"
	# Regular files and relative paths only, and no symlink entries: TWRP's
	# busybox tar refuses to replace an existing symlink that resolves outside
	# the extraction root.  gts9-enable-units creates the links afterwards.
	tar --format=gnu --owner=0 --group=0 --numeric-owner \
		-C "$staging" -cpf "$tar_file" .
	note "overlay tarball: $tar_file"
	note "deploy with: adb push $tar_file /tmp/ && cd /mnt/debian && tar -xpf /tmp/${tar_file##*/} && sync"
	note "then enable the units: sh /mnt/debian/usr/libexec/gts9-enable-units /mnt/debian"
	exit 0
fi

resolved=$(readlink -f -- "$target" 2>/dev/null || echo "$target")
[ "$resolved" != "/" ] || fail 'refusing to install onto the running root filesystem'
[ -d "$target/etc/systemd" ] || fail "not a Debian root filesystem: $target"
if [ ! -f "$target/etc/os-release" ]; then
	note "WARNING: $target/etc/os-release is missing; is this really a Debian rootfs?"
fi

install_tree "$target"
note "installed the gts9 userspace into $target"
note 'review the units before rebooting: systemctl --root='"$target"' list-unit-files "gts9-*"'
