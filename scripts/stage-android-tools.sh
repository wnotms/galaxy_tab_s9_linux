#!/usr/bin/env bash
# Stage the AOSP boot-image tooling this port needs, into $GTS9_WORKDIR/tools.
#
# mkbootimg.py, unpack_bootimg.py and avbtool.py are AOSP tools (Apache-2.0)
# that distributions do not package.  They are not vendored in Git.
#
# Adapted from the SM-X910 reference port (ubuntu-galaxy-tab-s9-ultra,
# scripts/stage-android-tools.sh), which stages them out of a postmarketOS
# build chroot.  This repository has no such chroot, so they are downloaded
# from android.googlesource.com at pinned revisions and checked against pinned
# SHA-256 values: a silent upstream change fails here instead of producing a
# boot image nobody can reproduce.
#
# Staging writes only inside $GTS9_WORKDIR.  Nothing is flashed.
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
workdir=${GTS9_WORKDIR:-$repo_root/.work}
tools=${ANDROID_TOOLS:-$workdir/tools}

# Pinned upstream revisions (resolved 2026-09-21) and the SHA-256 of the files
# at those revisions.
mkbootimg_rev=d2bb0af5ba6d3198a3e99529c97eda1be0b5a093
avb_rev=761178607206f4cb2af79ed9eec52d8cbd814adb

mkbootimg_url=https://android.googlesource.com/platform/system/tools/mkbootimg
avb_url=https://android.googlesource.com/platform/external/avb

# Manifest: <source-url> <sha256> <destination-relative-path>
manifest=$(cat <<EOF
$mkbootimg_url/+/$mkbootimg_rev/mkbootimg.py 37d84b3d162e0bc62e36c1f4e1c63c85ea0caa9f29be023eb2f8efe006ad948c mkbootimg.py
$mkbootimg_url/+/$mkbootimg_rev/unpack_bootimg.py a9d260978a63bd06a24b6347e7dee8a28ff96639793caea15dff6aa491316308 unpack_bootimg.py
$mkbootimg_url/+/$mkbootimg_rev/gki/generate_gki_certificate.py 1bb1feec68a13da18d581aa2c631798f86f6bc10b55d587b2dd31446a0f8a203 gki/generate_gki_certificate.py
$mkbootimg_url/+/$mkbootimg_rev/gki/certify_bootimg.py e6cba3f8b543418a609f02bea7c334fe48343961be1f9d92c640b47a39486054 gki/certify_bootimg.py
$mkbootimg_url/+/$mkbootimg_rev/gki/boot_signature_info.sh 6ad303133495047a4008207a42fd39485b0cc6240d404fa3767cc3b7fb9a33a3 gki/boot_signature_info.sh
$avb_url/+/$avb_rev/avbtool.py e5a664a38db623da00f080219bc0ee60a640a9dc4a872803616fae4938ac749b avbtool.py
EOF
)

command -v curl >/dev/null || { echo 'curl is required to stage the AOSP tools' >&2; exit 1; }
command -v base64 >/dev/null || { echo 'base64 is required to stage the AOSP tools' >&2; exit 1; }

mkdir -p "$tools"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

printf '%s\n' "$manifest" | while read -r url sha dest; do
    [ -n "$url" ] || continue
    mkdir -p "$tools/$(dirname "$dest")" "$tmp/$(dirname "$dest")"
    echo "fetching $dest"
    # googlesource serves file contents base64-encoded when asked for TEXT.
    curl -fsS "$url?format=TEXT" | base64 -d > "$tmp/$dest"
    actual=$(sha256sum "$tmp/$dest" | cut -d' ' -f1)
    if [ "$actual" != "$sha" ]; then
        echo "SHA-256 mismatch for $dest" >&2
        echo "  expected $sha" >&2
        echo "  actual   $actual" >&2
        exit 1
    fi
    install -m 0755 "$tmp/$dest" "$tools/$dest"
done

( cd "$tools" && sha256sum mkbootimg.py unpack_bootimg.py avbtool.py \
    $(find gki -type f | sort) > SHA256SUMS )
cat "$tools/SHA256SUMS"

# Prove the tools run before a build depends on them: a missing Python module
# only shows up at import time, halfway through packaging.
for tool in mkbootimg unpack_bootimg avbtool; do
    if python3 "$tools/$tool.py" --help >/dev/null 2>&1; then
        echo "OK    $tool.py runs"
    else
        echo "FAIL  $tool.py does not run" >&2
        exit 1
    fi
done

echo
echo "Android tools staged in $tools"
echo "use them with:"
echo "  MKBOOTIMG=$tools/mkbootimg.py AVBTOOL=$tools/avbtool.py ./scripts/build-boot-bundle.sh ..."
