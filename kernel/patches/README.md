# Local patch queue

This directory starts intentionally small. `scripts/prepare-kernel.sh` applies every `*.patch` here in lexical order with `git apply --check` before applying it.

Add a patch only when one of these is true:

1. it is a backport of an upstream fix needed by the pinned kernel;
2. an SM-X710 hardware quirk is not yet upstream and cannot be expressed in DTS;
3. an out-of-tree driver integration needs a minimal Kconfig/Makefile hook.

Prefer one purpose per patch. Record origin/upstream status in the patch header or commit message. Do not copy Samsung's downstream driver tree wholesale.


## Current queue

- `0001-arm64-dts-qcom-sm8550-add-samsung-abl-labels.patch` — carries the
  minimal Samsung ABL DTBO symbol compatibility identified in
  Azkali's SM-X710 work. Re-check and drop it once the pinned upstream
  `sm8550.dtsi` contains equivalent `qcom_tzlog`, `arch_timer`, and
  `qcom_scm` labels.
- `0002-soc-qcom-hook-x710-sec-log-into-kbuild.patch` — adds
  `CONFIG_SAMSUNG_GTS9WIFI_SEC_LOG` and its `drivers/soc/qcom/Makefile` hook
  for the out-of-tree persistent console. The driver source stays readable as
  `kernel/drivers/samsung-gts9wifi-sec-log.c` and is installed next to the
  board DTS by `scripts/prepare-kernel.sh`. Drop both once an equivalent
  console exists upstream.
- `0003-printk-allow-ignoring-samsung-console-null.patch` — the reference
  X910 port's opt-in `ignore_console_null` early parameter. The X710 ABL logs
  also show `console=null`; use it to retain the requested bring-up consoles.

- `0004-drm-panel-add-samsung-ana38407.patch` — Kconfig/Makefile integration
  for the SM-X710 panel overlay driver.
- `nxp-ptn3222-apply-dt-register-overrides.patch` — repeater register overrides
  used by the board's USB bring-up.

The former default `0005` early command-mode kickoff patch is now held in
`pending/`: the pinned MSM path already kicks off after modeset enable, while
that patch triggers before resource/vsync/DSC preparation. See
[the offline display audit](../../docs/DISPLAY_OFFLINE_AUDIT.md).
