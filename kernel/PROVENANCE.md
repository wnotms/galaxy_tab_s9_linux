# Kernel port provenance

## Upstream kernel

The build is pinned to:

- repository: `https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git`
- tag: `v7.2-rc3`
- commit: `a13c140cc289c0b7b3770bce5b3ad42ab35074aa`

`scripts/fetch-mainline.sh` refuses to continue if the checkout does not resolve to this commit.

## SM-X710 board DTS bootstrap

`kernel/dts/sm8550-samsung-gts9wifi.dts` is imported from the hardware-tested SM-X710 mainline work at:

- repository: `https://github.com/troikoss/gts9wifi-fedora`
- commit: `656d2ded8031657b60cde22e6fdfbc0b722a9dff`
- source path: `kernel/files/sm8550-samsung-gts9wifi.dts`
- source file license: BSD-3-Clause (SPDX header preserved)

The root Samsung ABL selectors in that DTS were independently cross-checked against the owner-supplied live downstream DTS (`board-id 0x04` and the four SM8550 `qcom,msm-id` pairs).

The rest of the reference port's out-of-tree drivers and patch stack are **not** bulk-imported by this bootstrap. They remain engineering references for later subsystem-by-subsystem work. This keeps the initial delta understandable and makes it clear which support has actually been integrated here.

## Sibling reference

The Samsung Galaxy Tab S9 Ultra (`SM-X910`, `gts9uwifi`) mainline repositories by `agcarbajo` are used as a secondary engineering reference for common SM8550/Samsung ABL issues. Do not copy X910-specific Goodix/WCN7850 hardware assumptions onto the X710.

## Owner-supplied stock evidence

The owner supplied a live DTB, its decompiled DTS and a stock kernel config. The live DTB/DTS hashes and extracted facts are recorded in `reference/stock/MANIFEST.md` and remain downstream hardware evidence. The **stock kernel config itself is preserved byte-for-byte** as deterministic Base64/gzip parts under `reference/stock/config/`; `scripts/materialize-stock-config.sh` reconstructs the exact original SHA-256 before it is used as the Linux 7.2 Kconfig seed. The downstream DTS is still not a drop-in upstream board description.


## Earlier SM-X710 mainline history: Azkali

An earlier direct X710 kernel fork is tracked as an engineering reference:

- repository: `https://github.com/Azkali/sm8550-mainline`
- branch: `gts9wifi-7.0`
- inspected head: `c48fedbd799a2b792a095840eeb96746afe2f327`
- Linux lineage: 7.0

The branch is not used as this repository's kernel source. Its most portable
result is commit `112203bf04d3`, which documents Samsung ABL's dependency on
the `qcom_tzlog`, `arch_timer`, and `qcom_scm` DT labels. The pinned
Linux 7.2-rc3 source was checked and still lacks those labels, so a minimal
adaptation is carried in
`kernel/patches/0001-arm64-dts-qcom-sm8550-add-samsung-abl-labels.patch`.

The Azkali branch head also contains invasive early-boot diagnostics in generic
arm64/EFI/printk/init code. Those changes are retained as debugging knowledge,
not as production patches. See `docs/AZKALI_SM8550_MAINLINE_ANALYSIS.md`.

## Boot-loop repair reference (2026-09-21)

Local sibling checkout: `../ubuntu-galaxy-tab-s9-ultra`, origin
`https://github.com/agcarbajo/ubuntu-galaxy-tab-s9-ultra`, inspected commit
`32273b0a410b3e73b20a3a2451e24260fb2a36bd`.

- `kernel/patches/ignore-console-null.patch` is copied unchanged as patch 0003.
- `configs/vendor_boot/cmdline.txt` supplies the bring-up power-retention flags.
- `scripts/build-android-v4-bundle.sh` supplies the generic-initramfs placement:
  real initramfs in init_boot, empty platform archive in vendor_boot.

The X710 board DTS, stock seed and Linux pin are unchanged. These common boot
changes do not import X910 panel, touch, Wi-Fi or fingerprint hardware.
