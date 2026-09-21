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
