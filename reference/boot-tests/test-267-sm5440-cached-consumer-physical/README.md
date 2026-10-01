# Test267: Test266 passive kernel physical regression

Owner authorizes deployment/test (2026-10-01). Candidate source6477a094,
Test266 final build/full1379/static qualification reused; no rebuild/full rerun.
Device already arrived in SM-X710 TWRP; five partitions and181 regular modules
match accepted Test263. Persistent last boot753b5cf5 differs from older accepted
33435db7; this is a pre-existing boot, not a runner-issued reboot. No runtime
rescue/notes claim is made while in recovery. Root is inspected ro,noload.

Scope: install new boot and exactly paired181 modules into fresh test267 slots,
retain exact Test263 boot/modules and all older backups; vendor_boot/init_boot/
dtbo/vbmeta remain unchanged. Clear the registered BCB and perform one ordinary
Debian boot. Check candidate boot/config/notes, journal attribution, driver/OFF,
DCC absent, and PCUSB Sink/Device. Observe30 seconds at5-second intervals via
combined ADB snapshot/gauge/incremental journal. One final ADB/NCM/Wi-Fi endpoint.
Full journal only at boundaries/on anomaly, module manifest once at installation.
No rootfs/service/USB/config/current/protection/thermal change, PPS, pumpON,
Q4 handoff, real suspend, fresh API consumer or calibration test.

TWRP reports100%/4.409V/25.2C/Good. This is a full-battery passive PC regression,
not charging-power qualification. Registered SOC5..100, gauge VBAT3.5..4.44V,
passive VBAT2.5..4.44V (inclusive), pack<42C (entry20..<38C), die22.5..<60C,
PC VBUS4.5..5.5V, IBUS0, unchanged protections and valid cached snapshot<=2500ms.
The former4.3V/<80% entry bound belonged to the older charging trial; that trial
is not executed or relabeled here. No9V power test on a full pack. The new
100ms in-kernel API has no live consumer; device test covers boot/poller/gadget
regression only, not successful runtime consumption of that export.

Stop first actual device/safety fault: unexpected mode/protection/current,
voltage/temp bounds, I2C/ADC/startup fault, reset loop, kernel/CPU/systemd fault,
unexplained candidate boot, lost device rescue or Code43. Save first raw evidence
and restore exact Test263 through TWRP; manual recovery if online rescue fails.
No repeat-to-clean or diagnostics enable. Host recorder/parser/readiness defect
is retained separately under owner device-normal acceptance; it does not alone
force rollback/reflash/repeated windows. Unknown device evidence is incomplete,
never invented PASS. Accepted first-only startup0x80 still needs retained event
and two fresh confirmations<=5s; no broader whitelist.

Follow-on fixed9V/charging and activeStage3 remain separate, unexecuted.
ActiveStage3 NOT READY. No independent voltage/current/OCP qualification claim.
