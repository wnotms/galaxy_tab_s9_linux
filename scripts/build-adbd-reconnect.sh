#!/usr/bin/env bash
# Build only userspace adbd; never contact a device or change kernel artifacts.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
cache="$root/.work/downloads/adbd-reconnect-source"
output="$root/out/adbd-reconnect"
mkdir -p "$cache" "$output"
files=(
  'android-platform-tools_34.0.5-12.dsc 4eb852fd4d7499bc3e0c0d23686d423796f71f0df302f3606860fc66d52d70b0'
  'android-platform-tools_34.0.5.orig.tar.xz 4893f6a85b205f1df2c35cde5d6ca3bedd5e9f19afdb3b5ac781e647aa2243f4'
  'android-platform-tools_34.0.5-12.debian.tar.xz 3cc7d24e24c6b38f641f4ab13742ba86506aa6f15ce920c159c4ef8a1eefd722'
)
for entry in "${files[@]}"; do
  name=${entry%% *}; expected=${entry##* }
  if [ ! -f "$cache/$name" ] || [ "$(sha256sum "$cache/$name" | cut -d' ' -f1)" != "$expected" ]; then
    curl -fsSL --max-time 180 \
      "https://deb.debian.org/debian/pool/main/a/android-platform-tools/$name" \
      -o "$cache/$name.part"
    echo "$expected  $cache/$name.part" | sha256sum --check --status
    mv "$cache/$name.part" "$cache/$name"
  fi
done
job=$(mktemp -d "$root/.work/adbd-reconnect.XXXXXX")
# HTTPS source checksums are pinned above. No OpenPGP-signature claim is made.
dpkg-source --no-check -x "$cache/android-platform-tools_34.0.5-12.dsc" "$job/source"
patch --directory="$job/source" -p1 < "$root/userspace/adbd/0001-linux-functionfs-reconnect.patch"
docker build -t gts9-adbd-reconnect-builder:34.0.5-12 \
  -f "$root/userspace/adbd/Dockerfile" "$root/userspace/adbd"
docker run --rm --user "$(id -u):$(id -g)" \
  -v "$job/source:/source" -v "$output:/output" \
  -v "$root/userspace/adbd/build-in-container.sh:/build-script:ro" \
  gts9-adbd-reconnect-builder:34.0.5-12 sh /build-script
python3 - "$root" "$job" <<'PY'
import hashlib, json, pathlib, subprocess, sys
root, job = map(pathlib.Path, sys.argv[1:])
out = root / 'out/adbd-reconnect'
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
manifest = dict(source_version='34.0.5-12', architecture='arm64', kernel_changes=False,
    patch_sha256=sha(root/'userspace/adbd/0001-linux-functionfs-reconnect.patch'),
    binary_sha256=sha(out/'gts9-adbd-reconnect'),
    source_files={name: sha(job/'source/packages/modules/adb/daemon'/name)
                  for name in ('usb.cpp','usb_ffs.cpp')},
    builder_image=subprocess.check_output(['docker','image','inspect',
        'gts9-adbd-reconnect-builder:34.0.5-12','--format','{{.Id}}']).decode().strip())
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
PY
