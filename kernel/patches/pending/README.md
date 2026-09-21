# Patches held back from the default build

`prepare-kernel.sh` applies `kernel/patches/*.patch` and ignores subdirectories,
so anything in here is deliberately *not* applied.

## Why these two are here

Both came from the SM-X910 port (agcarbajo/ubuntu-galaxy-tab-s9-ultra) and were
applied for test 019 together with the PDC config fix.  That test was cut short
by hand, so it could not say whether they helped or hurt.

Test 020 carried the PDC fix alone and answered the question for the UFS patch:
UFS enumerates without it (`host0 -> 1d84000.ufshc`, `sda`..`sdf` with every
partition), because what UFS was really waiting for was the PMIC side that the
PDC unlocked.  The UFS patch is therefore not needed on this board and stays
here - kept because the reasoning may still matter for suspend/resume.

`snps-eusb2-match-samsung-sm8550-init.patch` was tried in test 021 and **broke
USB on this board**: with it, no gadget appears on the host at all (test 020,
without it, at least reached a host-visible `VID_0525&PID_A4A7` with its control
interface).  Samsung's CPBIAS=1 plus the post-POR delay is the right sequence
for the X910's PHY configuration, not for this one, so it stays here.

The gadget's missing data interface is instead the PTN3222 redriver, which no
upstream driver programs: see `nxp-ptn3222-apply-dt-register-overrides.patch`,
now in `kernel/patches/`.

## Premature command-mode kickoff (0005)

`0005-drm-msm-dpu-start-command-mode-at-enable.patch` is retained as historical
evidence but removed from the default build after the offline audit on
2026-09-22. Its explanation confuses CRTC atomic_flush with the MSM KMS
flush_commit. In the pinned source, msm_atomic_commit_tail() invokes
commit_modeset_enables() before flush_commit(), which reaches
dpu_crtc_commit_kickoff() -> dpu_encoder_kickoff().

The extra trigger in physical encoder enable runs before the virtual encoder's
resource control and vsync setup, and before the normal kickoff's preparation
(including DSC setup). It also adds another pending count. Test 038's partial
screen observation does not establish this as a correct fix. Do not re-enable
it without tracing the normal commit path. See docs/DISPLAY_OFFLINE_AUDIT.md.
