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

`snps-eusb2-match-samsung-sm8550-init.patch` was taken back out of this
directory for test 021: test 020 got the gadget as far as the host seeing
`VID_0525&PID_A4A7` with a `MI_00` control interface, but no data interface, so
the COM port cannot be opened.  That is precisely the symptom the port wrote
the patch for (`the host cannot read its USB descriptor`).
