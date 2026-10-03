# Checked SM5440 pump register layer

This is an offline, unintegrated part of the future direct-charge adapter.
Test317 kernel/package and its required accepted311 rollback are frozen.
There is no Kbuild hook, live caller, userspace activation or device write.

The existing transaction core already owns eligibility/PPS/fallback, and the
OFF-settings/watchdog helpers own their specific registers. The new layer
supplies the missing checked CNTL5 CHG_ON/OFF and CNTL6 ENHIZ operations, with
readback and bounded cleanup. It does not implement another PD state machine.

[VENDOR] `sm5440_set_op_mode()` owns CNTL5[3:2], CHG_ON code1; `set_ENHIZ()`
clears CNTL6[7] for charging and sets it for attached+OFF. [FEDORA ab123e7d]
waits for real VBUS and arms WDT before pumpON. We retain these operations,
not full init F2/FE, reset, OCP-disable recipe, current margins or unchecked
success returns. Restore inherited settings only after OFF is read back.

## Admission and ordering

Caller must serialize SM5440 I/O, drain cancellation/PM and bind a local atomic
generation to the current source. No cross-device callback or PD wait occurs
inside the helper. A READ_ONCE generation check precedes every possible ON
write and follows it. Caller still owns native source/lease/producer ordering.

Enable defaults false. Existing `x710_charge_eligible()` must accept real facts,
including software_ocp_verified, source APDO and pack gates. There is currently
no qualified live producer of that OCP flag: pumpON remains unavailable on device.
Facts must be <=400ms old, actual OFF physical sample <=100ms old, VBUS within
100mV of the approved8.2–10.5V target, real VBAT3.5..<4.3V, zero OFF IBUS/no
fault, die<42C. Target current1000..1800mA in50mA steps; source bounds apply.
The explicit switching-inhibit flag and a same-epoch armed30s watchdog are
mandatory. Fresh native SM5714 snapshot must prove actualONLINE2/pps_contract,
exact mirrored V/I, instance/source/budget generations and a matching approved
PPS APDO. A PD_PPS capability label on ONLINE1 is refused. Diagnostic500ms
samples cannot pass these gates.

Before ENHIZ/mode writes, verify DEVICEID, healthy live STATUS/POK, pumpOFF,
all prepared current/voltage/frequency fields and ten unmodified witnesses
(CNTL1 may equal the owned watchdog value). Only then save CNTL6, clear its
ENHIZ bit with exact readback, recheck generation/freshness/live state, write
CHG_ON and verify mode plus live fault/POK. Mark write ownership before I2C.
Post-ON physical measurement/100ms monitor remains the transaction core's job;
register readback alone is not direct-charge acceptance.

On any start failure attempt one checked OFF cleanup. If OFF cannot be proven,
retain possible-ON/ownership and do not disable WDT, restore limits or permit
fixed fallback. Once OFF is proven, restore owned ENHIZ, watchdog then settings
in that order; watchdog must be restored before settings' CNTL1 witness check.
Preserve first operation error and separate cleanup error. Cleanup is attempted
once per actuator lifetime, including failed cleanup: an outer transaction's
fallback cannot silently issue a second OFF retry or erase the first result.
Stop also latches cancellation against later start/rearm. Unknown/drifted
bits, uncertain writes or failed readback remain visible; no automatic retry.

Stopping is allowed after cancellation; it never writes CHG_ON. Resume/rearm,
source-voltage change and lease release are not provided here. The future
adapter must prove same-source physical fixed state before switching release.

## Boundary

Compile the actual C and inject each bus failure/drop/uncertain write, changed
generation, stale/future time, hardware fault and cleanup failure. Compile an
unlinked ARM64 object with W=1/sparse, retaining current316 provider identities.
These checks prove register-layer behavior, not ADC calibration, analog cutoff,
software OCP latency or physical protection. Integrate only in a separate
qualified offline active profile after Test317/rollback; normal fixed charging
and current device stay unchanged.

## Offline results

44 affected tests pass (14 new actuator,16 watchdog,14 existing OFF settings).
They compile/link all four actual C sources and execute admission, real
register writes, every start/cleanup I/O failure, uncertain/ignored writes,
source generation/mode/APDO rejection and single-attempt cleanup. Mock OCP
qualification is test input, never a physical acceptance record.

ARM64 unlinked object W=1/sparse passes in3.657s, with no changed-helper warning.
An initial host compilation exposed signed comparisons/mock parentheses; these
were corrected before the final executed suite. An earlier successful ARM64
object before the cleanup latch is retained as superseded, not final evidence.
All six316 provider hashes,98 sealed317 inputs and nine package artifacts remain
exact; config/DT diff is empty. No Image/modules relink/full/Actions/deployment.
Results: `reference/charging/sm5440-actuator-foundation/summary.json`.
