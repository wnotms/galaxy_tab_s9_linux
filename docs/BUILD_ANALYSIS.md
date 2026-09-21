# SM-X710 mainline build: repository analysis and build report

> Historical build analysis: the current ramdisk layout and boot-loop repair
> are documented in [BOOTLOOP_FIX.md](BOOTLOOP_FIX.md). In the current bundle,
> init_boot holds BusyBox and vendor_boot has an empty platform archive.

This note records what the repository actually does, what had to be fixed before
a flashable kernel could be produced, and what the resulting artifacts are.
It complements `AGENT.md` (working rules) and `docs/MAINLINE_PORT_PLAN.md`
(bring-up plan); it does not replace either.

Status vocabulary follows `AGENT.md`: **compiled**, **booted**, **enumerated**,
**observed**, **verified** are different states and are not collapsed here.

## 1. What the repository is

A reproducible bring-up workspace for upstream Linux on the Samsung Galaxy Tab
S9 Wi-Fi (`SM-X710` / `gts9wifi`, Qualcomm SM8550 / `kalama`), built from three
separated layers:

| Layer | Location | Role |
|---|---|---|
| stock evidence | `reference/stock/` | owner-extracted Samsung 5.15.153 `.config` (byte-exact, SHA-256 checked) plus live DTB/DTS facts |
| port layer | `kernel/dts/`, `kernel/config/`, `kernel/patches/` | board DTS, Kconfig fragment, minimal patch queue |
| build pipeline | `scripts/` | fetch → prepare → resolve config → LLVM build → artifacts; never flashes |

Pipeline as executed:

```text
fetch-mainline.sh     clone/verify torvalds/linux @ v7.2-rc3 a13c140cc289c0b7b3770bce5b3ad42ab35074aa
prepare-kernel.sh     disposable git worktree + patch queue + board DTS + dtb-* rule (-@ for __symbols__)
materialize-stock-config.sh
                      rebuild the exact 5.15.153 seed config and verify its SHA-256
merge_config.sh       seed + kernel/config/gts9wifi-mainline.fragment
olddefconfig          Linux 7.2 Kconfig resolution
build-kernel.sh       make Image.gz qcom/sm8550-samsung-gts9wifi.dtb [modules]
```

The pinned upstream checkout under `.work/linux-mainline` is kept pristine; all
device edits happen in the throwaway worktree `.work/build/linux-src-gts9wifi`
and all generated state lives in `O=.work/build/linux-out`.

## 2. Build environment

| Item | Value |
|---|---|
| host | WSL2, x86_64, 12 CPUs, 15 GiB RAM |
| clang / lld | 21.1.8 |
| binutils helpers | llvm-ar / llvm-nm / llvm-objcopy / llvm-strip |
| other | GNU make 4.4.1, bison, flex, bc, dtc, pahole, openssl, ccache |
| kernel source | `torvalds/linux` mirror, verified to the pinned commit |

`git.kernel.org` was reachable but rate-limited to roughly 50 KB/s in this
environment, so the clone was taken from the `torvalds/linux` mirror with
`LINUX_REPO=`. The pin is a content hash, so the verification step in
`fetch-mainline.sh` (`HEAD == a13c140cc289c0b7b3770bce5b3ad42ab35074aa`) still
fails closed if the wrong tree is present. No script change was needed.

## 3. Kconfig: what the stock seed can and cannot provide

The 5.15.153 Android seed is intact and reproducible (191,842 bytes, SHA-256
`80693a06…0112`). After `olddefconfig` on Linux 7.2 it contributes 2,114
symbols; 320 of them no longer exist upstream and 13 changed between `y`/`m`.
Representative removals are downstream-only or renamed:

