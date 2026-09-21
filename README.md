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
- Initial mainline port sources: the hardware-validated SM-X710 work in `troikoss/gts9wifi-fedora`, pinned in `kernel/PROVENANCE.md`

The vendored board DTS is a bootstrap baseline derived from a hardware-tested SM-X710 mainline port. This repository intentionally does **not** import that port's entire out-of-tree driver/patch stack on day one. Hardware support is added in small, reviewable steps and must be revalidated on this tablet.

## Build the kernel

Ubuntu 24.04 / Debian-like host:

```bash
sudo apt update
sudo apt install -y \
  git make bc bison flex clang lld llvm ccache gzip \
  libssl-dev libelf-dev dwarves device-tree-compiler \
  python3 rsync kmod

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

The build scripts never flash a tablet. Once a matching initramfs exists, an Android boot-v4 bundle can be assembled explicitly:

```bash
MKBOOTIMG=/path/to/mkbootimg.py \
AVBTOOL=/path/to/avbtool.py \
./scripts/build-boot-bundle.sh \
  --initramfs /path/to/initramfs.img \
  --cmdline boot/cmdline.example.txt \
  --bootconfig boot/bootconfig.example.txt
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
scripts/build-kernel.sh      reproducible LLVM build
scripts/build-boot-bundle.sh Android boot header v4 packaging, no flashing
scripts/audit-stock.sh       extracts useful facts from stock config/DTS
reference/stock/             hashes and facts from the supplied stock artifacts
docs/MAINLINE_PORT_PLAN.md   staged bring-up and validation plan
```

## Safety boundary

Nothing in this repository should invoke Odin, Heimdall, `dd` to a block device, `fastboot flash`, or TWRP flashing automatically. Build and packaging are allowed; flashing is a separate, manual test step after artifact inspection and recovery planning.
