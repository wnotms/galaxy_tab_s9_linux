# Test258 attempt02: passive probe with release-root module installation

Owner authorization: "继续实机测试". Start HEAD a4437ece. Preserve the earlier
stopped Test258 attempt and all seals/results; this is a fresh registration.

Purpose: install the SAME f3a266b5-qualified sm5440-passive candidate, verify
passive probe/OFF-backed telemetry on ordinary PC USB for at least150s.
No PPS, pump ON, current increase, charger change, unplug/suspend or active
transaction core. Stage2 fixed5V<=1800mA/9V<=1500mA,4440mV float,2100mA pack,
thermal, Test253 adbd, Test254 containers and DCC=n remain unchanged.

Only deployment-helper change: use the separately sealed release-root adapter
from a4437ece, already host-tested on the actual181-file candidate archive
(5 checks,2.671s). Reuse the qualified build/full1264/artifact/bundle audit.
No repeated kernel/full regression for registration/results. Adapted runner
paths get syntax/diff review; qualification is not presented as a new test run.

Fresh runtime preflight: accepted Test255 config/notes/normal cmdline,
boot ID, Good battery,SOC5..<80,20..<38C,VBAT3500..<4300mV, Sink/Device,
DCC/candidate slots absent, no failed unit/new kernel fault, ADB/NCM/Wi-Fi,
Windows no Code43. Current Wi-Fi10.191.121.119 is reachable again on the same
0456f423 boot; older failed attempts remain failed, recovery cause is unknown.
Fresh five-partition/module verification occurs in TWRP before permanent writes
instead of duplicating it in Debian. Historical rollback/module/config records
remain the accepted Test255 baseline, not inferred from new values.

Commit/push registration before recovery request/reboot. Verify TWRP/root/UUID,
fresh five partition hashes and current181 modules; seal/check staged candidate,
rollback and helper files. Install ONLY boot/vendor_boot plus181 paired modules,
retain accepted Test255 modules in .gts9-test258-original and all older backups.
Read back all five partitions; init_boot/dtbo/vbmeta unchanged. Clear temporary
BCB/unmount, save install evidence, then normal system boot and150s observation.
Reuse old Windows image files; only the new helper occupies gts9-test258-a02.

Observation: candidate boot/config/notes, DCC absence, probe/driver/DT, ADB/NCM/
Wi-Fi/Windows gates. Combine boot ID, battery/SM5440 uevents, roles, failed units
and incremental kernel journal per5s sample; ADB every sixth sample. Full kernel
journal at boundaries/first fault, current181 module verification once at end.
No repeated partition/rollback hashes per sample. ADC values are reported only,
not calibrated independent VBUS/input power or OCP proof.

Stop first identity/evidence/install fault, unknown extra reboot, new severe
kernel fault/CPU stall, Code43/rescue loss, failed unit, I2C/probe/ADC timeout/
latched fault/stale or missing OFF-backed sample, nonzero pump mode, PPS/Source/
DFP, pack>=42C/VBAT>=4300mV, die>=60C or rise>=10C, reported PC VBUS outside
4500..5500mV/IBUS>100mA. No automatic experiment retry. Preserve first failure;
if deployed, recover exact accepted Test255 boot/vendor_boot and saved181
modules via verified TWRP, no other image/config change. If no write happened,
clean only this attempt's extraction/BCB and return the unchanged accepted pair.

This may qualify only passive probe and bounded reported telemetry. Independent
ADC calibration/protection/sensors/live PM/transaction acceptance remain pending;
active Stage3 NOT READY regardless of the passive result.
