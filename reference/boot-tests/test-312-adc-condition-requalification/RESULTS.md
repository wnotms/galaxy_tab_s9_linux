# Test312 — offline ADC condition requalification

Verdict: **OFFLINE_ADC_CONDITION_WITH_ACCEPTED_ORDINARY_RECOVERY_QUALIFIED**.
Physical deployment: **not executed**. Device retains accepted Test311 candidate
boot45f6c912. No reboot, register operation, PPS request or pump activation.

The unmodified vendor-backed diagnostic introduced in Test305 is now compiled
with the ordinary-program recovery driver accepted in Test311. Compared with
accepted308/311, the sole resolved-config change is
CONFIG_SM5440_ADC_CONDITION_TEST:n -> y. Unexpected config delta:empty. DTS/DTB
byte-identical. CONFIG_HVC_DCC=n; USER_NS/mqueue/container config, SM5714/ADC5Gen3,
4.44V float, thermal and fixed5/9V current ceilings remain unchanged. No source,
TCPM, USB/gadget/adbd/rootfs policy modification. It remains one pump-OFF
conversion/bit7-only ENHIZ experiment with exact cleanup and no companion/grant.

Standard eight-job ARM64 Image/DTB/modules build exit0,89.526s.
The36 affected actual-C/profile tests PASS,1.651s,
zero failure/error/skip. Tests cover ADC transaction bounds/I2C failures/uncertain
writes/restore/cancel/lifecycle and the accepted ordinary recovery. Prior unchanged
qualification reused; no redundant full suite or Actions. Source overlays10 match
158d0dd3; protected files96 unchanged;181 exact paired modules archived and checked.
Embedded config matches resolved config; config diff and all artifact hashes saved.

Changed diagnostic object W=1/sparse exit0,8.221s. Object
and vmlinux hashes unchanged by the check. No changed-driver warning. Existing
upstream vDSO __kernel_getrandom declaration warning remains in static.log; build
seed normalization warnings retained, no unrelated source edits.

Reused existing308 incremental cache, not a new complete build tree. All formal
accepted308 artifacts verified unchanged before/after. Previous vmlinux compressed
and decompression hash verified;79 config/CRC/generated-header inputs archived
and individually verified. No old boot/Image in the debug archive. The reused
cache is now a **Test312 diagnostic provider**, not still the old308 provider;
formal accepted artifacts and debug inputs are separate. Project shared ccache
used with5GiB cap. No Windows staging/image copy for this offline qualification.

Original SM5440/gauge disagreement and retained startupREVBLK remain unresolved.
This experiment tests an operating condition, not sensor calibration,100ms
freshness, causality or active protection/PPS/pump readiness. Full Stage3 is
**NOT READY**. A separate physical registration must preserve accepted311
ordinary recovery and use exact308/311 boot+181 rollback, then restore once after
one diagnostic boot. Do not flash old305/306 images reverting accepted recovery.

The Test303–Test312 retention window retires three old302 Images; manifest in
reference/host-storage-cleanup/2026-10-03-test312-image-retirement/. Original
source/config/DTB/modules/debug/evidence kept, current packages untouched.
