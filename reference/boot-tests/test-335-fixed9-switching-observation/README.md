# Test335 — unchanged Test331 fixed9 switching observation

Purpose: collect the missing **30 seconds of continuous ordinary fixed9 switching
charging**, using the qualified enrolled Wi-Fi discovery helper. Test334's native
OFF fixed-return proof already succeeded; its host transport STOP remains sealed.
This test does not replay that one-shot or retroactively accept Test334.

Installed baseline: accepted Test331 source `1f1d8568`, Linux7.2-rc3, config
`51ba6a9c…`, notes `03c9c46e…`, boot `f1e9a45a…`; exact hashes and existing normal
cmdline are frozen in registration.json. Reuse Test334 final all-five/181 paired
acceptance and current same-boot Wi-Fi identity; no build or repeated partition/
module hashing. No flash, recovery request, reboot, rootfs/service/config change,
native fixed-check opt-in, PPS request, ADC setup, SM5440 init/reset or pump ON.
Only the already accepted atomic CNTL5 pointer/read verifies OFF; it programs no
register data. HVC_DCC remains disabled, float4.44V and thermal policy unchanged.

## Registered sequence

1. Publish registration and affected host qualification before owner cable action.
   Enrolled SSH key/alias only; last private IP then bounded same-/24 discovery,
   ≤90s,16 TCP workers,2 SSH identity slots. Require exact machine/config/notes/
   same boot/cmdline/defaultOFF, DCC absence, no failed units, device NCM and
   ssh/adbd/USB services. Preserve full boot kernel JSON before/after.
2. Arm read-only `run.py charge`; after ARMED ask owner to attach Lenovo YG65G
   USB-C2 (18W), C1 empty, computer USB disconnected; Wi-Fi remains connected.
   Wait≤240s for fixed9. From its first healthy sample observe≥30s with sample
   gaps≤3s: sink/device, fixed9 PD online, ordinary battery Charging/current>0,
   input100mA–1.5A and no greater than source contract, pump OFF. All samples:
   SOC20–<80%, VBAT3.5–<4.3V, pack20–<38°C, real enabled pack thermistor agrees
   within0.5°C, present/Good, design4.44V, no PPS or unexplained reboot.
3. Only after charge PASS arm `run.py discharge`; ask owner to unplug charger,
   keep Wi-Fi, no computer USB/reboot. Wait≤240s then observe≥15s source/USB
   offline, Discharging/current<0, same boot/OFF/pack gates. Device-normal
   completion within this scope is sufficient; Windows NCM reachability and
   another PC reconnect are not this test's acceptance target.

Stop on the first safety/identity/transport/evidence gap, unknown fixed voltage,
PPS/pump activation, severe kernel signature/new priority≤3 kernel error,
failed unit, charging loss or response gap. Existing same-boot startup errors
remain in the complete raw journal and are distinguished from new errors;
CPU/panic/Oops/stall signatures are never whitelisted. No retry/new scope to hide
the first stop. Tell owner to unplug the charger on STOP; inspect evidence.
Rollback requires no software writes because installed accepted331 is unchanged.

## Qualification and limits

Affected tests only: local Test335 gates/continuity/journal/first-stop/transport
plus unchanged discovery's23 tests. No test routing, kernel or build integration
change; full tests and kernel build `executed:false`, reuse accepted qualification.
Source/config/DT/USB/adbd/charging drivers remain unchanged.

TCPM voltage/current are negotiated limits, not independently measured VBUS or
charger input power. Battery power is VBAT×IBAT, not charger watts. No physical
9.5V proof, ADC calibration, PPS-to-fixed transition, SM5440 active/high-power
acceptance, cold-boot/reliability claim or automatic current progression. Full
charging port remains NOT READY after this bounded ordinary-charge scope.
