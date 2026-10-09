# Test380 — live config metadata PASS, SSC discovery STOP, baseline restored

Registration648fd7f8 was pushed before device mutation. Fresh read-only preflight
ona1e7570f-4f1b-4068-b768-8e0edb0c457d passed exact config/notes/fivepartitions/181
modules, ADB/device NCM/authenticated Wi-Fi and Windows noCode43. Battery
100%,28.1°C,4.445V passed the registered3.4..4.45V observation
bounds. Charger4.44V setpoint/current/thermal policy unchanged. Test379's earlier
preflight STOP and exact preexisting USB row remain preserved, no future waiver.

One candidate boot16971083-2297-4220-a24f-24e113ba612d was uniquely attributed.
Only qualified early-ADSP vendor_boot and380-owned stock assets/text/RPC trace
were installed; accepted370 kernel/config/DTB/181 modules and persistent USB
remained unchanged. ADSP running/authenticated, FastRPC present, native519/MTP,
ADB/NCM/Wi-Fi normal; startup observation37.25s passed. No live GNOME late-ADSP start.

| Question | Observed result |
| --- | --- |
| Native Servreg | One endpoint, complete6domains, sensor_pd74, reply0.75ms |
| Runtime launch | rootPD then sensorsPD actually started once and active |
| Actual RPC config stat | **35/35 PASS**, exact sizes andmtime1640995200.000000000; no missing/mismatch/stat fault |
| SSC400 publication | Absent in failure inventory |
| Accelerometer | 23 probes in registered60s, all SSC QMI Service not found, no sample |
| SensorProxy/rotation | Not started/tested without real sample |
| Failed-boot kernel | Complete1110row offline JSON; no detected fault counts or unclassified suspects |

Metadata proves the actual returned size/time at this RPC boundary, not file
content consumption, selected registry group, electrical IMU response, SSC
publication or a completed sensor initialization. The isolated fstat cleanup
was not proven to cause/fix SSC absence. Do not repeat metadata/profile unchanged
or clear/rebuild the registry. Firmware initialization/hardware service
publication is now the next boundary to investigate. Trace still contains an
oemconfig.so lookup failure; necessity is unproven, not labeled root cause.

The first bounded discovery failure stopped this attempt. Gate removed, owned
RPC/proxy stopped; complete runtime/QRTR/kernel evidence retained. Automatic
rollback restored exact Test370 vendor and380-owned overlays/assets; five
partition hashes and all181 module files matched. Restored attributed boot:
178facf3-7e1e-4004-8041-cd70eb48df6d. Normal graphical.target/GDM/gnome-shell,
ADB/SSH/permanent USB active; ADSP offline, sensor gate and six owned payload
paths absent, RPC/proxy inactive, no failed unit. GNOME service/process recovery
is observed; no new user visual confirmation is claimed. Rollback ledger remains
for provenance, not an active diagnostic. Final battery100%,
28.2°C,4.447V; healthGood. No PPS/pump, no current increase, no kernel/config/DTS/USB
or adbd modification. No repeated hardware attempt.

120 affected host checks/no skips were executed for registration; ARM64 RPC and
kernel qualification reused. Result recording **executed:false** (no new test
run/build/full regression/CI). Raw journals preserve boot/source timestamps;
RESULT_SHA256.json verifies all registration, preflight, mutation, runtime and
restoration evidence. Sensor migration and automatic rotation remain incomplete.
