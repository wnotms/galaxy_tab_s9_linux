# Test 034 — the DisplayPort controller is the second blocker (2026-09-21T15:53:xxZ)

Test 033 left `ae90000.displayport-controller` in the deferred list, and on
mainline the DP is one of the components the msm DRM master waits for — so it is
disabled here, on the grounds that a panel console does not need it and
`qcom,defer-hpd-until-first-resume` (which our DTS carried from the SM-X910 port)
is not a mainline property.

Artifacts: `vendor_boot aacde925…` (DTB only), `boot 013ffa94…`.

## Result: DP out of the way, GPU still blocks

The deferred list no longer mentions the DP controller, `msm_dpu` and `msm_dsi`
both bind (`ae01000.display-controller`, `ae94000.dsi`) — but the card still does
not appear, and the report shows the same GPU failure as test 033.  So the DP was
one blocker and the missing Adreno firmware is the other.

The owner also reported the screen went black during this run: the DSI host is
now being programmed by the kernel, which takes the panel away from the
bootloader's splash and leaves it dark because the DRM card never came up.
