#!/usr/bin/env bash
# Install the gts9 Debian userspace on a mounted Debian root filesystem, or
# build the same tree as a tarball that TWRP can extract offline.
#
# Direct install (host, with the card mounted).  --ssh-key is how a rootfs gets
# its login now that the serial console is gone:
#
#	sudo ./scripts/install-debian-rootfs.sh --ssh-key ~/.ssh/id_ed25519.pub /mnt/debian
#
# Offline deploy through TWRP (recommended: the tablet's recovery has no repo).
# A key can be delivered this way too, because the tarball is written --owner=0
# and root is who this project connects as:
#
#	./scripts/install-debian-rootfs.sh --tar out/gts9-debian-overlay.tar \
#	    --ssh-key ~/.ssh/id_ed25519.pub
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
#   * the freestanding C helpers in usr/libexec/*.c compiled for aarch64
#   * enablement symlinks created by usr/libexec/gts9-enable-units from each
#     unit's own WantedBy= (no systemctl needed, works in TWRP)
#   * kernel modules under lib/modules/<release> plus a basedir depmod
#   * firmware under lib/firmware/
#   * optionally an ssh public key for root, with --ssh-key
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
# root's ssh public key, installed into the target's authorized_keys.  This is
# the only way to give a fresh rootfs a key now: the serial console that
# `gts9-debug-channel.sh install-key` used is gone (see
# docs/FAST_DEBUG_CHANNEL.md), so without this option a newly installed rootfs
# can only be reached through TWRP or a password login.
ssh_key=${GTS9_SSH_KEY_FILE:-}
# Which account on the target receives it.  Root, because that is who the rest of
# this project connects as (scripts/gts9-ssh.sh defaults to GTS9_SSH_USER=root).
ssh_key_user=${GTS9_SSH_KEY_USER:-root}
# Toolchain used for the freestanding overlay helpers; overridable so tests
# (and hosts without clang) can exercise the "no toolchain" path.
cc=${GTS9_CC:-clang}
linker=${GTS9_LD:-ld.lld}

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
	--ssh-key) ssh_key=${2:?--ssh-key needs a .pub file}; shift 2 ;;
	--ssh-key-user) ssh_key_user=${2:?--ssh-key-user needs a name}; shift 2 ;;
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

build_native_helpers() {
	# The overlay ships a few freestanding C helpers for the tablet; they are
	# compiled here so the repository stores sources, never prebuilt binaries.
	# Missing toolchain is a warning: everything except those helpers still
	# gets installed.
	local dest=$1 source name output
	local built=0
	for source in "$dest"/usr/libexec/*.c; do
		[ -f "$source" ] || continue
		name=${source##*/}
		output=${source%.c}
		if ! command -v "$cc" >/dev/null 2>&1 || ! command -v "$linker" >/dev/null 2>&1; then
			note "WARNING: clang/ld.lld missing; $name was not built"
			rm -f "$source"
			continue
		fi
		if ! "$cc" --target=aarch64-linux-gnu -nostdlib -static -ffreestanding \
		     -fno-stack-protector -fno-builtin -fuse-ld=lld \
		     -Wl,--build-id=none -Wl,-n -o "$output" "$source"; then
			fail "cannot build $name"
		fi
		if readelf -l "$output" 2>/dev/null | grep -q INTERP; then
			fail "$name is dynamically linked"
		fi
		chmod 0755 "$output"
		# Only the binary belongs on the Debian root filesystem.
		rm -f "$source"
		built=$((built + 1))
	done
	if [ "$built" -gt 0 ]; then
		note "built $built native helper(s) for the tablet"
	fi
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

