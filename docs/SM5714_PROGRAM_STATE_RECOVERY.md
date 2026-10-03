# SM5714 ordinary charger programming lifetime

Design follows the read-only Test307 incident. No runtime change is authorized
by this document itself; the critically low battery must recover first.

## Observed gap

On retained Test299 notes/config, a new `lpcharge=1` boot logged ordinary SDP
charging at500mA input /500mA battery near1.52s and1.98s. At uptime2052s the
gauge reported0%,2.775V, about+6mA and `Not charging`. The real pack thermal
zone was enabled at31.5°C. Atomic reads of documented stable charger registers
found Q4OFF (`CNTL1=0x64`), input1800mA (`VBUSCNTL=0x44`), fast-current code
0x97 and float4200mV (`CHGCNTL4=0x55`, low6bits0x15). The expected configured
codes were input0x10, fast0x20, float0x2d and Q4 bit3ON.

Operation mode was5 (ordinary VBUS switching), not suspend/OTG. WDTCNTL=0x04
had enable bit0 clear. Do not label this an active watchdog timeout: prior
watchdog state and the cause/time of the register change are not established.
No configuration data was written; register-pointer/read transactions were
atomic and avoided INT latches. The initial I2C-name guard failed before bus
access; corrected capture checks the actual driver and OF compatible.

The current driver reprograms on attach/type/thermal change and FULL->NOT_CHARGING.
It does not retain/verify the successfully programmed Q4/input/fast/float state
while the same cable stays present. A disappearing enable or changed float can
therefore remain undetected. Repeatedly calling configure on any NOT_CHARGING
status is inappropriate: standby, suspend, PPS ownership, thermal stop and FULL
are intentional OFF conditions, and failed programming must remain latched.

## Source facts and boundary

[VENDOR] `sm5714_charger_oper.c:set_OP_MODE()` writes CNTL2[3:0], ordinary mode5.
[VENDOR] `chg_set_enq4fet()` controls CNTL1 bit3 after input reduction.
[VENDOR] `chg_set_batreg()` programs CHGCNTL4[5:0];4440mV encodes0x2d.
[VENDOR] WDTCNTL bit0 enables, bit3 kicks, bit6 clears expiry. Do not add those
operations or clear a watchdog fault as part of programming-loss recovery.
[MAINLINE CURRENT] existing configure sets all approved current/float values
and preserves unrelated register bits; every real sensor/I2C/fault refusal
opens Q4 and inhibits further Type-C charging. Preserve that behavior.

No proof of battery precharge calibration or its hardware threshold follows
from this incident. No guessed low-VBAT charging recipe, emergency current
increase, OTP override, watchdog reset, SM5440/PPS, charger mode write, thermal
waiver or live register patch belongs in this change.

## Implementation

The implementation keeps an internal programmed-state witness under existing `chg_lock`: validity,
expected input and fast-current codes, a bounded recovery-used flag and a
sticky program-fault latch independent of Type-C ownership.
Float uses the existing4.44V encoding. The witness is captured only after a
successful full configuration with actual Q4/input/fast/float readback.
Every deliberate disable invalidates it before I2C, including uncertain writes.

Ordinary polling compares the witness with fresh stable register reads only
when charging is authorized: no suspend, PPS, switching lease, Type-C fault or
standby. Compare only controlled masks and actual programmed codes; do not
manufacture a CHG_ON status requirement for hardware trickle/regulation.
An unchanged witness causes no register write and no repetitive log. Hardware
AICL can autonomously lower the input-current code: monitoring treats the saved
input as a ceiling and never raises it merely to restore an exact match. Initial
configuration readback remains exact. Float/fast/Q4 compare their owned bits.

A positively read mismatch permits at most one recovery per driver binding.
First open/verify the pack gate; re-run the existing bounded ordinary configure
under `chg_lock`, with a current source grant and fresh real thermistor/fault
checks. Reapply exactly the existing approved limits, not values read from the
drifted registers. Do not hold TCPC locks or initiate PD negotiation. Record
before/expected values and the one recovery outcome; preserve the first error.

An I2C error, active fault, failed readback or second mismatch refuses recovery,
attempts Q4OFF/minimum input and reads both back, revokes/inhibits ordinary
authorization and remains latched. The program-fault latch survives later
budget/PM/cable changes even on the unclaimed BC1.2 path. No
watchdog clear, automatic reset, retry timer or recovery storm. If cleanup I2C
fails, OFF is unproven; require unplug/manual recovery instead of a healthy
status claim. Detach/PM/lease paths must never be misidentified as programming
loss, and no new connection may inherit a stale witness.

## Validation and deployment boundary

Execute the actual C functions with injected failures at every read/write,
intentional OFF states, known Test307 mismatches, unchanged-state no-write,
mask preservation, bounded recovery, second mismatch, source contraction,
thermal failure, suspend and detach. Existing Stage1/Stage2/lease tests stay.
Build the standard passive candidate with the same Linux7.2-rc3/toolchain and
pair181 modules. Resolved feature settings must match retained Test299;
only this ordinary charger implementation changes in this patch. The already
introduced, default-off ADC diagnostic declaration adds an explicit disabled
line relative to Test299; that is the sole resolved-config delta, not a feature
enablement. DTB must remain byte-identical. Run affected tests / W=1 /
sparse and preserve accepted rollback. Do not deploy at0% or below the safe
registered VBAT entry range.

The Test306 ADC-condition runner seals the previous source. A charger-driver
change invalidates that registered source gate even if its saved binaries stay
intact. Do not bypass the gate or silently substitute a new image: first qualify
and independently register ordinary charging recovery, then decide whether a
new ADC comparison is still needed. Full Stage3 remains NOT READY.
