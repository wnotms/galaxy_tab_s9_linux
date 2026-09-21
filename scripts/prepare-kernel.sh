#!/usr/bin/env bash
set -euo pipefail

tree=${1:?usage: prepare-kernel.sh LINUX_WORKTREE}
repo_root=$(cd "$(dirname "$0")/.." && pwd)
dts_src="$repo_root/kernel/dts/sm8550-samsung-gts9wifi.dts"
fragment="$repo_root/kernel/config/gts9wifi-mainline.fragment"
patch_dir="$repo_root/kernel/patches"
stock_cfg="$tree/.config.stock"

[ -d "$tree/.git" ] || { echo "not a git worktree: $tree" >&2; exit 1; }
[ -f "$dts_src" ] || { echo "missing board DTS: $dts_src" >&2; exit 1; }
[ -f "$fragment" ] || { echo "missing config fragment: $fragment" >&2; exit 1; }

shopt -s nullglob
for patch in "$patch_dir"/*.patch; do
    echo "applying ${patch##*/}"
    git -C "$tree" apply --check "$patch"
    git -C "$tree" apply "$patch"
done
shopt -u nullglob

qcom_dts="$tree/arch/arm64/boot/dts/qcom"
install -m 0644 "$dts_src" "$qcom_dts/sm8550-samsung-gts9wifi.dts"

makefile="$qcom_dts/Makefile"
if ! grep -q 'sm8550-samsung-gts9wifi\\.dtb' "$makefile"; then
    printf '\\ndtb-$(CONFIG_ARCH_QCOM) += sm8550-samsung-gts9wifi.dtb\\n' >> "$makefile"
fi
if ! grep -q '^DTC_FLAGS_sm8550-samsung-gts9wifi := -@$' "$makefile"; then
    printf 'DTC_FLAGS_sm8550-samsung-gts9wifi := -@\\n' >> "$makefile"
fi

# Preserve the owner-extracted Samsung 5.15.153 config as the explicit seed.
# Linux 7.2 olddefconfig is allowed to discard obsolete downstream-only symbols,
# while the small mainline fragment below forces/records the upstream settings
# the port actually depends on.
"$repo_root/scripts/materialize-stock-config.sh" "$stock_cfg"
"$tree/scripts/kconfig/merge_config.sh" -m -O "$tree" "$stock_cfg" "$fragment"
make -C "$tree" ARCH=arm64 LLVM=1 olddefconfig

required=(
    CONFIG_ARCH_QCOM CONFIG_SERIAL_QCOM_GENI CONFIG_SERIAL_QCOM_GENI_CONSOLE
    CONFIG_BLK_DEV_INITRD CONFIG_DEVTMPFS CONFIG_SCSI_UFS_QCOM
    CONFIG_MMC_SDHCI_MSM CONFIG_EXT4_FS CONFIG_PSTORE CONFIG_PSTORE_RAM
)
for sym in "${required[@]}"; do
    if ! grep -qx "$sym=y" "$tree/.config"; then
        echo "required Kconfig symbol is not built-in: $sym" >&2
        exit 1
    fi
done

echo "prepared SM-X710 mainline tree from verified stock config seed: $tree"
