# Test257: offline transaction source, evidence and monitoring guards

Qualified source `31ca86caf0a9af23789f3da89113b9b06c069266`, branch test.
Start `a3ddd0debd2eb92a98e1ee4174cd476c526cb18c`; design/registration
`f0f28089` preceded code. Linux7.2-rc3 pin/toolchain/profile pairing retained.
This is an offline continuation of Test256, whose evidence remains sealed.
No tablet command, device identity query, deployment, reboot, module/rootfs
change, actual PPS request or pump activation. Active PPS/direct: **NOT READY**.

## Changes and reasons

Only the existing unwired `x710-charging-policy.c/.h`, its executable C mock
tests and audit/design records changed. Hardware drivers, DTS, fragments,
TCPM core, SM5714 fixed charging and passive SM5440 implementation are untouched.

* A target must fit the latest APDO min/max/current snapshot at every admission
  checkpoint. `apdo=true` alone cannot authorize an old target. Source generation
  includes capability/reset changes; adapter must serialize epoch checks with I/O.
* Facts require actual acquisition time, using the oldest required datum in a
  bundle. ADC requires its completed conversion time. Unknown, stale, future
  or backward monotonic times are rejected. Copying cached data must not refresh
  its timestamp. Source offers persist by generation, not a500ms PD message timer.
* Facts age<=500ms; ADC age<=100ms. Before ON facts age<=400ms reserves the full
 100ms observation window. ON/monitor callback overruns and missed100ms monitor
  call deadline revoke authorization and fall back. These are proposed software
  refusal limits, **not measured protection latency or an OCP safety guarantee**.
* Physical IBUS stays in uA, preserving the ADC625uA LSB.1800625uA exceeds an
 1800mA cap; truncation to integer mA cannot hide it. Exact1800000uA is accepted
  only when all other gates pass. No new hardware current programming or IBAT.
* New monitor entry point reads fresh facts/ADC without changing PPS/pump mode
  on a healthy sample. Fault, revoked offer, stale data, epoch/clock change,
  actual overcurrent or deadline failure invokes verified OFF/fixed fallback.
* Stop revokes authorization even if already switching or adapter is invalid.
  Missing callbacks cannot prove OFF. Ambiguous OFF still blocks voltage change;
  physical cancellation never restores the old contract on a new source.

## Deeper vendor OCP findings

`SM5440_SOFTWARE_OCP_AUDIT.md` traces the actual Samsung implementation:
hardware OCP marked unusable, active init disabling some hardware protection;
IBUSLIM triggers a work item delayed1s; that worker requires IBUSLIM plus thermal
alarm on three checks with1s sleeps. Its status I2C read returns are unchecked.
The separate CC loop adjusts PPS from IBUS. Neither mechanism proves a bounded
mainline cutoff under I2C/scheduler/CPU faults. Vendor ADC aggregation also
returns success despite channel failures and IBAT getter returns0; no fabricated
IBAT or vendor error-handling shortcut is imported.

The live adapter, actual software OCP response, independent protection/watchdog,
ADC accuracy and complete sensor/PM coordination remain blockers. No timer,
automatic PPS consumer, worker activation or pump-ON API was connected here.
Tests only execute the real policy C against mock callbacks.

## Verification

| Check | Result |
| --- | --- |
| Final focused C transaction tests |28 passed (14 retained transaction tests +14 new) |
| Final changed shell wrapper |1253 passed, no failures/errors/skips |
| Final all --fail-on-skip |1253 passed;1239 previous IDs retained,14 added;88.690s report wall time |
| Earlier explicit changed report |1252 passed before adding the final ON-time recheck test; retained as an earlier run |
| Plan commit default build |passed;1239 host checks; protected/config/DT audit passed |
| Code commit policy/default full Image.gz/DTB/modules |both passed,181 paired regular module-directory files each |
| W=1 + actual sparse0.6.5-rc1 |four relevant drivers checked; no driver diagnostic, retained VDSO declaration warning |
| SM5440 binding / dtbs_check |no new binding issue; retained unbound PS5169 role-switch type diagnostic |
| Test256 sealed evidence / reference hashes |all retained;62 references unchanged,96 protected files unchanged |

The first draft mock compilation failed two -Werror style checks (misleading
indentation and missing logical grouping); raw failure is preserved separately.
Fixture formatting was fixed; flags/assertions were not weakened. No skip or
test deletion. No CI/GitHub Actions/main merge.

## Exact identity comparison

Against Test256, **both candidate configurations and DTBs are unchanged**.
Default fixed Image.gz, embedded config, DTB, kernel notes and normalized module
archive are all byte-identical to its qualified fixed-refactor output. The new
code is absent from that default binary because its policy option remains off.
The isolated policy image/notes/archive change as expected for compiled policy.
All paired artifacts and individual module hashes are recorded in validation.

Relative to original Test255, explained deltas remain:

| Profile | Resolved config delta | DT delta |
| --- | --- | --- |
| fixed | CHARGER_SM5440_DIRECT absent->n | none, byte-identical |
| policy-offline | CHARGER_SM5440_DIRECT and X710_CHARGING_POLICY absent->y | hub3 charger@63 status disabled->okay only |

No unexpected delta. USER_NS/POSIX_MQUEUE and all85 Docker/UPower gates retained;
HVC_DCC=n; SM5714/ADC5 Gen3 remain. Frozen Test255 outputs intact. Fixed5V<=1.8A,
9V<=1.5A,float4440mV,ordinary battery2100mA,pack thermal behavior unchanged.
Physical PC USB/PD/battery behavior has not been re-tested by this task.

Raw build/config/DT/static/host reports, artifact SHA256 and failed mock evidence
are sealed under validation and EVIDENCE_SHA256.json. Large images/archives stay
in ignored `out/kernel-x710-257-fixed` and `out/kernel-x710-257-policy`.
Post-record build/test/config/DT/protected review uses separate ignored
`out/kernel-x710-257-record` / `out/x710-257-record-*`; sealed candidates must
not be overwritten merely to change their documented source revision.

## Next

Continue offline protection/adapter design if requested. Hardware sequence stays
passive ID/OFF -> fixed-PD ADC/calibration -> PPS pumpOFF -> reviewed protection/
PM/live adapter -> separately authorized<=1.8A short/5min/20min tests. This
result cannot satisfy those hardware gates. Existing staged physical plan and
stage2-fixed-pd-known-good plus accepted rollback pair remain authoritative.
No rollback was needed or executed. **Active charging candidate: NOT READY.**
