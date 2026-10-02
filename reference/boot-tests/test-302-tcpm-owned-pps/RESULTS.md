# Test302 — owned TCPM PPS protocol, offline qualification

**OFFLINE_OWNED_TCPM_PPS_PROTOCOL_QUALIFIED.** Implementation `de2ebc5c`;
build `21d534c1` adds only the separately committed read-only photo follow-up.
This qualification does not deploy or physically activate PPS or the charge pump.

The kernel-only API uses native TCPM ONLINE=2/current/voltage setters under
a checked switching-OFF lease and exact source/provider identity. Every target
and intermediate pair must fit the source APDO, board limits and connector
operating power. Actual RDO transmission and owned budget callbacks must match
the permitted pair; authorization closes before the API returns. An unchanged
refresh requires a new owned call with pump OFF. Fixed return uses the native
2.5W standby budget and retains inhibition; PPS9V/1.5A cannot be mistaken for
a releasable fixed9V/1.5A contract. Failures preserve the first error and permit
only one same-owner fixed cleanup attempt, never an automatic release or retry.

The default fixed path remains 5V<=1.8A / 9V<=1.5A. The unused owned PPS API
has existing bring-up limits 8.2–10.5V / <=1.8A, not a new validated operating
range. No installed consumer calls it. No TCPM core, DWC3, USB gadget, adbd,
rootfs, DTS/config, SM5440 ADC/pump policy, float voltage or pack thermal change.

185 affected actual-C/policy host tests passed in 5.102s, zero failures/errors/
skips. This includes transport setters/callbacks, exact wire permission,
identity/lease lifetime, detach/PM/fault refusal, timeout/transport injection,
standby and fixed/PPS kind distinction. Native TCPM/physical hardware are mocked
in these host fixtures; the ARM64 build checks the real pinned APIs. Initial
fixture failures and discovered owner-cleanup defect remain in raw logs.
Full regression executed:false; routing unchanged and latest owner workflow
requires changed-scope checks. No existing tests were removed or weakened.

ARM64 Image/DT/modules build passed in 96.678s. Changed battery and TCPC
objects passed W=1/C=2 sparse in 8.361s with the same ccache environment;
object hashes and linked vmlinux stayed identical. Neither changed driver
warned; the existing upstream vDSO `__kernel_getrandom` declaration warning is
retained. Checkpatch: zero errors/warnings.

Exact Test301 -> Test302 config and DTB diffs are empty. Embedded configuration,
Docker/UPower prerequisites, HVC_DCC=n, 96 protected sources, eight compiled
overlays and both compiled shared-header copies pass. All 181 paired module
files and the normalized archive match the new build. Use this candidate's
paired modules and Module.symvers; do not reuse older observer module CRCs.
Test301 artifacts and frozen Stage2 artifacts are unchanged. Full hashes and
module manifests are in summary/artifact audit; large artifacts stay under
`out/kernel-x710-302-passive`, not Git.

The only device activity during this continuation was the read-only owner-photo
follow-up committed separately. The photo is byte-identical to Test299's old
incident. Current retained Test299/Test300 boot57535... notes match; its complete
1145-row kernel journal contains no temperature-read disable message, all
enumerated zones are enabled, and the real pack zone37 reads31.8C. That is not
a new physical charging acceptance or evidence of valid SM5440 die temperature.
No flash/reboot/PPS/pump or charging-current change was made.

Next: connect the actual coordinator/PM consumer and register a short pump-OFF
protocol scope with genuine physical voltage/temperature/OFF evidence and
accepted fixed baseline rollback. Resolve ADC validity/freshness and protection
requirements before any pump activation; do not waive them or repeat an
unchanged failed ADC-delay profile. Active Stage3 is **NOT READY**, full wired
charging port remains incomplete. No automatic deployment or Actions/CI.
