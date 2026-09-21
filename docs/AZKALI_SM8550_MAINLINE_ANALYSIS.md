# Analysis of Azkali/sm8550-mainline gts9wifi-7.0

This note records what is useful from Azkali's Samsung Galaxy Tab S9 11-inch
(`SM-X710 / gts9wifi`) branch and, equally importantly, what should not be
blindly carried into this repository.

## Reference snapshot

- repository: `https://github.com/Azkali/sm8550-mainline`
- branch: `gts9wifi-7.0`
- branch head inspected: `c48fedbd799a2b792a095840eeb96746afe2f327`
- base lineage: Linux 7.0
- important X710 commits:
  - `048ac714a92a` — initial SM-X710 DTS
  - `b7652aa88cca` — Tab S9 board support/config integration
  - `f99b39eaac60` — substantial DTS cleanup/fixes
  - `112203bf04d3` — Samsung ABL DTBO-label fix
  - `c48fedbd799a` — Gunyah watchdog + framebuffer boot-stage diagnostics

## What is directly useful

### 1. Samsung ABL DTBO labels

Commit `112203bf04d3` is the most portable result in the branch.

It records that Samsung ABL expects these labels in the SM8550 base DTB:

- `qcom_tzlog` on `/chosen`
- `arch_timer` on the ARM timer node
- `qcom_scm` on the SCM node

The commit also records `qcom_scm` as relevant to warm-reset boot behavior.
The pinned Linux 7.2-rc3 source used by this repository was checked and still
does not contain those labels. Therefore this repository carries the minimal
port of that change as:

`kernel/patches/0001-arm64-dts-qcom-sm8550-add-samsung-abl-labels.patch`

This patch is preferable to modifying the X710 board DTS because the labels
belong to nodes defined by `sm8550.dtsi`, and Samsung's overlay tooling looks
for the base-DTB symbols.

### 2. Boot-stage diagnostics as a troubleshooting technique

Commit `c48fedbd799a` contains an aggressive but informative debugging method:

- paint known colors directly into the preserved Samsung framebuffer from very
  early arm64 assembly;
- pet a Gunyah-virtualized watchdog while early kernel init is running;
- place later progress markers in `setup_arch()`, EFI init and `start_kernel()`;
- embed the X710 DTB into the kernel for experiments where ABL DT handoff is
  itself under suspicion.

This is useful as a **last-resort diagnostic design**, especially when serial,
pstore and normal printk are unavailable. It is not appropriate for the default
kernel because it changes generic arm64 entry code, printk, idle, EFI and init.

If a future physical test shows that ABL enters Linux but no conventional log
survives, reproduce the technique as an optional diagnostic patch series on a
separate branch. Do not mix it into normal hardware enablement commits.

### 3. Independent X710 bring-up history

The branch is useful for understanding which SM8550 areas were investigated:
UFS, PCIe/WLAN, Bluetooth UART, USB-C/PS5169, display, audio, reserved memory,
GPU, remoteproc and early-boot memory layout. Its generated
`gts9wifi_defconfig` also confirms many expected mainline foundations such as
PSTORE, GENI console, MSM DRM, UFS QCOM, SDHCI MSM, ath11k and QCA HCI UART.

These are cross-checks only. This repository keeps the owner-extracted Samsung
5.15.153 config as the immutable configuration seed and resolves it through
Linux 7.2 `olddefconfig`.

## What should NOT be imported wholesale

### Final DTS is not authoritative for this tablet

The later Azkali DTS still contains assumptions that conflict with the
owner-extracted SM-X710 evidence already recorded in
`reference/stock/MANIFEST.md`. Examples include a Goodix GT9916 touchscreen,
while the supplied stock tree identifies STM FTS1BA90A, and a generic
WCN7850-PMU compatible used around QCA6490/WCN6855-class radio plumbing.

The current DTS in this repository comes from the later SM-X710 work in
`troikoss/gts9wifi-fedora` and was cross-checked against the owner's live
downstream tree. Keep that as the main board baseline unless physical evidence
shows a regression.

### Diagnostic memory declarations are not a production memory map

The Azkali branch used a conservative hard-coded `memory@a0000000` 512 MiB
window, a simple-framebuffer node, explicit splash/reserved ranges and later
direct framebuffer painting. Those choices are understandable during early boot
bisecting but should not replace a memory map validated from the actual X710
bootloader handoff and `/proc/iomem`.

### Do not cherry-pick the final branch as a kernel fork

The branch head contains device-specific modifications in generic files such as:

- `arch/arm64/kernel/head.S`
- `arch/arm64/kernel/idle.c`
- `arch/arm64/kernel/setup.c`
- `drivers/firmware/efi/efi-init.c`
- `kernel/printk/printk.c`
- `init/main.c`

Those changes are excellent forensic clues, but carrying them permanently would
make rebasing and upstreaming much harder.

## Decision for this repository

Adopt now:

1. the Samsung ABL DTBO labels patch;
2. the documented diagnostic lessons;
3. Azkali as a pinned engineering reference in provenance/agent guidance.

Do not adopt by default:

1. Azkali's full generated defconfig;
2. its final board DTS over the current later X710 baseline;
3. the Gunyah watchdog SMC hooks;
4. embedded-DTB/head.S framebuffer paint code;
5. hard-coded diagnostic memory sizing.

This keeps the project mainline-first while preserving the most valuable
Samsung-specific boot knowledge from the earlier X710 effort.
