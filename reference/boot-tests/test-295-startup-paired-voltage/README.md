# Test295 — startup paired-voltage diagnostic

ONE candidate boot, PC USB kept attached. Purpose: compare SM5440 OFF-mode
startup VBAT with nearby live SM5714 SRAM VOLTAGE_NOW, including timestamps.
Only first sample/pending confirmations receive a supplier read (at most3).
No observer, trace, PPS, pump ON, current increase, converter/threshold/deadline
change, fault clearing or startup-health exemption. Existing passive refusal
is retained as evidence; diagnostic completion is not charging acceptance.

ADB and strictly pinned sameboot NCM SSH are required. WiFi host reachability
failed during preflight and is recorded; it is not required for this fixed-PC
scope. Do not unplug or switch charger. Exact263 rollback mandatory after
collection; only boot +181pairedmodules written, other4partitions read-only.
Unique295module backup slots preserve old backups. BCB approved helper plus
ordinary reboot only; clear BCB and unmount before TWRP exit.

Readiness up to150s, return immediately when services/ADB/NCM available;
collect complete startup kernel JSON/cache snapshot, then15s endpoint. First
new kernel/SM5440/I2C/USB/thermal/identity/evidence failure stops and rolls back.
Known REVBLK/startup confirmation failure never becomes a charging grant.
No fixed150/300s stability wait, no late observer load/unload, no repeated
physical attempt. Preserve paired timestamps; neither sensor is independently
calibrated. Missing/failed gauge read => inconclusive, no retries.

Source1028ae06, build/config/DT/protected/181 archive/W1sparse PASS.208affected
SM5440 tests (10new) +11runner tests pass. Unchanged294full qualification reused;
full-regression executed:false. Initial relative-build-path config refusal is
preserved; rerun with canonical absolute paths passed, noconfig workaround.
Deploy only AFTER this registration is committed and pushed to origin/test.
