# SM-X710 official display source located (2026-09-22)

Owner-supplied archive: `/home/ms/Samsung/SM-X710_EUR_15_Opensource.zip`

SHA-256: `9394aa2a004198cdfee6b1dd3c1a775dfaa990a99a5bd06106cd221516486ebc`

The archive's `Kernel.tar.gz` contains both kernel_platform and vendor sources.
`README_Kernel.txt` names target `gts9wifi_eur_open` and explicitly builds
`../vendor/qcom/opensource/display-drivers/msm` as an external module.
The earlier GitHub repository's main branch at 6b78c65f0ee22f625fe0923af8270ea95ca4994c
contains common/prebuilts but not this vendor tree. Its sm-x710-actions branch
adds only build workflow/documentation/script changes relative to main.

## Files inside Kernel.tar.gz

Base: `vendor/qcom/opensource/display-drivers/msm/samsung/`

- `GTS9_ANA38407_AMSA10FA01/GTS9_ANA38407_AMSA10FA01_panel.c`:
  exact X710 panel callbacks. Line 971 defines
  `GTS9_ANA38407_AMSA10FA01_WQXGA_init`; lines 1032–1033 select the PDF_DATA
  buffer. Revision 0x04 maps to D (lines 50–52).
- `panel_data_file/GTS9_ANA38407_AMSA10FA01.dat`: readable Samsung command
  definitions, including POWER_ON_PRE_SETTING (line 2), VRR_SETTING (65),
  PM_EN_DISP_ON_DELAY (140), SLEW_BOOSTING_OFF (157), TCON_INTR_SETTING (288),
  TE_ON (353) and DSC_SETTING (379).
- `GTS9_ANA38407_AMSA10FA01/GTS9_ANA38407_AMSA10FA01_PDF.h`: embedded byte
  array containing command text; despite its name, it is not a PDF document.
- `ss_dsi_panel_common.c`: name-based registration at lines 9954–9956.
- Sibling panel.h, mdnie.h, SELF_DISPLAY and FW_UPDATE sources are also present.

Board DTS:
`kernel_platform/msm-kernel/arch/arm64/boot/dts/samsung/galaxytab/gts9wifi/gts9wifi_eur_open_w00_r04.dts`.
The matching panel node begins at line 8393; do not confuse it with the many
other panel nodes in that expanded overlay source.

## Relevance to the mainline display failure

The earlier assumption that this panel's command macros cannot be resolved is
superseded: their definitions and the Samsung parser are now available.
The exact panel data starts with SLEW_BOOSTING_OFF and PM_EN_DISP_ON_DELAY,
uses a 50 ms sleep-out delay, and later applies SLEW_BOOSTING_ON and VRR_SETTING.
Our current X910-derived initialisation differs and must be audited against
these X710 commands, including revision conditions and runtime substitutions.
A difference alone is not proof of the display failure's cause.

DSC_SETTING explicitly specifies width 2560, height 1600 and slices 1280 x 100,
and provides WT 0x07 and WT 0x0A packet data. This is direct evidence for
comparing the mainline-generated PPS and packet handling with stock; do not
blindly interpret WT packet types as DCS opcodes or copy Samsung's framework.

## Local extraction

404 regular files (display-driver subtree plus the revision-04 board DTS)
were extracted under `.work/reference-samsung/official/`, about 13.2 MB.
`extracted-manifest.json` contains individual file hashes and original paths.
The large source archive and extracted source are not committed. No driver was
changed, no build was required, and no physical test was performed for this lookup.
