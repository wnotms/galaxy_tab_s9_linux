#!/usr/bin/env bash
# Build only an external diagnostic module against the sealed Test290 provider.
# No production Kconfig/DT/archive edit, device connection or install.
set -euo pipefail
repo_root=$(cd "$(dirname "$0")/.." && pwd)
observer_stage="$repo_root/.work/build/sm5440-passive-observer"
observer_out=${OBSERVER_OUT_DIR:-$repo_root/out/sm5440-passive-observer}
provider_tree="$repo_root/.work/build/linux-src-x710-charging"
provider_build="$repo_root/.work/build/linux-out-x710-290-passive"
python3 - "$repo_root" "$provider_tree" "$provider_build" <<'PY'
import hashlib,json,subprocess,sys,tempfile
from pathlib import Path
root,tree,build=map(Path,sys.argv[1:])
manifest=json.loads((root/'reference/boot-tests/test-290-passive-observation-api/ARTIFACTS.json').read_text())
for item in manifest.values():
    p=root/item['path']
    if hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']:
        raise SystemExit('sealed Test290 artifact changed: '+str(p))
if (build/'.config').read_bytes()!=(root/manifest['config']['path']).read_bytes():
    raise SystemExit('provider resolved config changed')
for name in ('sm5440-direct.c','sm5440-hw.h'):
    frozen=subprocess.check_output(['git','-C',str(root),'show','8e890215:kernel/drivers/'+name])
    if (root/'kernel/drivers'/name).read_bytes()!=frozen:
        raise SystemExit('source no longer matches sealed Test290 provider: '+name)
    if (root/'kernel/drivers'/name).read_bytes()!=(tree/'drivers/power/supply'/name).read_bytes():
        raise SystemExit('provider overlay changed: '+name)
with tempfile.TemporaryDirectory() as tmp:
    notes=Path(tmp)/'notes'
    subprocess.run(['llvm-objcopy','--dump-section',f'.notes={notes}',str(build/'vmlinux'),'/dev/null'],check=True)
    if hashlib.sha256(notes.read_bytes()).hexdigest()!=manifest['kernel-notes.bin']['sha256']:
        raise SystemExit('provider ELF notes do not match sealed Test290 image')
sym=(build/'Module.symvers').read_text().splitlines()
if not any('\tsm5440_passive_observe\tvmlinux\tEXPORT_SYMBOL_GPL' in line for line in sym):
    raise SystemExit('provider lacks passive observation symbol; do not force-load on Test263')
PY
mkdir -p "$observer_stage/include" "$observer_out"
cp "$repo_root/kernel/diagnostics/sm5440-passive-observer/Makefile" "$observer_stage/Makefile"
cp "$repo_root/kernel/diagnostics/sm5440-passive-observer/sm5440-passive-observer.c" "$observer_stage/"
cp "$repo_root/kernel/drivers/sm5440-hw.h" "$observer_stage/include/"
export CCACHE_DIR="$repo_root/.work/ccache"
export CCACHE_BASEDIR="$repo_root/.work"
make -C "$provider_tree" O="$provider_build" ARCH=arm64 LLVM=1 CC="ccache clang" \
    W=1 -j8 M="$observer_stage" modules
cp "$observer_stage/sm5440-passive-observer.ko" "$observer_out/"
echo "External observer only: $observer_out/sm5440-passive-observer.ko (not installed)"
