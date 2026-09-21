# Galaxy Tab S9 Wi-Fi (SM-X710) mainline Linux

This repository is a reproducible bring-up workspace for running an upstream Linux kernel on the Samsung Galaxy Tab S9 Wi-Fi (`SM-X710`, `gts9wifi`, Qualcomm SM8550 / Snapdragon 8 Gen 2).

The project deliberately separates three things:

1. **stock evidence** — the owner-extracted Samsung 5.15.153 config is preserved byte-for-byte as the Kconfig seed; the live DTB/decompiled DTS remain hardware documentation;
2. **mainline port layer** — board DTS, out-of-tree drivers and a small patch set carried on top of a pinned upstream kernel;
3. **build output** — generated outside the source checkout and never flashed automatically.

## Baseline

- Device: Samsung Galaxy Tab S9 Wi-Fi, SM-X710 (`gts9wifi`)
- SoC: Qualcomm SM8550 / `kalama`, Adreno 740
- Mainline baseline: Linux `v7.2-rc3`, commit `a13c140cc289c0b7b3770bce5b3ad42ab35074aa`
- Stock evidence supplied for this repository: Linux 5.15.153, Android clang 14.0.7, board-id `0x04`
- Initial mainline port sources: the hardware-validated SM-X710 work in `troikoss/gts9wifi-fedora`, plus the earlier `Azkali/sm8550-mainline` X710 bring-up history, pinned in `kernel/PROVENANCE.md`

The vendored board DTS is a bootstrap baseline derived from a hardware-tested SM-X710 mainline port. A small Samsung ABL compatibility patch from the earlier Azkali X710 work is carried separately because Linux 7.2-rc3 still lacks the DTBO labels expected by Samsung's bootloader. This repository intentionally does **not** import that port's entire out-of-tree driver/patch stack on day one. Hardware support is added in small, reviewable steps and must be revalidated on this tablet.

## Build the kernel

Ubuntu 24.04 / Debian-like host:

```bash
sudo apt update
sudo apt install -y \
  git make bc bison flex clang lld llvm ccache gzip \
  libssl-dev libelf-dev dwarves device-tree-compiler \
  python3 rsync kmod cpio lz4

./scripts/check-build-deps.sh   # report anything still missing
./scripts/fetch-mainline.sh
./scripts/build-kernel.sh
```

Outputs are written to `out/kernel-gts9wifi/`:

```text
Image.gz
sm8550-samsung-gts9wifi.dtb
config
kernel.release
SHA256SUMS
modules-root/        # when BUILD_MODULES=1
```

Useful switches:

```bash
KERNEL_CLEAN=1 ./scripts/build-kernel.sh
BUILD_MODULES=0 ./scripts/build-kernel.sh
JOBS=16 ./scripts/build-kernel.sh
```

The build uses LLVM (`ARCH=arm64 LLVM=1`) and a disposable git worktree. The pinned upstream checkout remains pristine. Before Kconfig resolution, `scripts/materialize-stock-config.sh` reconstructs the exact owner-extracted Samsung 5.15.153 `.config` and verifies SHA-256 `80693a069d406fbdafe01b73e65e8f1e15b681451bbb53b9d05fde7a93220112`; Linux 7.2 then merges the small mainline device fragment and runs `olddefconfig`, so obsolete Samsung-only symbols are naturally dropped while the stock baseline remains explicit.

## Android boot v4 bundle

The build scripts never flash a tablet. The AOSP tools the packaging needs are
staged and hash-pinned by the repository, the initramfs is packed and checked
here, and only then is the bundle assembled:

```bash
./scripts/stage-android-tools.sh          # mkbootimg.py / avbtool.py, hash-pinned

./scripts/make-initramfs.sh \
  --root /path/to/initramfs-tree \
  --modules out/kernel-gts9wifi/modules-root \
  --out out/boot-bundle/initramfs.img

./scripts/build-boot-bundle.sh \
  --initramfs out/boot-bundle/initramfs.img \
  --cmdline boot/cmdline.example.txt \
  --bootconfig boot/bootconfig.example.txt
```

`make-initramfs.sh` packs a tree you supply (it does not generate userspace),
injects the modules built for this kernel release, runs `depmod`, and refuses
anything that is not a legacy-LZ4 stream or that does not fit the `vendor_boot`
budget. `build-boot-bundle.sh` takes `MKBOOTIMG`/`AVBTOOL` from the environment
and defaults to the staged copies when they are already exported:

```bash
MKBOOTIMG=$PWD/.work/tools/mkbootimg.py AVBTOOL=$PWD/.work/tools/avbtool.py \
  ./scripts/build-boot-bundle.sh --initramfs ... --cmdline ... --bootconfig ...
```

Read `docs/MAINLINE_PORT_PLAN.md` before any physical test. In particular, do not blindly replace Samsung's DTBO or repartition internal storage during early bring-up.

## Repository layout

```text
AGENT.md                     rules/context for future coding agents
kernel/dts/                  translated SM-X710 mainline board DTS
kernel/config/               small device Kconfig fragment
kernel/patches/              local patch queue (initially empty/minimal)
scripts/prepare-kernel.sh    stages DTS/patches into a disposable tree
kernel/PROVENANCE.md         source/pin/licensing notes
scripts/fetch-mainline.sh    obtains and verifies the upstream kernel
scripts/check-build-deps.sh  reports missing host tools, installs nothing
scripts/build-kernel.sh      reproducible LLVM build
scripts/stage-android-tools.sh  hash-pinned AOSP mkbootimg/avbtool staging
scripts/make-initramfs.sh    packs and verifies the legacy-LZ4 initramfs
scripts/build-boot-bundle.sh Android boot header v4 packaging, no flashing
scripts/audit-stock.sh       extracts useful facts from stock config/DTS
reference/stock/             hashes and facts from the supplied stock artifacts
docs/MAINLINE_PORT_PLAN.md   staged bring-up and validation plan
docs/BUILD_ANALYSIS.md       repository analysis and the verified build result
docs/AZKALI_SM8550_MAINLINE_ANALYSIS.md  decisions from the earlier X710 kernel fork
```

## Safety boundary

Nothing in this repository should invoke Odin, Heimdall, `dd` to a block device, `fastboot flash`, or TWRP flashing automatically. Build and packaging are allowed; flashing is a separate, manual test step after artifact inspection and recovery planning.
