# Test 023 — the power-off proof is armed again (2026-09-21T14:28:5xZ)

One change in `/init`: the telemetry/proof block was moved back in front of the
infinite shell loops, where it can actually run.  Tests 019-022 never armed it,
which is why the tablet sat at the logo instead of switching itself off.

Artifacts: `boot aac25c70…` (unchanged from test 022), `init_boot bfb9631f…`,
`vendor_boot 139e0f5d…`.

## Result

The gadget did **not** appear on the host this time (a 2-second-resolution
watcher saw nothing for 11 minutes), where test 022 - same kernel - got a
host-visible device.  That is the flakiness that points at the physical link
rather than at the descriptors, and it is why the PTN3222 override values
matter.  The report and the power-off behaviour are read back from the card.
