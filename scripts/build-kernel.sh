#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
workdir=${GTS9_WORKDIR:-$repo_root/.work}
kernel_src=${KERNEL_SRC:-$workdir/linux-mainline}
kernel_tree=${KERNEL_WORKTREE:-$workdir/build/linux-src-gts9wifi}
build_dir=${KERNEL_BUILD_DIR:-$workdir/build/linux-out}
out_dir=${KERNEL_OUT_DIR:-$repo_root/out/kernel-gts9wifi}
fragment="$repo_root/kernel/config/gts9wifi-mainline.fragment"
# Optional extra fragment for a *diagnostic* build, merged after the mainline
# one.  Empty (the default) means the production configuration, and the
# assertions at the end of this script enforce that the production build can
# never acquire a diagnostic symbol - including by this variable being set in
# the environment of a build someone believed was production.
#
#   GTS9_DIAG_FRAGMENT=kernel/config/gts9wifi-csd-lock.fragment \
#       BUILD_MODULES=0 ./scripts/build-kernel.sh
diag_fragment=${GTS9_DIAG_FRAGMENT:-}
jobs=${JOBS:-$(nproc)}
build_modules=${BUILD_MODULES:-1}
# ccache turns a KERNEL_CLEAN=1 rebuild from a full recompile into a cache
# replay. Enabled whenever ccache is installed; USE_CCACHE=0 opts out.
use_ccache=${USE_CCACHE:-auto}

