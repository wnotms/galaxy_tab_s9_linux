# Retained native charging session — offline qualification

Verdict: **OFFLINE_RETAINED_NATIVE_SESSION_QUALIFIED**. Full charging port:
**NOT READY**. No device deployment or new physical charging acceptance.

The real native controller now retains one hardware/source/pack/switching session
across entry, monitor, paused refresh/retarget, resume and stop. Temporary OFF
preserves prepared settings/watchdog; terminal OFF alone restores/releases them.
Fresh source/pack reads bracket a previous genuine physical sample with its
original timestamp. Running measurements use the actual native supervisor,
raw-current/fault checks and watchdog service. Native binding verifies the real
owned TCPM snapshot and switching lease outside io_lock, rechecks PM/token under
that lock, and maps controller epoch to hardware-session epoch.

One ordered queue schedules 20ms monitoring and 4s paused refresh/retarget.
The existing 100ms refusal boundary remains; scheduling is not hard realtime
cutoff or physical OCP proof. First fault/cancel/suspend drains checked OFF,
fixed-PD return and source-bound switching release without hidden retries.
Resume never arms. Unknown cleanup latches unresolved ownership and refuses
replacement sessions. Source changes cannot reuse old worker authority.

**Kernel activation stays closed:** controller qualification, native actuator
ON and physical OCP grants are absent, with no public setter. Tests seed private
mock grants only in their separate translation units to exercise real entry /
monitor / pause / resume / stop. That is neither physical qualification nor
permission to energize the device. Existing explicit OFF roundtrip is retained.

A new actual-C fault test initially failed: after running monitoring and pause,
an unfinished newer OFF ADC conversion was skipped by terminal cleanup because
the old monitor had started. RELEASE returned EIO with retained ownership.
Cleanup now cancels both converter contexts after proven pump OFF and preserves
first error; the test proves settings/ADC restoration and no re-enable.
The original failure is retained in development-finding.json. No tests removed,
skipped or weakened. Mock release/delayed-work fixtures were corrected to match
real shutdown and zero-delay queue semantics rather than changing assertions.

## Executed validation

- 325 affected tests PASS, 10.256s; zero failure/error/skip.
  Actual threaded coordinator/core, 22 native bus/lifetime/active-session tests,
  converter/supervisor/actuator/watchdog, pack/source/TCPM/container dependencies.
- Full suite executed:false under latest affected-only owner workflow; no routing
  change. Historical full-suite missing-artifact results are not a new PASS.
- Final standard ARM64 Image/DTB/modules build PASS, 79.796s,
  jobs8/ccache, Linux7.2-rc3 a13c140cc289c0b7b3770bce5b3ad42ab35074aa.
  A preliminary build preceded the new cleanup test/fix; final artifacts replace
  that intermediate candidate, whose host log is preserved.
- Final W=1/sparse PASS, 7.416s, no changed-driver warning;
  known upstream VDSO declaration warning retained. Controller source/header and
  native diff checkpatch: zero errors/warnings/checks. Git whitespace PASS.

## Exact identity / unchanged baseline

Resolved config is byte-identical to previous native-control and OFF-controller
outputs (SHA256 6f70dd31a582efc0464c37b505693f7fe8af3949a9c2a573a1ca116a7e73f42d).
Accepted311 delta remains only CHARGING_POLICY n->y, NATIVE_CONTROL absent->y,
ADC_CONDITION_TEST n->absent from its existing !policy dependency. Test303 delta
remains NativeControl absent->y. HVC_DCC=n, USER_NS/mqueue/container and SM5714/
ADC5 retained. No config or DT change in this increment; DTB is exact accepted311
SHA256 233a9fee91dc725901f0c7c620a38e475d6d6e6880cde660ec85ae34d49e0a8e.

All 53 protected sources and 24 frozen formal files preserved.
181 matching module files archived and verified. Module ELF runtime bytes/shape/
relocations/nondebug symbols match accepted311; debug/BTF/build identity changes
are recorded. Built-in metadata/index is unchanged from prior OFF-controller.
Compiled copies, embedded config, kernel notes and actual linked native/core/
periodic/source/lease references verified; artifact-audit.json.gz is lossless.

Formal outputs: out/kernel-x710-active-session/. Same native-profile incremental
cache reused; its historical303 name is not a Test303 provider. Original accepted
ordinary outputs are untouched. No new full build tree or Windows staging.
TCPM core, TCPC transport, switching/thermal policy, converter/control algorithms,
DTS, USB/DWC3/gadget/adbd/rootfs and current/voltage ceilings remain unchanged.

## Remaining work

Native physical ADC/calibration/current/protection/cutoff qualification is still
missing; Test321 RAW data and passing mocks do not supply it. No guessed offset,
relaxed 100ms window or public activation knob is introduced. Next use a new
source-backed acquisition/calibration scope, then independent PPS-OFF/<=1.8A
pump/fault-PM acceptance with accepted ordinary rollback. Higher power remains
later. Do not reflash the unchanged failed profile. This record is progress on
the original full port, not final hardware release.

Separate owner USB-reconnection evidence was committed before this offline
increment; it records accepted311 device unchanged and pack0%/3.226V under PC
net discharge. Charging recovery was requested; no device operation belongs to
this offline qualification. No flash/reboot/PPS/pump ON/rootfs change/Actions.
