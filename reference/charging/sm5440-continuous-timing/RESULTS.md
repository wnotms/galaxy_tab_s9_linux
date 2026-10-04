# OFF continuous SM5440 ADC timing candidate — offline only

The actual passive driver now invokes the bounded converter through a separate
`sm5440-adc-timing` Kbuild/profile. This is real linked C, not an unapplied patch
or unlinked mock foundation. It runs once after existing OFF startup gates,
requires native fixed/pack facts, captures eight new READY/read brackets and
raw ADC/live/latch/control bytes, verifies original ADC restoration and stops.
No companion or writable trigger is published. No PPS/lease/Q4/current/ENHIZ/
protection programming, pump ON, TCPC/TCPM/DWC3/DTS/rootfs/adbd change exists.
The frozen converter, request/admission and ordinary/condition preprocessed
paths remain unchanged. An unexpected mode/fault gets one checked existing OFF
operation before ADC cleanup, with first/OFF/cleanup outcomes retained.

21 latest actual-C tests PASS0.628s, plus175 unchanged dependency tests retained
PASS. Prior combined196 PASS11.628s; those receipts are distinct, not a new full
regression claim. Fault injection covers every transfer, ignored changed-register
write/readback, old READY, missing later READY, physical voltage/current/die
bounds, cancellation, monotonic time/window, source/pack epochs, native errors,
readiness, no wait/supplier under I/O lock and no rearm/second cleanup. No old
test was deleted/skipped/weakened. No routing change or GitHub Actions.

Initial mock falsely treated a RATE write while disabled as a new disable event,
then a cycle fixture lacked errno/lockdep definitions; failures retained and
fixtures corrected. Exact archive root initially differed from the existing
release-root format, corrected after the preserved KeyError; final packaging
and all181 files must pass. A final boundary review made finish-before-begin
refuse instead of returning0. Final source/build supersedes earlier successful
readiness-only variants; their raw reports remain historical, not current
qualification. Final ARM64 Image/DT/modules build PASS83.143s, actual changed objects W=1/
sparse PASS6.177s, no changed-driver warning (known upstream vDSO warning only).
Exact embedded config/compiled overlays/linkage/protected209sources/21prior
formal artifacts PASS. DTB equals accepted311; exact config delta vs accepted311
is only CONFIG_SM5440_ADC_TIMING_TEST absent->y. All181 module files paired,
167 changed only.BTF, no module code/data or builtin metadata change. Complete
config diffs vs316/native-pack and all artifact hashes are inartifact-audit.json.

Diagnostic500ms/2000ms bounds and native clocks are **not** active100ms ADC/OCP
certificates. READY time is software observation, bulk channels may update and
physical calibration/current/cutoff/ON-mode protection still need acceptance.
The mainline charging port remains NOT READY; the physical device remains
accepted311, with no candidate flash/reboot/PPS/pump activation this turn.

The fresh owner-startup check is separately archived under
`reference/charging/device-startup/2026-10-04-ac442c81/`. The old thermal photo
is attributed to the Test299 SM5440 cache, already fixed by accepted Test300;
current actual battery zone is enabled. Latest brief read-only check shows6%
SOC,3.660V,31.1°C and Good battery but net-427mA from PC. Owner was asked to
use previously accepted Lenovo C2 ordinary18W charging while offline work
finishes; no answer/physical connection is inferred from elapsed time.

Next independently register Test318 one PC fixed5V boot, this short bounded
OFF timing question and unconditional exactaccepted311 restore. No blind replay
of Test317,9V/PPS/pump/current escalation or repeated long observer window.
