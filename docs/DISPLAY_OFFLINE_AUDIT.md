# Display offline audit — 2026-09-22

Scope: source and archived-log analysis, followed by a local ccache build.
The owner explicitly paused physical testing. No device connection, flashing,
reboot or new hardware observation is part of this work.

## Test 039 cannot isolate DSC decoding

The original no-DSC working-tree diff and existing logs are archived under
`reference/boot-tests/test-039-20260921T171026Z/`. Its early report shows DRM
registration but no framebuffer and “Cannot find any crtc or sizes”. Later
serial logs contain echoes without results. Test 038's faint lines are an
owner observation, not proof of valid frame transfer or a DSC decoder fault;
CTL start and vblank were still timing out.

In the pinned source, `drivers/gpu/drm/msm/dsi/dsi_host.c` computes the
uncompressed pixel clock from mode.clock, including blanking, and byte clock
as pixel clock * 24 / (8 * 4). `dsi_manager.c:dsi_mgr_bridge_mode_valid()`
rejects clocks exceeding the available OPPs. The inherited SM8550
`mdss_dsi_opp_table` tops out at 358000000 Hz; the board does not override it.

| Mode | DRM clock, kHz | RGB888 byte clock, Hz | DSC byte clock, Hz |
| --- | ---: | ---: | ---: |
| 60 Hz (3403 x 2496 total) | 509633 | 382224750 | 190606935 |
| 120 Hz (2692 x 1738 total) | 561443 | 421082250 | 154229976 |

Both uncompressed modes exceed that limit. The no-DSC test therefore cannot
reach the intended scanout through the normal mode-validation path. The DSC
values apply the host's horizontal-active compression calculation (ceil of
2560 / 3 = 854), with the same integer truncation as the driver. They fit the
OPP ceiling; that alone does not validate panel timing or decoding. Do not
raise the OPP limit or invent panel timings to make this diagnostic pass.

The panel now defaults to DSC and prefers the stock 120 Hz mode. The retained
`panel_samsung_ana38407.dsc=0` boot parameter is diagnostic only: it offers the
60 Hz experiment and warns that the current OPP table rejects it. The
parameter is read-only after load. Initialisation explicitly programs the
DDIC compression state from the same dsi->dsc pointer attached to the host,
and sends PPS only when compression is enabled. This avoids a runtime toggle
or reset turning the host and DDIC into mismatched producers/consumers.

## Patch 0005 starts too early

The original patch's rationale conflates CRTC atomic_flush with KMS
flush_commit. The pinned code orders the normal path as follows:

1. `msm_atomic.c:msm_atomic_commit_tail()` calls commit_modeset_disables,
   commit_planes and commit_modeset_enables.
2. Virtual encoder enable calls physical enable, then resource control and
   `_dpu_encoder_virt_enable_helper()` (including vsync source selection).
3. After modeset enables, MSM calls KMS flush_commit, which reaches
   `dpu_kms_flush_commit()` -> `dpu_crtc_commit_kickoff()`.
4. That calls `dpu_encoder_prepare_for_kickoff()` (including
   `dpu_encoder_prep_dsc()`) before `dpu_encoder_kickoff()`.

The extra physical-enable trigger in 0005 precedes steps 2–4 and increments
pending state in addition to the normal kickoff. It is not a justified fix
for missing first-frame submission. It is retained in `kernel/patches/pending/`
for attribution but excluded from the build. The generated source worktree
was explicitly reverse-patched before building; simply moving a patch would
leave stale code in a reused worktree.

This corrects the source ordering; it does not prove why test 037 reported a
disabled encoder or prove that dropping 0005 fixes the screen.

## Remaining investigation

Keep fb blank-cycle recovery, the stock DSC geometry and the existing DCS
sequence for now. When physical testing is authorized again, first trace the
normal kickoff, encoder state, pending counters and CTL/PP/read-pointer IRQs
across initial enable and the blank cycle. Determine whether a frame completes
before interpreting a partial picture as a decoder fault. TE routing/polarity
and the X910-derived DDIC register sequence remain unverified hypotheses.
A controlled follow-up should retain DSC and avoid changing timings together
with transfer sequencing. No physical test has been scheduled or run here.

## Offline validation

- `USE_CCACHE=1 BUILD_MODULES=0 JOBS=16 ./scripts/build-kernel.sh`: passed,
  kernel image and board DTB built. Cache: `/home/ms/.cache/ccache`.
  The first attempt hit the earlier read-only cache permissions; the completed
  build ran after the owner changed permissions. No module build was requested.
- `python3 -m unittest discover -s tests -v`: all three tests passed after
  correcting the pre-existing host test's stale init-loop extraction marker.
- Archived test 039 SHA256SUMS: all files verified.
- `git diff --check`: passed.
- Generated `dpu_encoder_phys_cmd.c` matches the pristine upstream file;
  the panel overlay matches the repository source. Patch 0005 is not applied.
- Existing stock-seed Kconfig conversion warnings (BASE_SMALL and the two
  BOOTPARAM panic options) remain; required built-in/module assertions passed.
- No boot bundle was repackaged, no modules deployed, and no hardware tested.
  Existing `out/boot-bundle` files are older artifacts, not this kernel build.

Kernel output (`out/kernel-gts9wifi/SHA256SUMS`):

```text
ec32c2148e106b3b7b4465d55330fb71a6c63f4c115e39b13d8ceaf3bc79704d  Image.gz
65bee98035c03b899ad0096b13eafca433494dfb6358f113dc2c1c283c4fd609  sm8550-samsung-gts9wifi.dtb
07179e0f5d5b23cfb81823b2aa4f3653231e9c341ef9e1c693bea08f25cda246  config
b3f154357931f9e2ddce4bd3b37facae84a69e93a280dbb9bb877f7c824d5658  kernel.release
```

Build transcript: `.work/build/display-offline-build.log` (local generated log).