case "$build_modules" in 0|1) ;; *) echo "BUILD_MODULES must be 0 or 1" >&2; exit 2 ;; esac
# A diagnostic fragment is named as a path relative to the repository root and
# must exist: a typo that silently produced a production kernel would be the
# worst possible outcome of a diagnostic run, because the profile would look
# armed and the instrument would be absent.
if [ -n "$diag_fragment" ]; then
    case "$diag_fragment" in
        /*) diag_path=$diag_fragment ;;
        *)  diag_path=$repo_root/$diag_fragment ;;
    esac
    [ -f "$diag_path" ] || {
        echo "GTS9_DIAG_FRAGMENT does not exist: $diag_fragment" >&2
        exit 2
    }
else
    diag_path=
fi
case "$use_ccache" in auto|0|1) ;; *) echo "USE_CCACHE must be auto, 0 or 1" >&2; exit 2 ;; esac
if [ "$use_ccache" = 1 ] && ! command -v ccache >/dev/null 2>&1; then
    echo 'USE_CCACHE=1 requires ccache; refusing an uncached build' >&2
    exit 1
fi

ccache_args=()
if [ "$use_ccache" != 0 ] && command -v ccache >/dev/null 2>&1; then
    # Keep the cache outside the build tree: KERNEL_CLEAN=1 deletes that, and
    # the whole point is to survive it. The worktree path is stable across
    # clean builds, so absolute-path hashing stays cacheable.
    export CCACHE_DIR=${CCACHE_DIR:-$workdir/ccache}
    export CCACHE_BASEDIR=${CCACHE_BASEDIR:-$workdir}
    # Only sloppiness that cannot change the produced object: reusing a cached
    # object whose include timestamps differ is fine because the content is
    # hashed anyway. time_macros is deliberately NOT set: it lets ccache replay
    # an object compiled with a different __DATE__/__TIME__, which made the
    # same source produce a different Image.gz than a non-ccache build.
    export CCACHE_SLOPPINESS=${CCACHE_SLOPPINESS:-include_file_ctime,include_file_mtime}
    mkdir -p "$CCACHE_DIR"
    ccache_args=(CC="ccache clang")
    echo "ccache enabled: CCACHE_DIR=$CCACHE_DIR"
    ccache --show-stats --verbose 2>/dev/null | sed -n '1,6p' || true
elif [ "$use_ccache" != 0 ]; then
    echo "ccache not found; compiling without it" >&2
fi

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

# Diagnostic patches are opt-in (kernel/patches/diagnostic/README.md) and
# prepare-kernel.sh deliberately does NOT apply them - it restores the pinned
# source and reapplies only the default queue.  That is correct as a default, but
# it also means `build-kernel.sh` silently reverts a diagnostic patch that was
# applied by hand, and produces an image without it.  That is how the flashed
# kernel's `gts9_rpmh_debug` switch was lost by a later BUILD_MODULES=1 run.
#
# GTS9_DIAGNOSTIC_PATCHES names them explicitly, so a diagnostic build is
# reproducible from the command line instead of depending on tree state:
#
#   GTS9_DIAGNOSTIC_PATCHES=0021-gts9-rpmh-timeout-state-dump.patch USE_CCACHE=1 ./scripts/build-kernel.sh
diag=${GTS9_DIAGNOSTIC_PATCHES:-}
if [ -n "$diag" ]; then
	for name in $diag; do
		patch_path=$repo_root/kernel/patches/diagnostic/$name
		[ -f "$patch_path" ] || {
			echo "no such diagnostic patch: $patch_path" >&2; exit 2; }
		git -C "$kernel_tree" apply "$patch_path" || {
			echo "failed to apply diagnostic patch: $name" >&2; exit 2; }
		echo "applied diagnostic patch: $name"
	done
fi

# Keep all generated Kconfig state in O=. The source worktree must contain only
# deliberate DTS/patch changes, otherwise Kbuild rejects the out-of-tree build.
stock_cfg="$build_dir/SM-X710-stock-5.15.153.config"
"$repo_root/scripts/materialize-stock-config.sh" "$stock_cfg"
# The merge order is load-bearing: seed, then the mainline fragment, then the
# diagnostic fragment.  merge_config.sh resolves duplicates last-wins, so the
# diagnostic layer can only ever *add to* or *override* the production one, and
# can never be silently overridden by it.
merge_cfgs=("$stock_cfg" "$fragment")
if [ -n "$diag_path" ]; then
    merge_cfgs+=("$diag_path")
    echo "diagnostic config fragment: ${diag_fragment}"
fi
"$kernel_tree/scripts/kconfig/merge_config.sh" -m -O "$build_dir" \
    "${merge_cfgs[@]}"
make -C "$kernel_tree" O="$build_dir" ARCH=arm64 LLVM=1 olddefconfig

# Validate real Kconfig resolution, not just requested fragment assignments.
# Host-only: preserve UPower sandboxing and gate OCI/network prerequisites.
python3 "$repo_root/scripts/verify-container-config.py" "$build_dir/.config"

required=(
    # SERIAL_QCOM_GENI stays built-in but its *console* is deliberately off; the
    # console assertions are below, where they can be stated as "off" too.
    CONFIG_ARCH_QCOM CONFIG_SERIAL_QCOM_GENI
    CONFIG_BLK_DEV_INITRD CONFIG_RD_LZ4 CONFIG_DEVTMPFS CONFIG_SCSI_UFS_QCOM
    CONFIG_MMC_SDHCI_MSM CONFIG_EXT4_FS CONFIG_PSTORE CONFIG_PSTORE_RAM
    # The first boot test depends on the Samsung sec_log_buf console being
    # present before any root filesystem exists.
    CONFIG_SAMSUNG_GTS9WIFI_SEC_LOG
    # SM8550 early-boot providers: without these the board DTS nodes have no
    # driver at all, because their parent menuconfigs are not part of the
    # 5.15 Android seed (see the fragment's bring-up section).
    CONFIG_PINCTRL_MSM CONFIG_PINCTRL_SM8550 CONFIG_PINCTRL_QCOM_SPMI_PMIC
    CONFIG_PHY_QCOM_QMP CONFIG_PHY_QCOM_QMP_UFS
    CONFIG_PHY_QCOM_QMP_PCIE CONFIG_PHY_QCOM_QMP_COMBO
    CONFIG_SPMI_MSM_PMIC_ARB CONFIG_MFD_SPMI_PMIC
    # The SPMI arbiter's interrupt comes from the PDC: without it there is no
    # PMIC at all on this board (card detect, RTC, ADC), and usb@a600000 cannot
    # resolve its phy interrupts either.
    CONFIG_QCOM_PDC
    # The SMEM node takes its hwlock from the Qualcomm TCSR mutex provider. With
    # the provider missing, qcom_smem_probe() defers forever ("failed to retrieve
    # hwlock") and that cascades into the smp2p devices ("unable to allocate
    # local smp2p item") and then into the ADSP remoteproc, which waits on
    # /smp2p-adsp/slave-kernel. CONFIG_HWSPINLOCK alone is not enough: it is the
    # provider that must bind to hwlock@1f40000.
    CONFIG_HWSPINLOCK_QCOM
    # Reboot-mode support: the SDAM cell comes from SPMI and the driver turns
    # the reboot command string into the value ABL reads.
    CONFIG_NVMEM_SPMI_SDAM CONFIG_NVMEM_REBOOT_MODE
    # PON creates its pwrkey/resin child devices; without it the enabled
    # INPUT_PM8941_PWRKEY driver has no device to bind to.
    CONFIG_POWER_RESET_QCOM_PON
    # Display: the panel driver is the only piece mainline lacks for this board.
    CONFIG_DRM_PANEL_SAMSUNG_ANA38407 CONFIG_DRM_DISPLAY_DSC_HELPER
    CONFIG_QCOM_CLK_RPMH CONFIG_QCOM_RPMHPD CONFIG_ARM_SMMU
    CONFIG_VT CONFIG_VT_CONSOLE CONFIG_FRAMEBUFFER_CONSOLE
    CONFIG_INPUT_EVDEV CONFIG_I2C_QCOM_GENI
    # Stage 1 battery safety depends on the actual PMK8550 Gen3 ADC provider.
    CONFIG_POWER_SUPPLY CONFIG_QCOM_SPMI_ADC5_GEN3 CONFIG_BATTERY_SM5714
)
# The verified mainline Pogo port is the only driver selected by the default
# build. The imported vendor implementation requires an explicit manual A/B.
if ! grep -qx 'CONFIG_KEYBOARD_SAMSUNG_POGO=y' "$build_dir/.config"; then
    echo "required Kconfig symbol is not built-in: CONFIG_KEYBOARD_SAMSUNG_POGO" >&2
    exit 1
fi
if grep -qx 'CONFIG_KEYBOARD_SAMSUNG_POGO_VENDOR_PORT=y' "$build_dir/.config"; then
    echo "the default build must not select CONFIG_KEYBOARD_SAMSUNG_POGO_VENDOR_PORT" >&2
    exit 1
fi
for sym in "${required[@]}"; do
    if ! grep -qx "$sym=y" "$build_dir/.config"; then
        echo "required Kconfig symbol is not built-in: $sym" >&2
        exit 1
    fi
done

# ---------------------------------------------------------------------------
# The CSD/IPI diagnostic split, asserted in BOTH directions.
#
# This is the one config symbol in the tree that must be *off* in production and
# *on* only in a named diagnostic build, and getting it wrong is silent in the
# worst way: a run that believes it is instrumented but is not would produce a
# wedge with no CSD output, and the plan's Case D exists precisely to stop that
# being read as "CSD is not involved".  So the assertion is symmetric - the
# diagnostic build fails if the symbol did not take, and the production build
# fails if it did.
#
# CONFIG_CSD_LOCK_WAIT_DEBUG_DEFAULT is asserted alongside it because
# CSD_LOCK_WAIT_DEBUG alone does not enable anything at runtime: the static key
# is DEFINE_STATIC_KEY_MAYBE(CONFIG_CSD_LOCK_WAIT_DEBUG_DEFAULT, ...) and
# defaults to off.  A build with only the first symbol is a build whose
# instrument never runs, which is the same silent failure by another route.
# ---------------------------------------------------------------------------
csd_is_diag=no
if [ -n "$diag_path" ]; then
    case "$diag_fragment" in
        *csd-lock*) csd_is_diag=yes ;;
    esac
fi
if [ "$csd_is_diag" = yes ]; then
    for sym in CONFIG_CSD_LOCK_WAIT_DEBUG CONFIG_CSD_LOCK_WAIT_DEBUG_DEFAULT; do
        grep -qx "$sym=y" "$build_dir/.config" || {
            echo "CSD diagnostic build is missing $sym=y" >&2
            echo "  the instrument would never run and a wedge would produce no output" >&2
            exit 1
        }
    done
    # The instrument depends on 64BIT for csd->node.dst, which is how the
    # target CPU is named in every report.  Without it csd_lock_wait_getcpu()
    # returns -1 and the reports are useless.
    grep -qx 'CONFIG_64BIT=y' "$build_dir/.config" || {
        echo "CSD diagnostic build requires CONFIG_64BIT=y (csd->node.dst)" >&2
        exit 1
    }
    echo "CSD diagnostic config verified: CSD_LOCK_WAIT_DEBUG=y, _DEFAULT=y, 64BIT=y"
else
    if grep -qx 'CONFIG_CSD_LOCK_WAIT_DEBUG=y' "$build_dir/.config"; then
        echo "the production build must not enable CONFIG_CSD_LOCK_WAIT_DEBUG" >&2
        exit 1
    fi
fi

# The diagnostic fragment must not smuggle in the instruments this round
# deliberately excludes.  Asserted rather than trusted to the fragment's
# comments, because "one instrument at a time" is what makes a result
# attributable and a stray tracer would silently break that.
if [ "$csd_is_diag" = yes ]; then
    for sym in CONFIG_IRQSOFF_TRACER CONFIG_PREEMPT_TRACER CONFIG_FUNCTION_TRACER \
               CONFIG_FUNCTION_GRAPH_TRACER CONFIG_CSD_LOCK_WAIT_DEBUG_DEFAULT; do
        case "$sym" in
        CONFIG_CSD_LOCK_WAIT_DEBUG_DEFAULT) continue ;;
        esac
        if grep -qx "$sym=y" "$build_dir/.config"; then
            echo "the CSD diagnostic build must not enable $sym (one instrument at a time)" >&2
            exit 1
        fi
    done
    # The recovery chain must be unchanged: a wedge has to reboot the tablet by
    # itself or an unattended round strands it.
    grep -qx 'CONFIG_PANIC_TIMEOUT=0' "$build_dir/.config" || {
        echo 'the CSD diagnostic build must keep CONFIG_PANIC_TIMEOUT=0' >&2
        exit 1
    }
    grep -qx 'CONFIG_SOFTLOCKUP_DETECTOR=y' "$build_dir/.config" || {
        echo 'the CSD diagnostic build must keep CONFIG_SOFTLOCKUP_DETECTOR=y' >&2
        exit 1
    }
fi

# Do not silently inherit the Android seed's immediate panic reboot.
grep -qx 'CONFIG_PANIC_TIMEOUT=0' "$build_dir/.config" || {
    echo 'bring-up requires CONFIG_PANIC_TIMEOUT=0' >&2
    exit 1
}

# The serial debug consoles are removed (2026-09-26) and that has to be enforced
# here rather than trusted to the fragment.  Two of these are *silent* reverts:
# olddefconfig re-enables U_SERIAL_CONSOLE and SERIAL_QCOM_GENI_CONSOLE from the
# 5.15 Android seed whenever their dependencies are satisfied, and a single one
# of them back puts a blocking console on /dev/console again - the measured cause
# of both the boot stall (docs/BOOT_CONSOLE_BLOCK.md) and the 90 s poweroff
# (docs/SHUTDOWN_DELAY.md).  CONFIG_NULL_TTY is asserted as well, because without
# it the console=null that ABL appends resolves to nothing at all and the panel
# console loses the argument to an unresolved entry.
#
# Two forms are accepted for "off": `# X is not set` when the symbol is still
# visible but disabled, and NO LINE AT ALL when it has become unexpressible
# because its dependency was removed.  The second is the stronger outcome and is
# what U_SERIAL_CONSOLE now hits - with USB_U_SERIAL gone, Kconfig no longer
# offers that option to any configuration, so there is nothing left for the
# Android seed to re-enable.  Requiring the `is not set` line would fail on the
# very state this change exists to reach.
symbol_state() {
    # symbol_state SYMBOL -> on | off | absent
    if grep -qx "$1=y" "$build_dir/.config"; then
        echo on
    elif grep -qx "# $1 is not set" "$build_dir/.config"; then
        echo off
    else
        echo absent
    fi
}

# Test247 captured agetty in the inherited ARM DCC driver's unbounded TX wait
# with normal IRQs masked. A plain hvc0 getty can reach it without console=hvc0.
# Keep DCC absent in production and diagnostic builds; USB rescue is unrelated.
for off in CONFIG_U_SERIAL_CONSOLE CONFIG_SERIAL_QCOM_GENI_CONSOLE CONFIG_HVC_DCC; do
    state=$(symbol_state "$off")
    if [ "$state" = on ]; then
        echo "a serial debug console is still enabled: $off" >&2
        echo "  the tablet must reach userspace over ssh, not a serial console" >&2
        exit 1
    fi
    echo "console check: $off=$state"
done
for on in CONFIG_NULL_TTY CONFIG_VT_CONSOLE CONFIG_FRAMEBUFFER_CONSOLE; do
    if ! grep -qx "$on=y" "$build_dir/.config"; then
        echo "the console plumbing is incomplete: $on is not built-in" >&2
        exit 1
    fi
done
# CONFIG_VT_CONSOLE is what the panel console is; assert the GENI port itself
# still exists so this change cannot quietly disable the SE block as well.
grep -qx 'CONFIG_SERIAL_QCOM_GENI=y' "$build_dir/.config" || {
    echo 'CONFIG_SERIAL_QCOM_GENI must stay built-in (the GENI SE block is shared IP)' >&2
    exit 1
}

# The gadget has no serial function at all (2026-09-26), and this is the layer
# that makes it true rather than merely intended.  With USB_CONFIGFS_ACM and
# USB_CONFIGFS_SERIAL off, the shared u_serial core has no selector left, so it
# disappears - and that is what makes any gadget ttyGS port impossible, which in
# turn makes the console removal structural rather than merely conventional.
#
# The seed is what makes this worth asserting: it is a 5.15 Android config that
# enabled both, so they come back on their own unless they are pinned off, and a
# serial port reappearing is a capability returning to a device that deliberately
# has none.
for off in CONFIG_USB_CONFIGFS_ACM CONFIG_USB_CONFIGFS_SERIAL \
           CONFIG_USB_U_SERIAL CONFIG_USB_F_ACM CONFIG_USB_F_SERIAL; do
    state=$(symbol_state "$off")
    if [ "$state" = on ]; then
        echo "the gadget must not provide a serial function, but $off is enabled" >&2
        echo "  the ssh transport is the only channel; see docs/FAST_DEBUG_CHANNEL.md" >&2
        exit 1
    fi
    echo "gadget check: $off=$state"
done
# ... while the *host*-side cdc_acm driver stays: it is a different symbol, and it
# is what lets the tablet talk to a USB-serial adapter.
if grep -qx '# CONFIG_USB_ACM is not set' "$build_dir/.config"; then
    echo 'CONFIG_USB_ACM (host-side cdc_acm) must stay enabled' >&2
    exit 1
fi
grep -qx 'CONFIG_USB_CONFIGFS_NCM=y' "$build_dir/.config" || {
    echo 'CONFIG_USB_CONFIGFS_NCM is the ssh transport and must be built-in' >&2
    exit 1
}

# Radio/transport support stays modular, but a silently dropped module is a
# config regression just like a dropped built-in.
required_m=(
    CONFIG_CFG80211 CONFIG_MAC80211 CONFIG_ATH11K CONFIG_ATH11K_PCI
    CONFIG_BT CONFIG_BT_HCIUART CONFIG_BT_QCA
)
for sym in "${required_m[@]}"; do
    if ! grep -qx "$sym=m" "$build_dir/.config"; then
        echo "required Kconfig symbol is not modular: $sym" >&2
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

make -C "$kernel_tree" O="$build_dir" ARCH=arm64 LLVM=1 "${ccache_args[@]}" \
    -j"$jobs" "${make_targets[@]}"

release=$(make -s -C "$kernel_tree" O="$build_dir" ARCH=arm64 LLVM=1 kernelrelease)

# Refuse to silently replace a kernel image that a boot bundle says is flashed.
# This is not hypothetical: a `BUILD_MODULES=1` run on a worktree that had lost
# its diagnostic patches produced a valid-looking Image.gz without them, and
# overwrote the artifact that `out/boot-bundle-*/BUNDLE_INFO` names as flashed.
# The modules were unaffected (every patched driver is =y, so no patch can reach a
# .ko), but the image provenance was briefly wrong - which is exactly the kind of
# thing that is discovered months later.
new_img=$build_dir/arch/arm64/boot/Image.gz
if [ -f "$out_dir/Image.gz" ]; then
	old_sha=$(sha256sum "$out_dir/Image.gz" | cut -d' ' -f1)
	flashed=0
	for info in "$repo_root"/out/boot-bundle-*/BUNDLE_INFO; do
		[ -f "$info" ] || continue
		if grep -q "$old_sha" "$info" 2>/dev/null; then
			flashed=1
			echo "WARNING: the existing $out_dir/Image.gz (${old_sha:0:16}) is named by" >&2
			echo "         $(basename "$(dirname "$info")")/BUNDLE_INFO as a flashed image." >&2
			break
		fi
	done
	if [ "$flashed" = 1 ] && [ "${GTS9_ALLOW_IMAGE_REPLACE:-0}" != 1 ]; then
		if cmp -s "$new_img" "$out_dir/Image.gz"; then
			: # identical, nothing to protect
		else
			cp -a "$out_dir/Image.gz" "$out_dir/Image.gz.flashed-$(date -u +%Y%m%dT%H%M%SZ)"
			echo "WARNING: kept a copy as Image.gz.flashed-*." >&2
			echo "         Set GTS9_ALLOW_IMAGE_REPLACE=1 to replace it deliberately, and" >&2
			echo "         re-verify the worktree is patched before doing so." >&2
		fi
	fi
fi
install -m 0644 "$new_img" "$out_dir/Image.gz"
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
    sha256sum Image.gz sm8550-samsung-gts9wifi.dtb config kernel.release > SHA256SUMS
)

cat <<EOF2

Build complete
  release: $release
  output : $out_dir

$(cat "$out_dir/SHA256SUMS")
EOF2