install_ssh_key() {
	# install_ssh_key DEST
	#
	# Put an ssh public key into the target's authorized_keys for $ssh_key_user.
	#
	# Why this exists at all: `scripts/gts9-debug-channel.sh install-key` used to
	# write the key over the COM17 serial console, and that console is gone -
	# the autologin getty was deleted and the ttyGS kernel console removed, both
	# because they caused the boot and shutdown stalls (docs/BOOT_CONSOLE_BLOCK.md,
	# docs/SHUTDOWN_DELAY.md).  Writing the key into the rootfs before it ever
	# boots needs no channel on the device at all, which is the whole point: it
	# is the route the Fedora port for this board takes too
	# (rootfs/build-rootfs.sh: `install -Dm600 -o 1000 -g 1000 …authorized_keys`).
	#
	# Every failure here is fatal rather than a warning.  A rootfs that boots
	# without its key is reachable only through TWRP, and that is exactly the
	# situation this option exists to prevent - so a silent skip would be worse
	# than refusing to install.
	local dest=$1
	[ -n "$ssh_key" ] || return 0

	[ -f "$ssh_key" ] || fail "no such public key: $ssh_key"

	# Validate before writing anything.  A private key pasted by mistake, or a
	# truncated download, would otherwise be installed as an authorized key and
	# silently never authenticate, which is indistinguishable from "ssh is
	# broken" on the device.
	if ! grep -qE '^(ssh-(rsa|ed25519|dss)|ecdsa-sha2-[^ ]+|sk-(ssh-ed25519|ecdsa-sha2-[^ ]+)@openssh\.com)[[:space:]]+[A-Za-z0-9+/=]+' "$ssh_key"; then
		fail "$ssh_key is not an OpenSSH public key (expected 'ssh-ed25519 AAAA…' or similar)"
	fi
	if grep -q 'PRIVATE KEY' "$ssh_key"; then
		fail "$ssh_key contains a PRIVATE KEY: install the .pub file, never the private one"
	fi
	# One key per line, and no line that is not a key: an authorized_keys file
	# with a stray line is a file sshd reads partially or refuses.
	local line bad=0
	while IFS= read -r line || [ -n "$line" ]; do
		case "$line" in
		'' | '#'*) continue ;;
		esac
		printf '%s\n' "$line" | grep -qE '^(ssh-(rsa|ed25519|dss)|ecdsa-sha2-[^ ]+|sk-(ssh-ed25519|ecdsa-sha2-[^ ]+)@openssh\.com)[[:space:]]+[A-Za-z0-9+/=]+' || bad=1
	done <"$ssh_key"
	[ "$bad" = 0 ] || fail "$ssh_key has a line that is not an ssh public key"

	local home
	case "$ssh_key_user" in
	root) home=$dest/root ;;
	*) home=$dest/home/$ssh_key_user ;;
	esac
	[ -d "$(dirname "$home")" ] || fail "no home directory for '$ssh_key_user' in the target ($home)"

	local ssh_dir=$home/.ssh
	local auth=$ssh_dir/authorized_keys
	mkdir -p "$ssh_dir" || fail "cannot create $ssh_dir"

	# Idempotent, and it merges rather than replaces: this script is re-run over
	# an existing rootfs, and clobbering the file would drop keys an operator had
	# added deliberately.  `install -m` sets the mode on the new file; the
	# existing content is preserved by appending only keys that are not present.
	touch "$auth" || fail "cannot create $auth"
	while IFS= read -r line || [ -n "$line" ]; do
		case "$line" in
		'' | '#'*) continue ;;
		esac
		if ! grep -qxF "$line" "$auth" 2>/dev/null; then
			printf '%s\n' "$line" >>"$auth" || fail "cannot append to $auth"
			note "added a public key to $auth"
		fi
	done <"$ssh_key"

	# sshd refuses to use authorized_keys that is group- or world-writable, and
	# requires the directory to be private too.  Ownership matters for the same
	# reason: with StrictModes on (the default) a file owned by another user is
	# ignored.
	chmod 0700 "$ssh_dir" || fail "cannot chmod 0700 $ssh_dir"
	chmod 0600 "$auth" || fail "cannot chmod 0600 $auth"
	if [ "$(id -u)" = 0 ]; then
		local uid gid
		case "$ssh_key_user" in
		root) uid=0; gid=0 ;;
		*)
			uid=$(awk -F: -v u="$ssh_key_user" '$1 == u {print $3}' "$dest/etc/passwd" 2>/dev/null)
			gid=$(awk -F: -v u="$ssh_key_user" '$1 == u {print $4}' "$dest/etc/passwd" 2>/dev/null)
			;;
		esac
		if [ -n "${uid:-}" ] && [ -n "${gid:-}" ]; then
			chown "$uid:$gid" "$ssh_dir" "$auth" 2>/dev/null || \
				note "WARNING: could not chown $auth to $uid:$gid"
		else
			note "WARNING: no passwd entry for '$ssh_key_user'; left ownership as-is"
		fi
	else
		# Not root: the files may come out owned by the invoking user, which
		# sshd's StrictModes will reject.  Say so rather than let it fail on the
		# device with no explanation.
		note "WARNING: not running as root; $auth may not be owned by $ssh_key_user, which sshd rejects (StrictModes)"
	fi

	note "installed $(grep -c . "$auth" 2>/dev/null || echo 0) key(s) in $auth"
	[ "$(grep -c . "$auth" 2>/dev/null || echo 0)" -gt 0 ] || \
		fail "$auth is empty after installing $ssh_key"
}

install_tree() {
	# install_tree DEST [enablement]
	# The tarball is built without the enablement symlinks: TWRP creates them
	# with gts9-enable-units after extracting, because busybox tar refuses to
	# replace an existing link that points outside the extraction root.
	local dest=$1 enablement=${2:-yes}
	[ -d "$dest" ] || fail "not a directory: $dest"
	copy_overlay "$dest"
	build_native_helpers "$dest"
	if [ "$enablement" = yes ]; then
		install_units_and_enablement "$dest"
	fi
	install_modules "$dest"
	install_firmware "$dest"
	run_depmod "$dest"
	verify_usr_merge "$dest"
	install_ssh_key "$dest"
}

if [ -n "$tar_file" ]; then
	command -v tar >/dev/null 2>&1 || fail 'tar is required'
	# The tarball is written with --owner=0 --group=0, so everything it contains
	# becomes root:root on extraction.  sshd's StrictModes ignores an
	# authorized_keys owned by anyone but the account it belongs to, so a key for
	# a non-root user cannot be delivered this way - refuse rather than ship a
	# tarball whose key silently will not authenticate.
	if [ -n "$ssh_key" ] && [ "$ssh_key_user" != root ]; then
		fail "--ssh-key-user $ssh_key_user cannot be used with --tar: the tarball is written --owner=0, so the key would be owned by root and rejected by sshd (StrictModes). Install directly to the mounted rootfs instead, or use root."
	fi
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
