# Test373 — SSC discovery with Fedora userspace pd-mapper

Purpose: resolve the Test372 `SSC QMI Service not found` failure. Test372
proved early ADSP, the native auxiliary mapper and QRTR inventory, but the
Debian rootfs did not contain Fedora's userspace `pd-mapper`. This scope adds
only the qualified `libqrtr1` dependency and `pd-mapper` package, starts the
mapper before rootPD/sensorsPD, and removes both during cleanup.

Reuse the byte-exact signed X710 early ADSP vendor_boot qualified by Test365,
328 copied firmware/RFSA/registry assets with original mtimes, installed Fedora
hexagonrpc0.4.0/libssc0.4.4/proxy3.9, and already compiled verbose RPC executable.
No new kernel, config, DTB, module, keyboard, palm, charging, USB driver/profile
or SSH changes. Only vendor_boot is writable. Existing 181 modules stay in place.
The native kernel mapper remains observed, but is not treated as a replacement
for the userspace daemon. Missing `oemconfig.so` remains an unresolved lookup,
not proven required firmware; no other-device binaries or stock persist writes.

Register/push before mutation. Verify one fresh actual identity, all five
partitions,181 module hashes, ADB/device NCM/authenticated WiFi and no Code43.
Good battery20–85%,10–<42°C,3.4–<4.44V; DCC/PPS/direct OFF and Sink/Device.
Keep exact enabled USB lifecycle profile/helper across the unchanged kernel.

1. One qualified recovery entry; install only owned copied assets and five-file
   trace/GDM-text overlay, write/readback only vendor_boot. Do not swap modules.
2. One ordinary boot, unique persistent boot attribution, early ADSP running,
   native SMEM mapping, FastRPC and rescue;30s bounded health. No late DSP start.
3. Verify four already-installed SSC packages and exact incoming `libqrtr1` /
   `pd-mapper` packages; install/configure only those two, with closed gates.
   Copy actual native SoC fields, set only FastRPC node/copy permissions. Require
   bound auxiliary mapper; keep full QRTR raw before/after lookup (2s/256 packets).
4. Launch rootPD/sensorsPD exactly once. Actual finite plausible accelerometer
   sample required within60s from launch. Each trace unit has120s independent
   RuntimeMaxSec,Restart=no;2MiB trace cap. No infinite daemon/start retries.
5. Only after real sample, start SensorProxy≤15s and require HasAccelerometer.
   Preserve full raw RPC/kernel journals. Gate off/stop trace and proxy first.
6. On either outcome restore original vendor_boot and only owned assets/overlay;
   return to accepted Test370 GNOME with current USB/clock/input unchanged.
   Backend PASS is not persistent sensor/desktop rotation acceptance; a successful
   backend leads to a separate normal-runtime registration.

First unknown identity/new reboot/kernel/ADSP/thermal/transport/Code43/evidence
or daemon/readiness failure stops; no second start of failed scope. Durable
mutation ledger exists before recovery. Partial asset/overlay transactions are
restorable using Test373 namespaces. Preserve original and candidate partition
hashes; never overwrite an unknown partition. Offline failed-boot journals use
/usr/bin/journalctl. If rescue is lost, retain recovery-required and use manual
TWRP instead of blind repeated reboots. Passive packages/account and already
closed90 gates stay; original Test370 rollback namespace is never touched.

Local changed-scope tests only; no kernel rebuild/full historical run/Actions.
Windows staging under D:/android/gts9-active/gts9-test373, ADB under
D:/android/platform-tools. Stage only candidate+original vendor and small assets,
not duplicated boot/modules. The retained earlyADSP vendor image is reused
byte-for-byte from Test372; original efdd is current runtime rollback.

Read-only preparation enrolled the original d197 boot before registration. A
past physical pogo hot-reconnect emitted one -ENXIO event-transfer diagnostic,
then completed its MCU handshake after1retry within0.5s. Exact full row/source
context is frozen in registration, not a future error waiver. One prior owned
permanent-helper ep0 teardown is correlated within250ms. Full prior raw journals
and original classifier rejection are retained under ssc-current370-preparation;
fresh preflight compares exact same-boot journal cursors and rejects new errors.
