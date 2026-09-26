# Local patch queue

This directory starts intentionally small. `scripts/prepare-kernel.sh` applies every `*.patch` here in lexical order with `git apply --check` before applying it.

There are three distinct patch locations:

- `kernel/patches/*.patch` is the default queue applied by the build script.
- `kernel/patches/diagnostic/` keeps temporary measurements for manual,
  one-off use. The prepare script ignores this directory.
- `kernel/patches/pending/` keeps experiments and candidates that are retired,
  rejected, unnecessary, or still unresolved. They are not build candidates
  until new evidence justifies a separate change.

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
- `0004-drm-panel-add-samsung-ana38407.patch` — Kconfig/Makefile integration
  for the SM-X710 panel overlay driver.
- `0006-input-add-samsung-pogo-keyboard.patch` — Kconfig/Makefile integration
  for the EF-DX710 pogo keyboard overlay driver
  (`kernel/drivers/keyboard-samsung-pogo.c`, installed by
  `scripts/prepare-kernel.sh`). That driver is a native protocol port of
  Samsung's GPLv2 `stm32_pogo_*_v3` sources in the X710 open-source archive;
  the firmware-update, raw-register and DFU surfaces are deliberately not
  exposed.
- `nxp-ptn3222-apply-dt-register-overrides.patch` — repeater register overrides
  used by the board's USB bring-up.

Numbers in this directory are unique and are not reused from `pending/`, which
keeps the historical `0005-*` names because the display documentation refers to
them: `0005` was the retired command-mode kickoff patch, so the keyboard is
`0006`.

`0009` was the second half of the keyboard A/B: the Kconfig/Makefile wiring that
makes the imported `samsung-pogo/` directory selectable. It has been retired,
because `scripts/prepare-kernel.sh` installs that directory and inserts both
lines itself, so the patch had become a duplicate of the script and would have
conflicted with it. The number is not reused.

The former default `0005` early command-mode kickoff patch is now held in
`pending/`: the pinned MSM path already kicks off after modeset enable, while
that patch triggers before resource/vsync/DSC preparation. See
[the offline display audit](../../docs/DISPLAY_OFFLINE_AUDIT.md).

`0008-i2c-qcom-geni-log-bus-lines-on-error.patch` is diagnostic-only and lives
in `diagnostic/`. It was used to distinguish an address NACK from a non-idle
GENI bus while bringing up the keyboard. The normal Pogo path now works without
this instrumentation, so it is not applied to the default kernel. To reproduce
that measurement on a disposable prepared kernel worktree, run
`git -C <worktree> apply <repo>/kernel/patches/diagnostic/0008-i2c-qcom-geni-log-bus-lines-on-error.patch`
after `scripts/prepare-kernel.sh`, then rebuild. A subsequent prepare restores
the pinned source before applying the default queue.

`0010-pinctrl-report-pogo-pin-state-at-probe.patch` is also diagnostic-only in
`diagnostic/`. It sampled TLMM registers and rescheduled itself every 30 seconds
while investigating GPIO ownership. The Pogo driver's GPIO and IRQ paths do not
consume those samples; the patch only read and logged MMIO state. To reproduce
that measurement, manually apply it to a disposable prepared worktree as shown
in `diagnostic/README.md`.
- `0008-power-sequencing-qcom-wcn-send-aop-wlan-pdc-votes.patch` — sends the
  `qcom,wlan-pdc-init` AOP votes through the QMP mailbox and cold-resets
  `wlan-enable` on WCN6855/WCN7850, so the chip's PMU completes its power
  handshake and its PCIe receivers are detected on the SM-X710. Adapted from
  `gts9wifi-fedora-linux` (`kernel/patches/wcn7850-pwrseq-cold-reset-aop.patch`,
  commit `ab123e7`), a downstream port for this same device; not upstream, and its
  on-device verification is recorded under `reference/boot-tests/`. The helper is
  chip-generic and is a candidate for upstream submission once measured.
- `0010-remoteproc-qcom-q6v5-quiet-the-repeated-handover.patch` — one line:
  `dev_err()` → `dev_dbg()` for the already-issued branch of the ADSP handover
  interrupt. The interrupt is level-triggered and the ADSP keeps it asserted, so
  the message repeats ~5.4 times a second; on the Fedora port for this same board
  it was measured at 37,402 of 37,411 dmesg lines (99.98 %), which evicts every
  real diagnostic from the ring. Taken from `gts9wifi-fedora-linux`
  (`kernel/patches/quiet-adsp-handover-already-happened.patch`), where it is
  issue 19; the port enables the same `&remoteproc_adsp`, so it hits the same
  repeat. No behaviour change — the interrupt is handled identically.

## Retired from the default queue

`0003-printk-allow-ignoring-samsung-console-null.patch` moved to `pending/` on
2026-09-26. It existed so the X710 bring-up consoles could survive the
`console=null` that Samsung's ABL appends; with the serial debug consoles removed
from the command line there is nothing left for that argument to displace, and
the appended request is now absorbed by an upstream `CONFIG_NULL_TTY=y` instead.
Dropping it also returns `kernel/printk/printk.c` to unmodified upstream, which
is one less local change to core printk. See
[the boot console block](../../docs/BOOT_CONSOLE_BLOCK.md).
