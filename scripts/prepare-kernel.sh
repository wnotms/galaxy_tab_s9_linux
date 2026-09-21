#!/usr/bin/env bash
set -euo pipefail

tree=${1:?usage: prepare-kernel.sh LINUX_WORKTREE}
repo_root=$(cd "$(dirname "$0")/.." && pwd)
dts_src="$repo_root/kernel/dts/sm8550-samsung-gts9wifi.dts"
patch_dir="$repo_root/kernel/patches"

git -C "$tree" rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
    echo "not a git worktree: $tree" >&2
    exit 1
}
[ -f "$dts_src" ] || { echo "missing board DTS: $dts_src" >&2; exit 1; }

shopt -s nullglob
for patch in "$patch_dir"/*.patch; do
    if git -C "$tree" apply --reverse --check "$patch" >/dev/null 2>&1; then
        echo "already applied: ${patch##*/}"
        continue
    fi

    echo "applying ${patch##*/}"
    git -C "$tree" apply --check "$patch"
    git -C "$tree" apply "$patch"
done
shopt -u nullglob

qcom_dts="$tree/arch/arm64/boot/dts/qcom"
install -m 0644 "$dts_src" "$qcom_dts/sm8550-samsung-gts9wifi.dts"

makefile="$qcom_dts/Makefile"
if ! grep -q 'sm8550-samsung-gts9wifi\.dtb' "$makefile"; then
    printf '\ndtb-$(CONFIG_ARCH_QCOM) += sm8550-samsung-gts9wifi.dtb\n' >> "$makefile"
fi
if ! grep -q '^DTC_FLAGS_sm8550-samsung-gts9wifi := -@$' "$makefile"; then
    printf 'DTC_FLAGS_sm8550-samsung-gts9wifi := -@\n' >> "$makefile"
fi

echo "prepared SM-X710 source overlay: $tree"
