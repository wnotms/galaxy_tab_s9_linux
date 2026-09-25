#!/usr/bin/env bash
# Fetch the Debian packages that provide adbd for the tablet, with pinned hashes.
#
# Why these six.  `adbd 34.0.5-12` is the build in Debian *trixie*, which is the
# release the tablet runs (13.7), so it is built against the same glibc.  Five of
# its dependencies are absent from the minimal rootfs and are not pulled in by
# anything else: libprotobuf32t64 and the four android-* libraries.  The rest of
# its dependency list (libc6, libstdc++6, libsystemd0, libzstd1, liblz4-1,
# libbrotli1, libgcc-s1) is already installed.
#
# The .debs are NOT committed - they are binaries, and the pins below make them
# reproducible.  They land in .work/downloads/adbd-trixie/, which is gitignored.
#
#   scripts/fetch-adbd-packages.sh          # download and verify
#   scripts/fetch-adbd-packages.sh --check  # verify what is already here
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
dest=${ADBD_DEST:-$repo_root/.work/downloads/adbd-trixie}
base=${ADBD_BASE_URL:-http://deb.debian.org/debian/pool/main}

# path sha256 filename - sha256 first so a truncated download cannot be mistaken
# for a good one, and the path is spelled out rather than assembled so a typo in a
# package name is a review failure and not a silent 404.
packages=(
	"a/android-platform-tools/adbd_34.0.5-12_arm64.deb
c8d2cb679fb6b0d508181310f7fb0e6ce4e713376ac123b9c47f1be58112ce6c"
	"a/android-platform-tools/android-libbase_34.0.5-12_arm64.deb
1b1460faa12cf04611cb58ff02808608fd2e3be642b72752a189c4ab84112a20"
	"a/android-platform-tools/android-libcutils_34.0.5-12_arm64.deb
683ec66783e0d54e91bee661af7f758528b2c85163d585ae936d1cfd5bf8d661"
	"a/android-platform-tools/android-liblog_34.0.5-12_arm64.deb
7ce80b00c4592d0021ce2973d922f1c014fbbe33a289690732dfb556bfbbec96"
	"a/android-platform-external-boringssl/android-libboringssl_14.0.0+r45-2_arm64.deb
6dd20f2d7ad3cdff7c80d8076feea6258c8e9f0a0a23ad85d447eeb3e7f11c36"
	"p/protobuf/libprotobuf32t64_3.21.12-11+deb13u1_arm64.deb
51bf38fcca667be0deef732a903563ee6ffa9bfc04433310c2c49e4c92d06b09"
)

check_only=0
[ "${1:-}" = "--check" ] && check_only=1

mkdir -p "$dest"
fail=0
for entry in "${packages[@]}"; do
	path=${entry%%$'\n'*}
	want=${entry##*$'\n'}
	file=${path##*/}
	have=""
	[ -f "$dest/$file" ] && have=$(sha256sum "$dest/$file" | cut -d' ' -f1)

	if [ "$have" = "$want" ]; then
		echo "ok      $file"
		continue
	fi
	if [ "$check_only" = "1" ]; then
		echo "MISSING $file (want $want)" >&2
		fail=1
		continue
	fi

	echo "fetch   $file"
	if ! curl -fsSL -o "$dest/$file.part" "$base/$path"; then
		echo "FAILED to download $file" >&2
		rm -f "$dest/$file.part"
		fail=1
		continue
	fi
	got=$(sha256sum "$dest/$file.part" | cut -d' ' -f1)
	if [ "$got" != "$want" ]; then
		echo "SHA256 MISMATCH for $file: got $got, want $want" >&2
		rm -f "$dest/$file.part"
		fail=1
		continue
	fi
	mv "$dest/$file.part" "$dest/$file"
done

if [ "$fail" != "0" ]; then
	echo "fetch-adbd-packages: some packages are missing or wrong" >&2
	exit 1
fi
echo "fetch-adbd-packages: ${#packages[@]} package(s) verified in $dest"
