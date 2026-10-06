# Proposed Test336 — pump-OFF PPS roundtrip

Preparation only, not physical registration/execution. Do not treat ordinary
Test335 PASS or a bare continuation as permission for automatic PPS/pump/current
escalation. Authorize this specific PPS-OFF scope, register/freeze/push before
installation; never reuse335's evidence as a336 result.

1. Fresh single PC rescue/identity/pack/all-five/181 preflight; require ADB,
   deviceNCM, strict enrolled Wi-Fi, Windows notCode43, actual pumpOFF, approved
   rollback331 boot025ebea4/181 and secondary323 if explicitly registered.
   PrepSOC20–75 (nativeSOC20–<80), VBAT3.5–<4.3V, pack20–<38C. No active load
   or heating to obtain entry. Stop if baseline identity changed.
2. Use qualified source4d058527 Image/config/notes/DT/modules and armedboot
   ffb7bc94 with only sm5440_fedora.pps_return_check=1. All other cmdline tokens
   untouched; direct_charge=N and fixed_return_check=N. Paired181 install in
   TWRP, all-five readback, BCBclear/root unmount; remain TWRP.
3. Owner attaches known LenovoYG65G USB-C1 (C2empty; Test273 recorded its APDO),
   selects System once. Do not boot first on C2 or PC: the one-shot can be
   consumed by a fixed9 source that lacks PPS. Bounded enrolled Wi-Fi lookup
   (recentIP then /24,≤90s) binds machine/config/notes and unique new boot;
   no broad port scans or relaxed hostkey enrollment.
4. Native worker owns its300s first-source admission, one owned PPS request at
   existing target2×VBAT+cable/headroom and1.8A, ADC-only observation/OFF, then
   physical fixed9 proof/release. Require complete journal showing negotiated
   PPS, sample target/observed VBUS/range/zero rawIBUS/OFF, fixed proof and
   PPS-OFF complete lease0, in order/same native transaction. TCPM source
   timestamps/ADC are not independent VBUS calibration. Do not enable pump.
5. Future observer accepts transient PPS only inside this registered native
   transaction, checks pack/physicalOFF/source limits throughout, and stops on
   first fault/transport/identity/evidence/voltage-range/current error. After
   native fixed-return complete, start ordinary_charge_window:≤10s bounded
   positive-current/status settling, then≥30s fixed9 switching, sameboot,
   pack/OFF/identity/journal gates every sample. No timer resets or fault retry.
6. Owner unplugs; short15s discharge confirmation, returnsPC. Unconditionally
   restore exact331 boot/181, all-five readback, one normal attributed reboot,
   final identity/OFF/health/ADB/deviceNCM/Wi-Fi/fulljournal. Do not retain armed
   PPS check. No needanother long observation or repeated hashes per sample.

First native error/ADC out-of-envelope/nonzeroOFF rawIBUS/detach/source change/
suspend/thermal≥38C/SOC≥80/VBAT≥4.3/unknownphysicalOFF/kernelstall/oops/panic/
USB rescue loss/Code43/unexplained reboot stops. Preserve primary and cleanup
errors. Unknown physical return/lease retained => promptly unplug, obtain
recovery access and restore331; do not force lease release or fake readiness.

PASS proves only a bounded pump-OFF PPS-to-fixed roundtrip plus ordinary return.
It does not authorize pumpON,5min/20min high-power runs,2–3A progression, actual
input-watt claims, OCP/cutoff reliability or complete production direct charging.
