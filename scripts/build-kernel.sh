#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
workdir=${GTS9_WORKDIR:-$repo_root/.work}
kernel_src=${KERNEL_SRC:-$workdir/linux-mainline}
kernel_tree=${KERNEL_WORKTREE:-$workdir/build/linux-src-gts9wifi}
build_dir=${KERNEL_BUILD_DIR:-$workdir/build/linux-out}
out_dir=${KERNEL_OUT_DIR:-$repo_root/out/kernel-gts9wifi}
fragment="$repo_root/kernel/config/gts9wifi-mainline.fragment"
jobs=${JOBS:-$(nproc)}
build_modules=${BUILD_MODULES:-1}

case "$build_modules" in 0|1) ;; *) echo "BUILD_MODULES must be 0 or 1" >&2; exit 2 ;; esac

"$repo_root/scripts/fetch-mainline.sh"

if [ "${KERNEL_CLEAN:-0}" = 1 ]; then
    echo "clean build requested"
    rm -rf -- "$build_dir" "$out_dir"
    if [ -e "$kernel_tree/.git" ]; then
        git -C "$kernel_src" worktree remove --force "$kernel_tree" || true
        git -C "$kernel_src" worktree prune
    else
        rm -rf -- "$kernel_tree"
    fi
fi

mkdir -p "$(dirname "$kernel_tree")" "$build_dir" "$out_dir"

if [ ! -e "$kernel_tree/.git" ]; then
    git -C "$kernel_src" worktree add --detach "$kernel_tree" HEAD
fi

bash "$repo_root/scripts/prepare-kernel.sh" "$kernel_tree"

# Keep all generated Kconfig state in O=. The source worktree must contain only
# deliberate DTS/patch changes, otherwise Kbuild rejects the out-of-tree build.
stock_cfg="$build_dir/SM-X710-stock-5.15.153.config"
"$repo_root/scripts/materialize-stock-config.sh" "$stock_cfg"
"$kernel_tree/scripts/kconfig/merge_config.sh" -m -O "$build_dir" \
    "$stock_cfg" "$fragment"
make -C "$kernel_tree" O="$build_dir" ARCH=arm64 LLVM=1 olddefconfig

required=(
    CONFIG_ARCH_QCOM CONFIG_SERIAL_QCOM_GENI CONFIG_SERIAL_QCOM_GENI_CONSOLE
    CONFIG_BLK_DEV_INITRD CONFIG_DEVTMPFS CONFIG_SCSI_UFS_QCOM
    CONFIG_MMC_SDHCI_MSM CONFIG_EXT4_FS CONFIG_PSTORE CONFIG_PSTORE_RAM
)
for sym in "${required[@]}"; do
    if ! grep -qx "$sym=y" "$build_dir/.config"; then
        echo "required Kconfig symbol is not built-in: $sym" >&2
        exit 1
    fi
done

export KBUILD_BUILD_USER=${KBUILD_BUILD_USER:-gts9-mainline}
export KBUILD_BUILD_HOST=${KBUILD_BUILD_HOST:-reproducible}
export SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-$(git -C "$kernel_src" log -1 --format=%ct)}
export KBUILD_BUILD_TIMESTAMP=${KBUILD_BUILD_TIMESTAMP:-$(LC_ALL=C date -u -d "@$SOURCE_DATE_EPOCH")}
printf '0\n' > "$build_dir/.version"

make_targets=(Image.gz qcom/sm8550-samsung-gts9wifi.dtb)
if [ "$build_modules" = 1 ]; then
    make_targets+=(modules)
fi

make -C "$kernel_tree" O="$build_dir" ARCH=arm64 LLVM=1 -j"$jobs" "${make_targets[@]}"

release=$(make -s -C "$kernel_tree" O="$build_dir" ARCH=arm64 LLVM=1 kernelrelease)

install -m 0644 "$build_dir/arch/arm64/boot/Image.gz" "$out_dir/Image.gz"
install -m 0644 \
    "$build_dir/arch/arm64/boot/dts/qcom/sm8550-samsung-gts9wifi.dtb" \
    "$out_dir/sm8550-samsung-gts9wifi.dtb"
install -m 0644 "$build_dir/.config" "$out_dir/config"
printf '%s\n' "$release" > "$out_dir/kernel.release"

if [ "$build_modules" = 1 ]; then
    modules_root="$out_dir/modules-root"
    rm -rf -- "$modules_root"
    make -C "$kernel_tree" O="$build_dir" ARCH=arm64 LLVM=1 \
        INSTALL_MOD_PATH="$modules_root" modules_install
fi

(
    cd "$out_dir"
    sha256sum Image.gz sm8550-samsung-gts9wifi.dtb config > SHA256SUMS
)

cat <<EOF2

Build complete
  release: $release
  output : $out_dir

$(cat "$out_dir/SHA256SUMS")
EOF2
