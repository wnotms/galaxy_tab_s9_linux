# Bounded Fedora-source direct charging — offline preparation

Continue from Test337's accepted pump-OFF PPS/fixed9 ordinary recovery; retain
the installed exact Test331 baseline. Prepare a separately registered Test338
candidate, not an automatic continuation of the old pump-OFF scope.

Only add `direct_charge_once` to the already ported same-model Fedora driver:
one attempt, <=30s software observation budget,100ms scheduled monitoring,
first error terminal, no backoff/re-entry/resume. Reuse native Linux TCPM,
SM5714 owned switching lease, physical fixed return and Test337 async recovery.
Defaults remain inactive. Existing continuous opt-in behavior is not selected.

Before ON, verify the existing Samsung/Fedora register recipe and fresh owned
pack/continuous ADC, zero pump current, matching VBAT and die limits. Retain
625uA and500uV precision. Check latches/current/pack before refresh; park across
TCPM, check again before ON and refuse re-arm past the absolute deadline.

No speculative hardware OCP bits: Samsung explicitly says SM5440 cannot use
ordinary HW OCP.100ms scheduling and500ms gap refusal are software limits,
not hard-realtime cutoff proof. Readback of init registers does not validate
hardware protection. Initial tests need explicit pump-ON scope and physical
unplug/recovery on unknown OFF, lost rescue or failed fixed return.

Keep source PPS<=1.8A, SM5440 input<=1.8A/VBAT regulation4400mV, pack float4440mV,
fixed5<=1.8A/fixed9<=1.5A and fail-closed thermal/PM unchanged. Entry20–<80%,
20–<38C,3.5–<4.3V; runtime<42C/<4.4V, die<85C, physicalIBUS<=1.8A,
gaugeIBAT<=3.6A, ADC/gauge VBAT difference<=200mV. The latter are conservative
bring-up checks, not claims of independently calibrated physical measurements.

Run affected C/ownership/ADC/policy tests, one incremental ARM64 build,
changed-object W=1/sparse, exact config/DT/protected-source/module qualification.
No all-suite/routing change/CI/Actions. No device command, flash, reboot, source
PPS Request or pump operation during offline preparation. Build outputs use a
new formal namespace but the existing cache; preserve331/337 qualified files.
