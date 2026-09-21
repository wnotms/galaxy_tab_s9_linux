#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
workdir=${GTS9_WORKDIR:-$repo_root/.work}
target=${KERNEL_SRC:-$workdir/linux-mainline}
tag=${LINUX_TAG:-v7.2-rc3}
commit=${LINUX_COMMIT:-a13c140cc289c0b7b3770bce5b3ad42ab35074aa}
upstream=${LINUX_REPO:-https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git}

mkdir -p "$workdir"

if [ ! -d "$target/.git" ]; then
    git clone --depth 1 --branch "$tag" "$upstream" "$target"
else
    echo "using existing upstream checkout: $target"
fi

head=$(git -C "$target" rev-parse HEAD)
if [ "$head" != "$commit" ]; then
    echo "error: $target is at $head, expected $commit ($tag)" >&2
    echo "remove the checkout or set KERNEL_SRC/LINUX_COMMIT deliberately" >&2
    exit 1
fi

echo "verified upstream Linux: $tag @ $head"
