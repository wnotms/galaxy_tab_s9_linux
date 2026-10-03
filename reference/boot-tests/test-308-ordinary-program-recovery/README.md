# Test308 ordinary charger programmed-state recovery

Purpose: qualify a bounded recovery of the ordinary SM5714 Q4/input/fast/float
programming after Test307 proved those controls differed from the startup log.
This is an offline qualification, not a reset-cause experiment or a physical
charging acceptance. Frozen fixed5V<=1.8A/fixed9V<=1.5A,4.44V float and real pack
thermal policy remain. No SM5440 pump/PPS/charge-current escalation is enabled.

The actual C now retains a verified ordinary programming witness. Intentional
OFF invalidates it before I2C. Same-attach polling reads four stable controls;
matching state and AICL-lowered input produce no writes. A mismatch permits one
recovery per binding after verified Q4OFF and current fault/thermistor/source
checks. Bus errors, silent writes or a second mismatch latch an independent
program fault. Cleanup attempts Q4OFF/minimum input and reads both back; failed
cleanup does not constitute proof of OFF. No watchdog clear, mode/reset write,
TCPC core/data-role/gadget change or PD renegotiation is added.

See docs/SM5714_PROGRAM_STATE_RECOVERY.md. The existing Test306 runner seals the
old source; do not silently reuse its registration for this candidate.

## Future device scope (not registered or executed here)

First restore safe ordinary charging. Last Test307 observation was0%/2.775V,
Not charging, and lpcharge=1; it is insufficient for a deployment entry gate.
Owner confirmation of connection to the previously tested USB-C2 source and
fresh safe battery state remain required. No flashing/reboot/live register
patch is done during this offline qualification.

A separate test must register/push the paired candidate and exact accepted299
rollback before mutation. Use one normal candidate boot, essential identity,
real pack thermal/battery, ADB/device-side NCM/Sink+Device, full boundary journal
and stable controls. Observe ordinary charging at the existing caps; keep PPS
and pump OFF. No deliberate reset, forced I2C failure, overheating or low-battery
stress to cause the recovery path. Short registered observations are sufficient
for normal device behavior; host mocks establish injected-failure behavior.
Stop on charger programming fault, readback error, thermal invalidity, lost
rescue, kernel fault, unexplained reboot or abnormal battery current/voltage.
Unknown Q4OFF/identity requires manual recovery, not repeated writes. A clean
ordinary test can retain the fix; any failure restores exact accepted299 paired
boot/modules through the established recovery procedure when battery-safe.

Only after ordinary charging recovery is qualified should a new, separately
registered OFF-mode ADC condition comparison be considered. Physical ADC
validity/freshness, active protection, actual PPS/handoff and PM acceptance
remain incomplete; full Stage3 is NOT READY.
