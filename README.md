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
USE_CCACHE=1 ./scripts/build-kernel.sh
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

`USE_CCACHE=1` requires ccache and fails if it is unavailable; the default
`USE_CCACHE=auto` uses it when installed. The cache survives clean builds.

The build uses LLVM (`ARCH=arm64 LLVM=1`) and a disposable git worktree. The pinned upstream checkout remains pristine. Before Kconfig resolution, `scripts/materialize-stock-config.sh` reconstructs the exact owner-extracted Samsung 5.15.153 `.config` and verifies SHA-256 `80693a069d406fbdafe01b73e65e8f1e15b681451bbb53b9d05fde7a93220112`; Linux 7.2 then merges the small mainline device fragment and runs `olddefconfig`, so obsolete Samsung-only symbols are naturally dropped while the stock baseline remains explicit.

## Android boot v4 bundle

The build scripts never flash a tablet. The AOSP tools the packaging needs are
staged and hash-pinned by the repository, the initramfs is built, packed and
checked here, and only then is the bundle assembled and validated:

```bash
./scripts/stage-android-tools.sh          # mkbootimg.py / avbtool.py, hash-pinned
./scripts/build-bringup-initramfs.sh      # minimal BusyBox initramfs, pinned

MKBOOTIMG=$PWD/.work/tools/mkbootimg.py AVBTOOL=$PWD/.work/tools/avbtool.py \
  ./scripts/build-boot-bundle.sh \
    --initramfs out/boot-bundle/initramfs-bringup.img \
    --cmdline boot/cmdline.example.txt \
    --bootconfig boot/bootconfig.example.txt

./scripts/validate-boot-bundle.sh         # must print BOOT BUNDLE VALIDATION PASSED
```

`build-bringup-initramfs.sh` assembles the minimal bring-up userspace
(`boot/bringup-init.sh` as `/init`, a pinned static BusyBox and its applets)
and hands it to `make-initramfs.sh`, which packs a tree, refuses anything that
is not a legacy-LZ4 stream, and enforces a 7 MiB budget for the 8 MiB `init_boot` partition. Use
`make-initramfs.sh --root ... --modules out/kernel-gts9wifi/modules-root`
directly when a test needs loadable modules; the first boot test does not.

The opt-in `gts9_minimal_rootfs=1` profile branches to a separate, small
rootfs handoff path before display, USB, UFS, or bring-up report operations.
It waits up to 30 seconds for the microSD root, mounts ext4 and switches to
Debian, or leaves a BusyBox rescue shell with block-device diagnostics. Each
stage is persisted to `/var/log/gts9-minimal-last-boot` on the Debian root, so a
black screen with no USB console can still be diagnosed offline from TWRP. The
default cmdline is unchanged; see
[minimal rootfs boot](docs/MINIMAL_ROOTFS_BOOT.md) and
`boot/cmdline.minimal-rootfs.example.txt` for the controlled A/B profile.

Debian now owns the userspace bring-up that used to live in the initramfs -
the USB ACM console, the ttyGS0 root console, the X710 panel cold-boot recovery
and the boot-stage units - under `rootfs-overlay/`. Install them with:

```bash
sudo ./scripts/install-debian-rootfs.sh /mnt/debian      # mounted rootfs
./scripts/install-debian-rootfs.sh --tar out/gts9-debian-overlay.tar  # for TWRP
```

The tarball carries relative paths only, so TWRP deploys it with
`cd /mnt/debian && tar -xpf /tmp/gts9-debian-overlay.tar`. Kernel modules are
installed under `lib/modules/<release>`, firmware under `lib/firmware/`, and
`depmod -b` generates the module dependencies. See
[TWRP offline maintenance](docs/TWRP_DEBIAN_RECOVERY.md).

`validate-boot-bundle.sh` is the gate before any physical test: it re-extracts
the kernel, the appended DTB, both ramdisks and every AVB footer, and
fails if the initramfs has no executable `/init`. It only reads.

The generic BusyBox initramfs now lives in `init_boot.img`; `vendor_boot.img`
contains an empty platform fragment. Rebuild and update **all changed images**,
including `init_boot.img`, when moving from the older layout. The bring-up PID 1
survives a missing console or shell exit. See [boot-loop investigation](docs/BOOTLOOP_FIX.md)
for the reference comparison and the remaining hardware validation.

Read `docs/FIRST_BOOT_TEST.md` before any physical test: it defines the single
success chain, the mandatory stock backup, the recovery plan, the manual flash
steps and the A–E result classification. In particular, do not blindly replace
Samsung's DTBO, do not overwrite `vbmeta`, and do not repartition internal
storage during early bring-up.

## Repository layout

```text
AGENT.md                     rules/context for future coding agents
kernel/dts/                  translated SM-X710 mainline board DTS
kernel/drivers/              out-of-tree device drivers (sec_log console)
kernel/config/               small device Kconfig fragment
kernel/patches/              local patch queue (initially empty/minimal)
boot/bringup-init.sh         the /init of the bring-up initramfs
boot/minimal-rootfs-init.sh opt-in minimal rootfs handoff profile
boot/minimal-rootfs-state.sh  persistent minimal boot-stage record
boot/gts9-minimal-pid1.c     static PID 1 exec-failure rescue helper
rootfs-overlay/              Debian userspace: units, helpers, getty config
scripts/prepare-kernel.sh    stages DTS/patches into a disposable tree
kernel/PROVENANCE.md         source/pin/licensing notes
scripts/fetch-mainline.sh    obtains and verifies the upstream kernel
scripts/check-build-deps.sh  reports missing host tools, installs nothing
scripts/build-kernel.sh      reproducible LLVM build
scripts/stage-android-tools.sh  hash-pinned AOSP mkbootimg/avbtool staging
scripts/make-initramfs.sh    packs and verifies the legacy-LZ4 initramfs
scripts/build-bringup-initramfs.sh  minimal BusyBox initramfs for bring-up
scripts/build-boot-bundle.sh Android boot header v4 packaging, no flashing
scripts/validate-boot-bundle.sh  read-only pre-flash bundle gate
scripts/install-debian-rootfs.sh  Debian overlay install / TWRP tarball
scripts/twrp-mount-debian.sh  safe offline Debian mount helper for TWRP
scripts/check-device-layout.sh   read-only partition audit, runs on the tablet
scripts/audit-stock.sh       extracts useful facts from stock config/DTS
reference/stock/             hashes and facts from the supplied stock artifacts
docs/FIRST_BOOT_TEST.md      first physical boot test, recovery plan, A-E cases
docs/MINIMAL_ROOTFS_BOOT.md  minimal Debian rootfs profile and A/B procedure
docs/TWRP_DEBIAN_RECOVERY.md TWRP offline inspection, repair and deployment
docs/MAINLINE_PORT_PLAN.md   staged bring-up and validation plan
docs/BUILD_ANALYSIS.md       repository analysis and the verified build result
docs/AZKALI_SM8550_MAINLINE_ANALYSIS.md  decisions from the earlier X710 kernel fork
```

## Safety boundary

Nothing in this repository should invoke Odin, Heimdall, `dd` to a block device, `fastboot flash`, or TWRP flashing automatically. Build and packaging are allowed; flashing is a separate, manual test step after artifact inspection and recovery planning. `scripts/validate-boot-bundle.sh` and `scripts/check-device-layout.sh` are read-only and refuse to run if a destructive command ever appears in them; the flashing commands live only in `docs/FIRST_BOOT_TEST.md`, for a human to run deliberately.
