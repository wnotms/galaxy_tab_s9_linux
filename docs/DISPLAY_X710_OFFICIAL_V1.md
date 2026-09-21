# Official X710 display candidate v1 — 2026-09-22

Status: offline candidate, not physically tested. Source archive and exact
paths are documented in `SM_X710_OFFICIAL_DISPLAY_SOURCE.md`. The hardware
observed ID 80 00 04 selects revision D in Samsung's panel driver. This
candidate targets that revision and the stock 120HS timing.

## Driver changes

- Replace the inherited X910 VBP write with X710 SLEW_BOOSTING_OFF and the
  complete PM_EN_DISP_ON_DELAY sequence, including indirect register 0x1435.
- Use the stock revision-C+ sleep-out delay of 50 ms.
- Remove X910's B9 offset 0x0e = 0x15 from TSP sync: the official X710 block
  only writes B9 offset 0x0b = 0xcc.
- After SP_SETTING, wait 20 ms, restore SLEW_BOOSTING_ON and explicitly select
  120HS: 0x60 = 0, DD offset 0x13 = 0, B9 offset 0x10 = 80 00 00 00.
- Advertise only 2560x1600 at 120 Hz. A 60 Hz mode requires coordinated DDIC
  VRR/GLUT changes that a fixed panel init cannot supply. Remove the no-DSC
  diagnostic parameter: the existing uncompressed modes exceed the DSI OPP
  table and are not a usable fallback (see DISPLAY_OFFLINE_AUDIT.md).
- Correct physical dimensions from the inherited X910 313 x 196 mm to the
  X710 DTS's 236 x 148 mm.

Power rails, reset timing, ID/cell-ID diagnostics, blank-cycle recovery and
separate display-on in enable retain their existing behavior. The retired
premature CTL kickoff patch remains excluded. Do not attribute any future
change in behavior solely to DSC; it was already enabled in the prior candidate.

This is a targeted power-on/sync correction, not a full Samsung brightness
stack. Adaptive GLUT, ACL, ELVSS temperature policy, mdnie, HBM FlatZ and the
vendor dynamic-refresh callbacks are not imported. Normal brightness retains
the existing 0x53/0x51 path; existing FOD controls are not validated by this work.
Other panel revisions and 60 Hz operation are not validated. A full match to
all stock brightness commands is not claimed.

## DSC comparison

Samsung's parser (`ss_wrapper_common.c`, around line 2128) interprets WT's
first value as the DSI packet type. Thus WT 0x07 enables compression and
WT 0x0a carries PPS; neither is a DCS register write. The existing MIPI helper
API calls are retained.

The host test compiles the repository's actual panel init/template, the pinned
MSM `dsi_populate_dsc_params()` and the DRM DSC helper functions. Generated PPS
matches all 88 bytes supplied by the stock DSC_SETTING. The remaining 40 bytes
of the standard 128-byte packet are zero/reserved. No DSC geometry, RC table,
PPS packet length or upstream calculation was changed. This comparison does
not establish correct physical transport, timing or full-frame scanout.

## Validation

- ccache kernel/DTB build passed:
  `USE_CCACHE=1 BUILD_MODULES=0 JOBS=16 ./scripts/build-kernel.sh`.
- Six host tests passed, including stock power/sync command order, exact PPS
  bytes, and injected transport failures at early/middle/last writes. Test
  transport records output only; it never connects to a tablet.
- Kernel conversion retains the existing stock-seed Kconfig warnings; required
  config checks passed. No module build was requested.
- Build log: `.work/build/display-x710-official-build.log`.
- No device access, flashing, reboot, or hardware success claim.

Kernel artifact hashes:

```text
a304ebef1051cd02d485d16db0a1ae4382d68953e50e6abd1e84c7e37385433f  Image.gz
65bee98035c03b899ad0096b13eafca433494dfb6358f113dc2c1c283c4fd609  sm8550-samsung-gts9wifi.dtb
07179e0f5d5b23cfb81823b2aa4f3653231e9c341ef9e1c693bea08f25cda246  config
b3f154357931f9e2ddce4bd3b37facae84a69e93a280dbb9bb877f7c824d5658  kernel.release
```

## Packaged candidate

A fresh initramfs was built from the current repository, and the candidate was
packaged separately under `out/boot-bundle-x710-official/`.
`validate-boot-bundle.sh --dir out/boot-bundle-x710-official` passed, including
kernel/DTB contents, initramfs entrypoint, AVB footers, layout and image hashes.
Build/validation logs are `.work/build/display-x710-initramfs.log`,
`display-x710-bundle.log` and `display-x710-validation.log`.
This is a local package only; physical testing remains paused.

Bundle manifest:

```text
27752545b2d1155ce1072bccc89c3c0c6fd1d63d6db55c739439d415eccd23cf  boot.img
c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3  dtbo.img
417cf0706a9be83223ec33a1a8093f8b7d0941ed003460d28700c00a308c4707  init_boot.img
90b3e4ba83e01dea90e8c91bfb203bb0dd84c71172444b45ec1336ef84f7ca64  initramfs-bringup.img
b95e5ef931fbe588f8574c06331db56ae906b1ac91ed73204704b35cb220b3d4  vbmeta.img
c1749463bffdaddc816cba5584dfd6fe9a98c4b747db802c8e9d28f5ce07de49  vendor_boot.img
```
