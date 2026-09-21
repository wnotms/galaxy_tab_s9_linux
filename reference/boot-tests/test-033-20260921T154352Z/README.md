# Test 033 — first display attempt: pipeline enabled, panel driver ported (2026-09-21T15:43:52Z)

The display is the last piece mainline lacks for this board: it has
`qcom,sm8550-mdss`, `qcom,sm8550-dpu`, `qcom,sm8550-dsi-ctrl` and
`qcom,sm8550-dsi-phy-4nm` already, but no driver for the AMSA10FA01 panel, so
the screen stays dark and the kernel console has nowhere to go.

This run is the attempt:

- `kernel/drivers/panel-samsung-ana38407.c` — the SM-X910 port's driver for the
  same ANA38407 DDIC, re-targeted to this panel (mode timings `wqxga120hs` /
  `wqxga60hs` and the DSC geometry 2560x1600 / two 1280x100 slices, both taken
  from this tablet's own stock DTBO; compatible
  `samsung,ana38407-amsa10fa01`).  The DCS init/exit sequences are DDIC-level and
  carried over: the bootloader reports `lcd_id=0x800004` and the driver expects
  exactly 0x80 0x00 0x04.
- `kernel/patches/0004-drm-panel-add-samsung-ana38407.patch` wires it into
  `drivers/gpu/drm/panel/`, and `prepare-kernel.sh` now installs `panel-*.c`
  overlays there instead of into `drivers/soc/qcom/`.
- The board DTS enables `&mdss` and `&mdss_dsi0` and removes the
  `/chosen` simple-framebuffer: fbcon binds the first registered framebuffer, and
  the splash node would claim it before the msm driver probes.

Artifacts: `boot bf1c841f…`, `vendor_boot f12d196f…` (the DTB changed),
`init_boot d43750a0…` unchanged.

## Result: pipeline builds and probes, but no DRM card

`msm-mdss`, `msm_dpu`, `msm_dsi`, `msm_dsi_phy` and `disp_cc-sm8550` all
registered and the panel node is in the live device tree, but
`/sys/class/drm/` held only `version` and `/proc/fb` was empty.

The report showed why in two steps:

- `disp_cc_mdss_mdp_clk_src: rcg didn't update its configuration` with a stack
  through `disp_cc_sm8550_probe` — a secondary symptom that turned out not to be
  the blocker;
- `msm_dpu ae01000.display-controller: failed to bind 3d00000.gpu (ops
  a3xx_ops): -22` and `adev bind failed: -22` — **the Adreno GPU is a component
  of the msm DRM master**, and with no GPU firmware in this initramfs it fails,
  which fails the whole card.