```text
ANDROID, ANDROID_VENDOR_HOOKS, ANDROID_VENDOR_OEM_DATA, ANDROID_KABI_RESERVE,
ASHMEM, SAMSUNG_BINDER_MONITOR, SECURITY_DSMS, SECURITY_KUMIHO,
GKI_HIDDEN_*_CONFIGS, SEC_MM, BLOCK_SUPPORT_STLOG, MMC_SUPPORT_STLOG,
SERIAL_SAMSUNG*, SND_COMPRESS_OFFLOAD,
CFI_CLANG -> CFI (renamed), CFI_CLANG_SHADOW (removed),
PINCTRL_SPMI_PMIC -> PINCTRL_QCOM_SPMI_PMIC (renamed),
MODULE_SIG_SHA1 (removed; 7.2 resolved SHA3-256), CMDLINE_EXTEND (removed)
```

### 3.1 The real problem: driver symbols that never reached Kconfig

`AGENT.md` rule 7 says a fragment symbol dropped by `olddefconfig` is a config
bug. Ten did, and the cause was not the 5.15→7.2 delta but **missing Kconfig
parents**: the drivers were not merely disabled, they were invisible, because a
`menuconfig`/`if` gate above them was never enabled.

| Fragment request | Hidden behind | Effect if left alone |
|---|---|---|
| `PINCTRL_SM8550` | `PINCTRL_MSM` | no TLMM: every GPIO in the board DTS |
| `PHY_QCOM_QMP_UFS` | `PHY_QCOM_QMP` | no UFS PHY → no internal storage |
| `PHY_QCOM_QMP_PCIE` | `PHY_QCOM_QMP` | no PCIe PHY → no Wi-Fi |
| `PHY_QCOM_QMP_COMBO` | `PHY_QCOM_QMP` | no USB3/DP combo PHY |
| `INPUT_PM8941_PWRKEY` | `MFD_SPMI_PMIC` | no power key |
| `RTC_DRV_PM8XXX` | `MFD_SPMI_PMIC` | no RTC |
| `ATH11K`, `ATH11K_PCI` | `WLAN_VENDOR_ATH` | no Wi-Fi driver at all |
| `FRAMEBUFFER_CONSOLE` | `VT` (console Kconfig is sourced only `if VT`) | no fbcon console |

The fragment's bring-up section now asserts those parents, and
`scripts/build-kernel.sh` asserts the resulting symbols (`=y` and `=m`) so a
future silent drop fails the build instead of shipping.

A second, larger gap is SM8550 platform plumbing that the stock Android config
never needed by those names: `SPMI_MSM_PMIC_ARB` (PMIC bus → regulators, GPIO,
pwrkey), `QCOM_CLK_RPMH` (RPMh clock controller that parents GCC/DISPCC/GPUCC),
`QCOM_RPMHPD` (RPMh power domains used by UFS/display/GPU), `ARM_SMMU`,
`QCOM_WDT`, `QCOM_TSENS` + `NVMEM_QCOM_QFPROM`, `ARM_QCOM_CPUFREQ_HW`,
`QCOM_SPMI_ADC5`. These are now explicit in the fragment.

## 4. Board DTS finding: malformed SCM interrupt specifier

`kernel/dts/sm8550-samsung-gts9wifi.dts` carried:

```dts
&scm {
	interrupts = <GIC_SPI 930 IRQ_TYPE_EDGE_RISING>;
};
```

SM8550's GIC is `#interrupt-cells = <4>` (the fourth cell selects the PPI
partition, `0` for an SPI), so this three-cell specifier is malformed. dtc
reports it, and at runtime `of_irq_parse_one()` fails with `-ENODATA`;
`platform_get_irq_optional()` then reports `-ENXIO`, so `qcom_scm_probe()`
silently continues **without** the SCM waitqueue interrupt whenever firmware
does not supply it through `QCOM_SCM_WAITQ_GET_INFO`. The specifier now has the
missing fourth cell and the DTB builds warning-free.

The same DTS keeps two deliberate oddities that were checked and left alone:

- `splash_region` has a `reg` but no unit address (dtc `W=1` warning). The node
  name is documented in the file as an X710 ABL expectation, so it must not be
  renamed for cosmetics.
