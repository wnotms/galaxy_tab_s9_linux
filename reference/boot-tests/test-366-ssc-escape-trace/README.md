# Test366 — SSC discovery trace and native EF-DX710 Escape update

One candidate boot, ordinary switching/fixed-PD charging only. The previous
Test365 start produced no SSC QMI accelerometer within 60 seconds. This test
uses the exact Fedora-derived hexagonrpc 0.4.0 and existing Samsung registry
patches with upstream verbose output, line buffered, plus a bounded QRTR
nameserver inventory. It does not add a kernel diagnostic or merely increase
the failed discovery window. Missing oemconfig is an unresolved lookup,
not a demonstrated missing required binary. Do not copy another model's blob.

The owner requests the next physical boot also include the compiled EF-DX710
driver update. The new kernel maps grave↔Escape on both edges; all other keys,
firmware, power and PM behavior stay unchanged. Config/DTB equal the preceding
native sensor candidate; the only config delta versus accepted Test331 remains
QCOM_SOCINFO n→y. All 181 matched modules and native pen/palm CRCs are qualified.
The exact old early signed ADSP vendor_boot is reused without a new packing.
Linux pin stays 7.2-rc3. DCC stays off; OCI/UPower remain enabled.

Registration and all controlled inputs must be committed/pushed to origin/test
before any reboot/device mutation. Host build and existing qualifications are
reused for byte-identical inputs; no Actions, CI wait or full historical rerun.
`host_flow.py verify` is host-only. Stage Windows interop files only under
`D:\android\gts9-active\gts9-test366`, using ADB at
`D:\android\platform-tools\adb.exe` as currently requested by the owner.
Fresh preflight verifies original five partitions/181 modules, authenticated
Wi-Fi, ADB/device NCM, boot/journal attribution, Code43, DCC, ordinary roles
and Good battery 20–85%, 10–<42°C, 3.4–<4.44V. Existing baseline GNOME is allowed.

## Sequence

1. Install once through qualified TWRP: signed assets in the isolated prefix,
   namespace-specific original-module backup, exact 181 new modules, boot and
   vendor_boot readback. A reversible 11-file overlay backs up original input
   loaders/modules, installs qualified native profiles and an isolated trace
   binary. Only a registered condition flag prevents GDM/pen/palm during initial
   admission; graphical.target and display-manager links are not altered/masked.
2. Boot normally once. Attribute boot ID/history uniquely; accept exact new
   kernel/config/notes/partitions/modules, early authenticated ADSP/native SMEM,
   ADB/NCM/Wi-Fi and 30 seconds health. No late live ADSP start.
3. Prepare exact packages/account and copied registry with the existing volatile
   gate closed. Validate trace SHA, byte-identical installed libhexagonrpc and
   resolved line-buffered unit commands. Query QRTR nameserver once (2 seconds,
   ≤256 packets); complete wildcard enumeration is required and raw packets kept.
4. Start rootPD + sensorsPD once. SSC accelerometer discovery remains ≤60 seconds
   from launch, not from human connection/setup time. Keep native boot/health
   checks and unit state. Trace journal size cap 2 MiB; each daemon has independent
   systemd RuntimeMaxSec=120s/Restart=no if the host disappears. No duplicate
   userspace PD mapper, SDSP start, service enablement or production binary swap.
5. A finite plausible actual accelerometer sample is required before proxy start.
   SensorProxy HasAccelerometer must appear within 15 seconds. Preserve complete
   raw unit/kernel journals and a second QRTR inventory. Stop trace/proxy and
   remove the gate before slow final evidence checks; they do not become permanent
   runtime services just because the backend sample passed.
6. Only after backend PASS, remove just ms's interim XKB option on the exact new
   kernel, remove the text flag and start the qualified native input/GNOME pair.
   Confirm actual plain Esc/Fn+Esc, Ctrl+Alt+T and touch with the user. GDM and
   text-console event acceptance is recorded only when actually exercised.
   Rotation remains pending a later normal-runtime acceptance because the trace
   daemons are deliberately stopped; do not call sensor migration complete.

## First failure and rollback

Any new boot/identity/health/kernel fault, ADSP/PAS error, unknown mapping,
Code43, lost rescue, daemon failure, incomplete evidence/QRTR enumeration,
size cap or readiness deadline stops the scope. No second flash/start/discovery.
Remove gate/stop owned services before recovery; the daemon time limit is the
backstop when remote commands cannot answer. No PPS, pump or current increase.

Use the namespace-explicit recovery helper with **gts9-test366** for both actual
original and tested slots. Verify baseline and candidate hashes before rename
and before partition writes; never infer an absent Test364 backup means modules
are original. Restore the independently recorded desktop overlay and only owned
sensor assets using Test366 ledgers. Preserve full failed-boot journals offline
with absolute /usr/bin/journalctl; collection failures stay explicit while safe
baseline restoration proceeds. Restore exact Test331 boot/vendor and all five
partition hashes/181 files, then one ordinary attributed reboot when transport
and journal history are available. Restore interim XKB on exact Test331 and
normal GNOME. If the boot never became readable, preserve the attribution gap
and request recovery rather than sending blind reboots. Qualified passive SSC
packages/account may remain inactive; this is not byte-for-byte rootfs rollback.

Test331 rollback belongs to this active registration. Test365 first-failure and
its recovery evidence are immutable. Sensor bring-up/full port remain incomplete
until real runtime/rotation acceptance; higher-power charging follows sensors.
