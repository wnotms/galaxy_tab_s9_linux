# Passive startup latch and transport ordering

Start revision4c3cf940, accepted installed Test255. Test258/259 results remain
immutable. This is an offline repair candidate, not another automatic physical
attempt. No PPS/pump ON/protection/current/USB/config/DT change.

[VENDOR] Samsung msm-kernel/drivers/battery/charger/sm5440_charger/
sm5440_charger.c: sm5440_irq_thread() reads INT and STATUS separately, logs
REVBLK independently, and reports forced cutoff only at direct state>PRESET
with modeOFF. This does not justify ignoring all inactive faults. Its reverse
boost recovery, aggregate init and higher protections are not copied.

[MEASURED] Test259 first conversion: INT3=0x62, STATUS3=0x20, modeOFF at
both boundaries, newly completed ADC4.867V/3.938V/0A/28.5C. Only latched
REVBLK is decoded; no livefault. This does not date/explain the latch or prove
Test258's different0x82 harmless. Existing decoding treats all latched flags
like live health failures and permanently disables the passive monitor.

[BRINGUP_LIMIT] Narrow startup state:

1. First successful sample only: decodedfault must be exactlyREVBLK;
   liveSTATUS must decode no fault; modeOFF and completedADC; onlinePCVBUS
   4.5..5.5V, VBAT3.5..<4.3V, IBUS exactly0, die22.5..<42C.
2. Preserve full first-fault raw warning. HealthUNKNOWN, notGood; no current/
   voltage/online telemetry publication while confirmation is pending.
3. Require TWO subsequent freshly completed samples within5s, each with no
   INT/STATUS faults, the same read-only protection settings and these bounds.
4. Any recurrent/livefault, timeout/I2C error, changed protection, detach,
   unsafe value, suspend or deadline expiry latches failure. No startup retry
   on resume or later attach. No global decoder mask; VBAT_OVP always stops.
5. After confirmation only passive monitoring resumes. Startup event remains
   recorded; physical result must distinguish accepted startup latch from a
   warning-free boot. This does not authorize any activecharge configuration.

No core mutex is held across ADC wait; existing singleworker/PM drainage and
OFF verification remain. Startup confirmation has no hardware writes beyond
existing ADC controls. Default fixed profile still does not bind SM5440.

Transport: Test259 runner requested NCM identity before reading hardwarehealth.
SSH timeout prevented early admission but ADB later retrieved fault1.676898s.
Replace this ordering in a new helper: ADB boot/journal/supplies first; any
hardwarefault stops before transport probes. Collect Windows adapter/address/
route evidence, interface-bound banner and actual NCM authentication separately.
Keep first NCM failure, finite readiness attempts and recovery timing; recovered
transport is usb-transient, never silently clean. WiFi is a separate channel,
not proof of NCM. No device/Windows networkconfiguration or USBdriver change.
Current host route is mirrored WSL eth2/APIPA; the old helper's generic NAT
comment alone cannot establish topology at the failedboot. Historical failed
boot has insufficient Windows evidence to locate routing/address/timing cause.

Next physical test requires a fresh separately published registration with
exact candidate/rollback identity and updated startup classification, PCUSB
only,150s after transport ready, and all historical safety/rescue stops. Do
not boot/reflash as part of this offline correction. ActiveStage3 NOT READY.