- The panel node uses `samsung,ana38407-amsa10fa01`, a device-specific panel
  binding whose driver is not part of this repository yet (milestone M3).
  `mdss`/`dsi0`/`dp0` probe, the panel itself will not bind until that driver
  is added.

## 5. Bring-up profile applied to the fragment

The stock seed is an Android **debug** configuration. Several of its choices are
wrong for a kernel that is meant to boot and be used on the tablet, so the
fragment overrides them explicitly (the seed itself is untouched):

| Symbol | Stock | Build | Why |
|---|---|---|---|
| `LTO_CLANG_FULL` | y | n | full LTO turns the final link into a single-threaded, high-memory, multi-hour step |
| `CFI` (was `CFI_CLANG`) | y | n | kCFI rewrites indirect calls in every early probe; keep the port debuggable |
| `KASAN` (+`KASAN_HW_TAGS`) | y | n | MTE/KASAN is a debug runtime with large memory/time cost |
| `UBSAN` | y | n | ditto, and `UBSAN_TRAP` panics on findings |
| `WERROR` | y | n | a newer clang must not turn a warning into a missing kernel |
| `CMDLINE` | Samsung debug string | `""` | `kasan.*`/`kvm-arm.mode=protected`/`cgroup_disable=pressure` do not belong in a non-KASAN bring-up kernel |
| `LOCALVERSION` | git-describe | `-gts9wifi` | stable module path (`-dirty` note below) |

Everything else still comes from the stock seed. Re-enabling any row is a
one-line change in `kernel/config/gts9wifi-mainline.fragment`.

Resolved configuration: 2,222 built-in / 165 modular symbols.

## 6. Build result

Command (no flashing, no device access):

```bash
BUILD_MODULES=1 JOBS=12 ./scripts/build-kernel.sh
```

| Artifact (`out/kernel-gts9wifi/`) | Size | SHA-256 |
|---|---|---|
| `Image.gz` | 21,803,106 B (20.8 MiB) | `ea2cf646a9679e16ac438f7904636786f2ddaad29924694562948cc5376a6fc9` |
| `sm8550-samsung-gts9wifi.dtb` | 175,387 B | `1c105090a0c087334435e19fb9f99047ac32865994baf372511846a0a367083c` |
| `config` | 240,586 B | `0b85ef3f4a141dde6719ec3554ba780b21ad8afacf02e118f19d93094b82ebdb` |
| `kernel.release` | `7.2.0-rc3-gts9wifi-dirty` | — |
| `modules-root/` | 167 modules + `modules.dep` | — |

Build statistics: 4,019 objects, 167 modules, ~17.5 min wall clock on 12 cores,
**zero compiler warnings**, zero errors. Re-running the same command afterwards
finishes in 22 s and re-produces byte-identical `Image.gz` and DTB.

The `-dirty` suffix is real, not an accident: the board overlay is applied to a
throwaway worktree that is deliberately never committed, so `scripts/
setlocalversion` marks the release. It is stable for a given overlay and the
module path matches the kernel's own vermagic
(`7.2.0-rc3-gts9wifi-dirty SMP preempt mod_unload modversions aarch64`).

Independent verification performed on the artifacts:

