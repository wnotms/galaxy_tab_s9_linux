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

# A patch that is dropped from the queue is *not* reverted by git apply, so a
# reused worktree silently keeps building it.  Refuse to continue when tracked
# files are modified that no queued patch claims - the DTS install and the
# Makefile edits below are deliberate and happen after this check.
shopt -s nullglob
queued=("$patch_dir"/*.patch)
shopt -u nullglob
unaccounted=
while read -r changed; do
    [ -n "$changed" ] || continue
    # Files this script maintains below (the DTB registration) are expected.
    case "$changed" in
        arch/arm64/boot/dts/qcom/Makefile) continue ;;
    esac
    claimed=false
    for patch in "${queued[@]}"; do
        if grep -q "^+++ b/$changed\$" "$patch"; then
            claimed=true
            break
        fi
    done
    [ "$claimed" = true ] || unaccounted="$unaccounted $changed"
done < <(git -C "$tree" diff --name-only)

if [ -n "$unaccounted" ]; then
    echo "refusing to build: the worktree carries changes no queued patch claims:" >&2
    for f in $unaccounted; do echo "  $f" >&2; done
    echo "revert them (git -C $tree checkout -- <file>) or add the patch back" >&2
    exit 1
fi

qcom_dts="$tree/arch/arm64/boot/dts/qcom"
install -m 0644 "$dts_src" "$qcom_dts/sm8550-samsung-gts9wifi.dts"

makefile="$qcom_dts/Makefile"
if ! grep -q 'sm8550-samsung-gts9wifi\.dtb' "$makefile"; then
    printf '\ndtb-$(CONFIG_ARCH_QCOM) += sm8550-samsung-gts9wifi.dtb\n' >> "$makefile"
fi
if ! grep -q '^DTC_FLAGS_sm8550-samsung-gts9wifi := -@$' "$makefile"; then
    printf 'DTC_FLAGS_sm8550-samsung-gts9wifi := -@\n' >> "$makefile"
fi

# Out-of-tree device drivers.  Kbuild awareness comes from the patch queue
# above; the driver source stays a reviewable file in kernel/drivers/ instead
# of being buried in a patch body.
driver_src="$repo_root/kernel/drivers"
soc_qcom="$tree/drivers/soc/qcom"
panel_dir="$tree/drivers/gpu/drm/panel"
[ -d "$driver_src" ] || { echo "missing driver overlay: $driver_src" >&2; exit 1; }
[ -d "$soc_qcom" ] || { echo "not a prepared kernel tree: $soc_qcom" >&2; exit 1; }
[ -d "$panel_dir" ] || { echo "not a prepared kernel tree: $panel_dir" >&2; exit 1; }

# Overlay drivers go where their subsystem expects them: a DRM panel has to sit
# next to the other panels for Kbuild to pick it up with the patch queue's
# Kconfig/Makefile entry.
shopt -s nullglob
for drv in "$driver_src"/*.c; do
    case "${drv##*/}" in
        panel-*) dest=$panel_dir ;;
        keyboard-*) dest="$tree/drivers/input/keyboard" ;;
        *)       dest=$soc_qcom ;;
    esac
    echo "installing ${drv##*/} -> ${dest##*/}/"
    install -m 0644 "$drv" "$dest/${drv##*/}"
done
shopt -u nullglob

# The vendor port is a directory, not a keyboard-*.c file, so it is copied as
# one: Kbuild then descends into it through the entry patch 0009 adds.
port_src="$repo_root/kernel/drivers/input/samsung-pogo"
port_dest="$tree/drivers/input/keyboard/samsung-pogo"
if [ -d "$port_src" ]; then
    mkdir -p "$port_dest"
    install -m 0644 "$port_src"/*.c "$port_src"/*.h "$port_dest/"
    install -m 0644 "$port_src"/Kconfig "$port_dest/"
    echo "installing samsung-pogo/ -> drivers/input/keyboard/samsung-pogo/"
fi

echo "prepared SM-X710 source overlay: $tree"
