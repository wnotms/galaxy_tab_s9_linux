# Patches held back from the default build

`prepare-kernel.sh` applies `kernel/patches/*.patch` and ignores subdirectories, so
anything in here is deliberately *not* applied. Keep it that way: every candidate below
was fitted on hardware, and every one of them has a recorded outcome. This directory is
the attribution record for work that was done and set aside - not a queue of pending
work, and not a place to re-enable something without a new measurement.

The default queue is unchanged and contains none of these:

```
0001-arm64-dts-qcom-sm8550-add-samsung-abl-labels.patch
0002-soc-qcom-hook-x710-sec-log-into-kbuild.patch
0003-printk-allow-ignoring-samsung-console-null.patch
0004-drm-panel-add-samsung-ana38407.patch
0006-input-add-samsung-pogo-keyboard.patch
nxp-ptn3222-apply-dt-register-overrides.patch
```

Note that `0008` also touches `drivers/i2c/busses/i2c-qcom-geni.c`, but it is only the
NACK/timeout bus-line logging patch - it is not the SE re-arm below.

## Dispositions

| Patch | Disposition |
| --- | --- |
| `qmp-ufs-clear-tx-pull-down-on-power-on.patch` | NOT NEEDED FOR NORMAL BOOT - POSSIBLY USEFUL FOR SUSPEND, UNRESOLVED |
| `snps-eusb2-match-samsung-sm8550-init.patch` | REJECTED ON X710 |
| `0005-drm-msm-dpu-start-command-mode-at-enable.patch` | RETIRED |
| `0005-drm-msm-dsi-quiesce-x710-phy-before-enable.patch` | RETIRED |
| `0005-drm-msm-dsi-cycle-x710-link-before-panel.patch` | RETIRED |
| `0007-i2c-qcom-geni-rearm-se-before-transfers.patch` | NOT NEEDED |

## UFS TX pull-down - NOT NEEDED FOR NORMAL BOOT, suspend angle UNRESOLVED

`qmp-ufs-clear-tx-pull-down-on-power-on.patch` came from the SM-X910 port
(agcarbajo/ubuntu-galaxy-tab-s9-ultra) and was carried in test 019 together with the PDC
config fix. That run was cut short by hand, so it could not say whether the patch helped
or hurt.

Test 020 carried the PDC fix alone and answered the question: UFS enumerates without the
patch (`host0 -> 1d84000.ufshc`, `sda`..`sdf` with every partition present), because what
UFS was really waiting for was the PMIC side that `CONFIG_QCOM_PDC` unlocked. See
`reference/boot-tests/test-020-20260921T140306Z/README.md`.

May be revisited **only** for suspend/resume, and only against a specific measured
failure that traces to the bootloader-inherited TX pull-down bit. Be precise about the
evidence status: no UFS suspend/resume test has ever been run on this board, so the
suspend angle here is an untested hypothesis, not a result.

## Samsung eUSB2 init - REJECTED

`snps-eusb2-match-samsung-sm8550-init.patch` was tried in test 021 and broke this board.
With it the kernel never reached userspace and no gadget appeared on the host at all,
where test 020 with the same kernel minus this patch produced a host-visible
`VID_0525&PID_A4A7`. Samsung's CPBIAS=1 plus the post-POR delay is the right sequence for
the X910's PHY configuration and wrong for this one. See
`reference/boot-tests/test-021-20260921T141444Z/README.md`.

Do not re-apply it. The gadget's missing data interface was a separate problem and is
fixed by `nxp-ptn3222-apply-dt-register-overrides.patch`, which is in the default queue.

## Premature command-mode kickoff - RETIRED

`0005-drm-msm-dpu-start-command-mode-at-enable.patch` is retained as historical evidence
only. Its premise is wrong: it conflates CRTC `atomic_flush` with the MSM KMS
`flush_commit`. In the pinned source `msm_atomic_commit_tail()` runs
`commit_modeset_enables()` before `flush_commit()`, which reaches
`dpu_crtc_commit_kickoff()` -> `dpu_encoder_kickoff()`.

The extra trigger in physical encoder enable therefore runs before the virtual encoder's
resource control and vsync setup and before the normal kickoff's preparation, including
DSC setup, and it adds a second pending count. Test 038's partial-screen observation does
not establish it as a correct fix. Do not re-enable it without tracing the normal commit
path. See `docs/DISPLAY_OFFLINE_AUDIT.md`.

## First-enable DSI candidates - RETIRED

Two candidates tried to remove the framebuffer blank cycle from the panel's cold-boot
recovery by fixing the first enable instead. Both failed, and both keep the `0005-` prefix
they were written with.

- `0005-drm-msm-dsi-quiesce-x710-phy-before-enable.patch` (test 041) quiesces the
  inherited PHY lanes before enable. The first ID was still `00 00 00` at 5.391 s and only
  the blank cycle recovered `80 00 04` at 7.953 s, so lane quiesce alone is not the
  missing step. See `reference/boot-tests/test-041-20260922T001026Z/README.md`.

- `0005-drm-msm-dsi-cycle-x710-link-before-panel.patch` (test 042) runs the normal
  host/PHY off path once before the initial panel prepare. It executed at 5.373 s and the
  ID was still zero at 5.514 s; the blank cycle recovered `80 00 04` at 8.033 s. That
  disproves the claim that powering down the inherited host/PHY before panel prepare is
  sufficient. See `reference/boot-tests/test-042-20260922T001407Z/README.md`.

  **Citation correction:** an earlier revision of this file attributed the link-cycle
  patch to "test 042/043" and quoted test 043's numbers (5.586 s, 5.880 s, 8.486 s).
  Test 043 did not build this patch - it had already been moved to `pending/` by then
  (commit `aede820`) and carried a DDIC sleep/reset retry in the panel driver instead.
  Test 042 is the evidence for this patch.

Which part of the modeset teardown the blank cycle performs is still not isolated; that
remains an open question, and it is the reason the recovery is a documented workaround
rather than a fix.

The recovery itself now runs early and without fixed sleeps (de7bd2b, verified in test
044), so the blank cycle costs a few seconds rather than the 120 s of the original
suspend/resume workaround.

## GENI SE re-arm - NOT NEEDED

`0007-i2c-qcom-geni-rearm-se-before-transfers.patch` implements the vendor's
`samsung,reset-before-trans` property by replaying the tail of the serial-engine firmware
load before every transfer. It is correct and harmless - test 045 fitted it and the
transfers completed normally - but it is not the missing piece: the pogo keyboard's MCU
did not answer with it either. See
`reference/boot-tests/test-045-20260922T004902Z/README.md`.

The premise was later refuted outright, which is the stronger reason not to bring it back:
neither `samsung,reset-before-trans` nor `samsung,stop-after-trans` has a consumer
anywhere in the vendor tree, and the stock kernel that drives the keyboard correctly
ignores them too. See `docs/GENI_TRANSFER_DIFF.md`, `docs/MAINLINE_VS_STOCK_POGO.md` and
tests 058/061. The board node no longer carries the property, so reusing this patch would
mean re-adding a property that nothing reads.

The first version of the patch called `geni_load_se_firmware()`, which cannot work on
SM8550: no node in the SoC tree sets `firmware-name`, so it returns `-EINVAL` and every
transfer failed with `-22` until it was rewritten. Keep that in mind if the idea is ever
revived - the failure mode looked like a bus NACK and was not one.