| Check | Tool | Result |
|---|---|---|
| arm64 boot image header | `Image` magic at offset 56 | `ARMd`, 4 KiB pages, `image_size` 46.2 MiB |
| gzip integrity | `gzip -t` | OK, uncompressed size matches `Image` |
| boot partition fit | 96 MiB `boot` partition from `build-boot-bundle.sh` | 20.8 MiB + 0.17 MiB |
| Samsung ABL selectors | decompiled DTB | `qcom,kalama-mtp/kalama/mtp`, `qcom,board-id = <0x10008 0x04>`, four `qcom,msm-id` pairs |
| ABL DTBO labels | `__symbols__` | `qcom_tzlog = /chosen`, `arch_timer = /timer`, `qcom_scm = /firmware/scm` |
| SCM interrupt specifier | decompiled DTB | `<0x00 0x3a2 0x01 0x00>` (4 cells) |
| DTB warnings | `make W=1 dtbs` | none from this board (one upstream-only note remains) |
| enabled hardware nodes | DTB parse | UFS HC + QMP UFS PHY, SDHCI `mmc@8804000`, PCIe0 + gen3x2 PHY, DWC3 + eUSB2/QMP PHY, TLMM, SPMI arbiter with PM8550/PMK8550 (regulators, GPIO, pwrkey, RTC, ADC5), MDSS + DP + DSI0 + DSI PHY, Adreno GPU, ADSP, VA macro, GPI DMA + I2C/UART console |
| radio modules | `modinfo` | `ath11k`, `ath11k_pci`, `cfg80211`, `mac80211`, `hci_uart`, `btqca`, `bluetooth`, `pwrseq-qcom-wcn`, `qrtr-mhi`; vermagic matches `kernel.release` |
| module dependencies | `modules.dep` / `modules.builtin` | present (depmod ran during `modules_install`) |
| config assertions | `scripts/build-kernel.sh` | all `=y` and `=m` required symbols present |


## 7. Boot-chain tooling adopted from the SM-X910 reference port

The adjacent `ubuntu-galaxy-tab-s9-ultra` (SM-X910, `gts9uwifi`) port already
solves the "built kernel -> flashable bundle" half of the pipeline. Three of
its host-side pieces were adapted, not copied wholesale: no X910 hardware
assumption, driver or config was imported, and the X710 boot layout (empty
generic ramdisk in `init_boot`, real initramfs as a `vendor_boot` platform
fragment) is kept as this repository defines it.

| New file | Adapted from | Change for this repository |
|---|---|---|
| `scripts/check-build-deps.sh` | X910 `scripts/check-build-deps.sh` | kernel half extended for `ARCH=arm64 LLVM=1` (clang/lld/llvm, pahole, libssl/libelf, depmod) plus the AOSP tool check; clang >= 17 is enforced because Linux 7.2 requires it |
| `scripts/stage-android-tools.sh` | X910 `scripts/stage-android-tools.sh` | the X910 script copies `mkbootimg.py`/`avbtool.py` out of a postmarketOS chroot; this repository has no chroot, so they are downloaded from `android.googlesource.com` at pinned revisions and verified against pinned SHA-256 values, with `unpack_bootimg.py` added for offline inspection |
| `scripts/make-initramfs.sh` | X910 `scripts/make-initramfs.sh` | the X910 script calls `update-initramfs` inside an Ubuntu rootfs chroot; this one packs a tree supplied with `--root`, injects the modules built for the kernel release, and verifies the legacy-LZ4 stream and the `vendor_boot` budget |

Pipeline smoke test performed on the real artifacts (`out/kernel-gts9wifi/`),
with a placeholder `/init` tree and the 167 built modules:

```text
make-initramfs.sh   152 MiB module tree -> 57,898,820 B legacy-LZ4 initramfs
                    magic 02214c18, inside the 92,274,688 B budget, depmod run
build-boot-bundle.sh boot.img / init_boot.img / vendor_boot.img / dtbo.img / vbmeta.img
                    produced at the exact partition sizes
```

Independent checks on that bundle: `avbtool info_image` reports the `boot` hash
descriptor with the expected original image size; `unpack_bootimg` reports
`VNDRBOOT` header v4, the X710 cmdline, the bootconfig, the 175,387 B DTB and
the 57,898,820 B vendor ramdisk; the extracted ramdisk is byte-identical
(SHA-256) to the one `make-initramfs.sh` produced; the `init_boot` ramdisk is
the 82 B empty legacy-LZ4 stream; and the `boot.img` payload is exactly
`Image.gz || sm8550-samsung-gts9wifi.dtb` (the appended-DTB fallback route).

