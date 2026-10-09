# Test380 — bounded SSC RPC metadata on explicitly enrolled baseline

One independent early-ADSP boot/one ordered rootPD+sensorsPD launch, reusing the
qualified RPC stat diagnostic fromc0ba0bfe and accepted Test370 kernel/config/
notes/181 modules. Test379 stopped in read-only preflight, physical attempts0.
It is not passed or retried; all raw evidence remains there.

Enroll its complete sameboota1e7570f kernel journal and existing priority3 rows
by exact cursor/content in ENROLLMENT.json. The new ep0out no-queue diagnostic
was adjacent to a sameboot permanent lifecycle unbind in journal sequence/time;
source timestamp differs from journal reception, so no claim of a qualifying
Test368 source-time boundary. Pinned FunctionFS/DWC3 source explains the branch;
actual ADB/authenticated Wi-Fi recovered. This enrollment does not prove every
USB fault harmless or authorize any additional diagnostic. Every new kernel
error after the enrolled baseline still stops. No source/error regex waiver.

Battery admission: Good/present, unchanged4.44V design/float setpoint, SOC20–100%,
temperature10–<42°C, measured VBAT3.4–4.45V inclusive.4.45V is an explicit host
observation stop policy [BRINGUP_LIMIT], not a vendor OVP/measurement tolerance/
new charging setting. Any missing/invalid telemetry or bounds violation stops.
DCC/PPS/pump remainOFF. No current/thermal/USB/adbd/GPU/input changes.

Register/push before mutation, fresh authenticated preflight≤600s. Write only
qualified early-ADSP vendor_boot and380-owned stock assets/trace/text overlay.
No kernel build/config/DTS/modules/packages/charging changes. Own namespace
gts9-test380, rollback restores exact Test370 vendor and own overlays/assets;
normal GNOME at completion on either result. No late ADSP on live GNOME.

Startup30s, ADB/device NCM/Wi-Fi≤90s, QRTR2s/one native Servreg2s query; no
duplicate mapper. Start rootPD then sensorsPD once; RPC120s/no restart/2MiB.
SSC60s/real finite accelerometer sample; all35 exact sameboot sensorsPD config
stat size/mtime required, preserving frozen archive/cache/marker/timestamps.
SensorProxy15s only after a sample. Metadata alone is not sensor or rotation
acceptance. No sample/domain/metadata/ADSP/rescue/identity/fault means first STOP
and immediate cleanup/restoration; no restart/reflash/repeated attempt.

Reuse exact ARM64 daemon e1e9faa4/unchanged library1be44d2f and early vendor
158e3826, rollback vendor efddf31c. No CI/full host rerun/kernel rebuild; only
affected ownership/admission/runtime/metadata tests. Fresh live acceptance still
required; no physical success claimed in registration.
