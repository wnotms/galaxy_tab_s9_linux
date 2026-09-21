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
