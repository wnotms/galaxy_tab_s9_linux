# Test324 — fixed9V OFF native single-shot acquisition

Purpose: one source-powered candidate boot, four once-only native single-shot
conversions, each within unchanged100ms deadline/READY/status/checked restoration.
No PPS, pumpON, native actuator/controller, masks/ENHIZ/protection/current raise,
DTS/TCPC/USB/adbd/rootfs/temperature/current policy change. Fixed9V<=1.5A and
float4.44V preserved. A successful observation is not calibration/current/OCP
or active direct-charge acceptance. Full charging port remains NOT_READY.

Qualified source ab30aff2 and exact package from
`reference/charging/sm5440-native-oneshot/`:139affected tests, ARM64 build,
config only newONESHOT=y, sameDTB, matched181. Reuse; do not rerun/rebuild for
registration. New parser/lifecycle/baseline tests execute separately.

Entry: exact accepted323 normalboot/config/notes, allfive/181 checked once,
20–<80%SOC,3.5–<4.3VBAT,20–<38C/Good/present/realthermistor,
ADB/NCM/authenticatedWiFi/SinkDevice/WindowsCode0. Current original311 saved
module directory is retained independently; new `.gts9-test324-original`
saves actual323 for this unconditional rollback. No archive/provider mixing.

Sequence: publish registration/preflight/package/tests on origin/test first.
Install boot-only +181 via qualified TWRP helpers; allfive readback, clearBCB,
unmount. **No automatic candidate reboot.** Owner then disconnects PC in TWRP,
connects known Lenovo YG65G USB-C2 alone (18W), and chooses Reboot System once.
Collect through authenticated WiFi, same known SSH key and machine/config/notes;
if DHCP changes, enroll the new address only after these identities match.
No cold/battery experiment, second candidate boot, replay/rebind/trigger.

Readiness bounded150s, stop as soon as native acquisition or startup faults
appear; services are not a reason to reinterpret a native fault. Save full
raw oneshot/snapshot/source/pack/kernel JSON/boot history before classification.
A successful four-sample result gets one15s sameboot endpoint. Physical range
VBUS4.5–9.5V, VBAT3.5–<4.3V, IBUS0, die<42C; pack20–<38C; new READY, exact ADC
field restoration0c/df, no converter reuse/stale epoch. No fault/extra boot/new
systemd/kernel failure/transport loss. First non-clean stops the test.

Unconditional rollback after capture or first non-clean: owner disconnects
charger and reconnects PC without reboot, then restore exact323boot/original181,
allfive readback, clearBCB/unmount, one normalboot with current PC5V grant capped
1.8A and identity/rescue/thermal/kernel checks. If ADB/SSH unavailable, request
manualTWRP and preserve persisted mutation state; no blind writes/reboots.
Data is kept on first failure before cable change; restoration does not wait
for publishing. Pump remains OFF throughout; no safety qualification grant.

Keep raw evidence and errors; host-only logging defects stay separate from
actual device failures. Retention window315–324; current323 operational rollback
is assigned to this round. Old diagnostics remain historical, not production.
