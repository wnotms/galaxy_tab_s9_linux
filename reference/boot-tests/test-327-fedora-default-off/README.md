# Test327 — Fedora X710 charging source default-OFF acceptance

Owner authorized flash/testing on2026-10-06. Test327 first accepts the new
Fedora SM5440 driver with direct charging OFF. It does not request PPS or start
the pump. The following PPS1.8A stage requires a separate registration/hashed
boot opt-in, SOC<80 and the entry conditions in the source qualification.

Candidate source376693d7, offline qualificationf105ffed; reuse155 affected tests,
final15 overlapping metadata tests, ARM64 build75.858s, W1/sparse12.344s and
exactDTB/181 paired modules/protected-file audit. No new kernel build/full suite.
The new runner/gate has21 host tests PASS; no ADC repair/profile is used.

One combined read-only baseline preflight: config/notes/normalboot, real pack,
OFF CNTL5, deviceADB + authenticatedUSB NCM (WiFi also checked), full journal/history, allfive and181.
Ordinary default-OFF flash entry SOC20–<95, VBAT3.5–<4.4V, pack20–<38C. This
intentionally separates ordinary charging admission from PPS eligibility; the
current82% pack is not eligible for direct charging.

Registration is committed/pushed before BCB/recovery/writes. Through verified
TWRP: stage hash proof, backup current181 modules in unique327 slot, swap paired
candidate, writeboot only, verifyallfive/181, clearBCB/unmount; one normalboot.
Require unique attributed newboot, exactconfig/notes/roles/services/defaultN,
new boundprovider, atomic read-only CNTL5 showingOFF. Observe30s onPC with four
pack/OFF samples; positive endpoint battery current and no newkernel fault.
Device-side NCM normal completes network scope; no repeatedWindowsTCP probe.

First realfault stops; verify/restore exact323 boot/saved181 through TWRP,
allfive readback/clearBCB/unmount, one restorednormalboot. Lost rescue requests
manualTWRP and never blindly repeatsflash. Retain candidate only after actual
device scope PASS. No rootfs/USB/DWC3/SM5714/DTS/protection/current change.
Readiness deadline90s, preflight freshness600s. A host publication defect after
completed physical gates is separately recorded and does not reflash/retest.

Windows stage D:\android\gts9-active\gts9-test327; ADB remains
D:\android\platform-tools\adb.exe. Candidate/rollback hashes in PACKAGE.json;
unique backup slots in module-swap.sh. No additional full build tree.

Read-only preflight01 stopped at host WiFi unreachable, no mutation. Independent
NCM SSH authenticates the same device/boot. This PC-only default-OFF registration
allows that USB rescue without claiming wireless acceptance. All charger/PPS
cable-removal stages still require fresh authenticatedWiFi; no activation here.

Final preflight is READY:83%/4.290V32.2C, allfive/181 match323, physical
pumpOFF verified, authenticatedUSB NCM. Earlier host failures retained under
preflight01/02; no device mutation occurred in either.
