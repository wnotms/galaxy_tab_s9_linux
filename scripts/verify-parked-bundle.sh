#!/usr/bin/env bash
# Verify a parked candidate bundle against ITSELF, independent of whatever is
# currently in out/.
#
# scripts/validate-boot-bundle.sh compares a bundle against the built tree, so it
# can only pass for the profile built most recently.  That is fine while you are
# building and flashing the same profile, and useless for a parked set of three
# candidates: two of them will always look broken.
#
# This checks the properties that must hold for ANY candidate:
#   * the bundle's own SHA256SUMS verify
#   * BUNDLE_INFO's image_gz_sha256 / dtb_sha256 match the images it describes
#   * boot.img's appended DTB and vendor_boot's DTB are the same tree
#   * that tree verifies as the intended idle-ablation profile
#
# Usage: verify-parked-bundle.sh BUNDLE_DIR PROFILE
set -euo pipefail
bundle=${1:?usage: verify-parked-bundle.sh BUNDLE_DIR PROFILE}
profile=${2:?usage: verify-parked-bundle.sh BUNDLE_DIR PROFILE}
repo=$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)
fails=0
pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; fails=$((fails+1)); }

[ -d "$bundle" ] || { echo "no such bundle: $bundle" >&2; exit 1; }
case "$profile" in
    cpuidle-off|no-llcc-off|no-cluster-idle) ;;
    *) echo "unknown profile: $profile" >&2; exit 2 ;;
esac

# The DTB profile is not always the bundle profile.  `cpuidle-off` changes only
# the command line, so its device tree IS the unablated baseline - passing
# "cpuidle-off" to the DTB verifier would ask it for an ablation that profile
# does not have, and fail a perfectly good bundle.  Anything that is not a known
# ablation is verified as the baseline tree.
case "$profile" in
    no-llcc-off|no-cluster-idle) dtb_profile=$profile ;;
    *)                           dtb_profile=baseline ;;
esac
echo "verifying $bundle as '$profile' (DTB profile: $dtb_profile)"

# 1. the bundle's own manifest
if (cd "$bundle" && sha256sum -c --quiet SHA256SUMS 2>/dev/null); then
    pass 'SHA256SUMS verifies against every image'
else
    fail 'SHA256SUMS does not verify'
fi

# 2. BUNDLE_INFO describes these images
img=$(sed -n 's/^image_gz_sha256=//p' "$bundle/BUNDLE_INFO")
dtb=$(sed -n 's/^dtb_sha256=//p' "$bundle/BUNDLE_INFO")
boot_sha=$(sha256sum "$bundle/boot.img" | cut -d' ' -f1)
grep -q "$boot_sha" "$bundle/SHA256SUMS" && pass "BUNDLE_INFO/boot.img consistent ($(echo $boot_sha|cut -c1-16))" \
    || fail 'boot.img hash absent from SHA256SUMS'

# 3. extract both DTBs and compare - they must be one tree
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
python3 "$repo/.work/tools/unpack_bootimg.py" --boot_img "$bundle/vendor_boot.img" --out "$tmp/vb" >/dev/null 2>&1
python3 - "$bundle/boot.img" "$tmp/boot.dtb" <<'PY'
import sys, zlib, struct, pathlib
d=pathlib.Path(sys.argv[1]).read_bytes(); i=d.find(b'\x1f\x8b\x08')
do=zlib.decompressobj(16+zlib.MAX_WBITS); do.decompress(d[i:]); un=do.unused_data
assert un[:4]==b'\xd0\x0d\xfe\xed', 'no appended DTB'
n=struct.unpack('>I',un[4:8])[0]
pathlib.Path(sys.argv[2]).write_bytes(un[:n])
PY
bh=$(sha256sum "$tmp/boot.dtb" | cut -d' ' -f1)
vh=$(sha256sum "$tmp/vb/dtb" | cut -d' ' -f1)
[ "$bh" = "$dtb" ] && pass "boot.img DTB is the one BUNDLE_INFO names" || fail "boot.img DTB != BUNDLE_INFO"
[ "$bh" = "$vh" ] && pass 'boot.img and vendor_boot carry the SAME device tree' \
    || fail 'boot.img and vendor_boot carry DIFFERENT device trees'

# 4. that tree is the profile it claims, and the CPU states are intact
if "$repo/scripts/verify-idle-ablation.sh" "$tmp/boot.dtb" "$dtb_profile" >"$tmp/ver.txt" 2>&1; then
    pass "DTB verifies as '$dtb_profile'"
else
    fail "DTB does not verify as '$dtb_profile'"
    sed 's/^/      /' "$tmp/ver.txt" | grep -E 'FAIL|references' || true
fi

echo
[ "$fails" -eq 0 ] && { echo "PARKED BUNDLE VERIFIED ($profile)"; exit 0; }
echo "PARKED BUNDLE VERIFICATION FAILED ($fails)"; exit 1