The test bundle was built in a temporary directory and deleted afterwards: its
initramfs contained a placeholder `/init`, so it is a pipeline test, not a
flashable image. Section 9 replaces that placeholder with a real BusyBox tree,
and the validator now rejects an `/init`-less archive outright.

## 8. What this does and does not prove

**compiled** and **packaged** — the statements above, plus the first-boot
additions below.

**not booted**: no artifact in this repository has been flashed or booted on the
tablet. Per `AGENT.md`, an empty pstore is not evidence of a kernel crash, and
a driver that compiles is not a driver that probes. The boot bundle above was
assembled and inspected offline; that proves the packaging, not the boot.

## 9. First-boot readiness added after the initial build

| Piece | State |
|---|---|
| persistent console | `CONFIG_SAMSUNG_GTS9WIFI_SEC_LOG=y`, driver `kernel/drivers/samsung-gts9wifi-sec-log.c`, compiled into vmlinux with no warnings. The built DTB wires it up as intended: `sec-kernel-log` (`samsung,gts9wifi-sec-kernel-log`) points at `sec-log@880200000` = `0x8:0x80200000 + 0x200000`, i.e. 2 MiB at `0x880200000`, which is the region the driver maps. The LOGM layout is a bring-up adaptation from the physically validated SM-X910 port and is **not** X710-verified |
| real userspace | `scripts/build-bringup-initramfs.sh` builds a pinned static BusyBox tree with `boot/bringup-init.sh` as `/init`; 1,146,125 B, byte-reproducible, applets present, no modules by design |
| packaging gate | `scripts/validate-boot-bundle.sh` re-extracts kernel, appended DTB, vendor ramdisk and AVB footers; fails hard when the initramfs has no executable `/init` |
| device gate | `scripts/check-device-layout.sh` read-only partition audit; the sibling values are an assumption until it confirms them on the tablet |
| procedure | `docs/FIRST_BOOT_TEST.md` (audit → backup → recovery plan → build → validate → manual flash → test → A–E classification → evidence) and `reference/stock/BOOT_CHAIN.md` |

End-to-end host-side run of the current tree:

```text
build-kernel.sh            Image.gz ddf356a0…  DTB 1c105090…  config aa414454…
build-bringup-initramfs.sh 1,146,125 B legacy-LZ4, sha256 4c2764ba…
build-boot-bundle.sh       boot/init_boot/vendor_boot/dtbo/vbmeta at partition size
validate-boot-bundle.sh    BOOT BUNDLE VALIDATION PASSED (exit 0)
```

Still required before the first physical test is meaningful:

1. the owner runs `check-device-layout.sh` on the tablet and reconciles the
   real partition sizes with `reference/stock/BOOT_CHAIN.md`;
2. the mandatory stock boot-chain backup;
3. firmware files on any later rootfs (`ath11k` QCA6490, `adreno` a740, `qcom`
   ADSP) — not needed for this test;
4. the M3 panel driver if display is required at first boot — also not needed
   for this test, which is judged on the persistent log and the initramfs.

The project state after this round was **ready for the first controlled physical
boot test**. That test has since happened: see
`reference/boot-tests/test-010-20260921T125507Z/`, where the owner watched the
tablet power itself off while running this kernel - `ABL -> mainline Linux ->
BusyBox /init` is therefore reached on hardware.

Two corrections came out of the physical tests and apply to the text above:

- the persistent `sec_log` console does **not** work as an evidence channel on
  this tablet: the bootloader's own log occupies 2,096,187 of the 2,097,136
  bytes of the ring on every boot (test 007), so mainline writes are overwritten
  before recovery can read them. An empty ring is not evidence of anything;
- the "kernel never reaches `setup_arch`" reading of test 003 was an artefact of
  that ring and is retracted.

Nothing about storage, display, touch, GPU, radio, audio or charging has been
validated, and the project must not be described as hardware-verified beyond the
boot chain above.
