#!/usr/bin/env bash
# Build only an external diagnostic module against the sealed Test272 provider.
# No production Kconfig/DT/archive edit, device connection or install.
set -euo pipefail
repo_root=$(cd "$(dirname "$0")/.." && pwd)
observer_stage="$repo_root/.work/build/sm5440-fresh-observer"
observer_out="$repo_root/out/sm5440-fresh-observer"
provider_tree="$repo_root/.work/build/linux-src-x710-charging"
provider_build="$repo_root/.work/build/linux-out-x710-272-passive"
python3 - "$repo_root" "$provider_tree" "$provider_build" <<'PY'
import hashlib,json,subprocess,sys
from pathlib import Path
root,tree,build=map(Path,sys.argv[1:])
manifest=json.loads((root/'reference/boot-tests/test-272-sm5440-fresh-request-offline/ARTIFACTS.json').read_text())
for item in manifest.values():
    p=root/item['path']
    if hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']:
        raise SystemExit('sealed Test272 artifact changed: '+str(p))
if (build/'.config').read_bytes()!=(root/manifest['config']['path']).read_bytes():
    raise SystemExit('provider resolved config changed')
for name in ('sm5440-direct.c','sm5440-hw.h'):
    frozen=subprocess.check_output(['git','-C',str(root),'show','399eb497:kernel/drivers/'+name])
    if (root/'kernel/drivers'/name).read_bytes()!=frozen:
        raise SystemExit('source no longer matches sealed Test272 provider: '+name)
    if (root/'kernel/drivers'/name).read_bytes()!=(tree/'drivers/power/supply'/name).read_bytes():
        raise SystemExit('provider overlay changed: '+name)
sym=(build/'Module.symvers').read_text().splitlines()
if not any('\tsm5440_passive_request_fresh\tvmlinux\tEXPORT_SYMBOL_GPL' in line for line in sym):
    raise SystemExit('provider lacks fresh acquisition symbol; do not force-load on Test263')
PY
mkdir -p "$observer_stage/include" "$observer_out"
cp "$repo_root/kernel/diagnostics/sm5440-fresh-observer/Makefile" "$observer_stage/Makefile"
cp "$repo_root/kernel/diagnostics/sm5440-fresh-observer/sm5440-fresh-observer.c" "$observer_stage/"
cp "$repo_root/kernel/drivers/sm5440-hw.h" "$observer_stage/include/"
export CCACHE_DIR="$repo_root/.work/ccache"
export CCACHE_BASEDIR="$repo_root/.work"
make -C "$provider_tree" O="$provider_build" ARCH=arm64 LLVM=1 CC="ccache clang" \
    W=1 -j8 M="$observer_stage" modules
cp "$observer_stage/sm5440-fresh-observer.ko" "$observer_out/"
echo "External observer only: $observer_out/sm5440-fresh-observer.ko (not installed)"
