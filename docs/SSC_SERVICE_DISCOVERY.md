# SSC service discovery after Test377

The accepted endpoint remains Test370 with ordinary GNOME startup. Test377 was
restored; its failed SSC discovery does not qualify accelerometer/rotation.
Analysis and exact source/raw-input hashes are in
`reference/desktop-bringup/ssc-service-discovery/analysis.json`.

## Evidence corrections

* The actual328-file stock archive contains `adspr.jsn`, `adsps.jsn`, and
  `adspua.jsn`. All describe X710 ADSP domains, instance74. An absent JSON
  dependency is not supported. The current baseline has no such files because
  the candidate-owned assets were correctly removed on rollback.
* Test377's complete QRTR inventory has one native service64/instance257 before
  startup and two endpoints afterward. This proves duplicate advertisements,
  not that either server caused the failure. No endpoint advertises SSC400
  (`QMI_SERVICE_SSC=0x190` in the actual builder's libqmi header). Service69 is
  not SSC. Kernel binding, an advertised mapper, and SSC publication are three
  different observations.
* Test373–377 define `UNITS=(rootPD,sensorsPD,proxy)` but start `UNITS[1:-1]`.
  Thus their registered rootPD start was omitted. The assertion that rootPD
  normally exited after a handoff is unsupported. Test372 did start both and
  still failed; correcting the omission alone is not a proved root-cause fix.
* The sensor trace reads the copied registry and stats configuration JSONs.
  Stat without opening JSON is consistent with the timestamp cache, not proof
  of failed JSON selection. The S9 Ultra helper explains why mismatched mtimes
  provoke a rebuild and unsupported local registry operations. Keep X710's
  own2022 mtimes/cache/marker; do not apply the Ultra's epoch0 normalization.
  This trace alone does not prove a successful cache hit or complete registry.
* `oemconfig.so` lookup failed; its necessity remains unproved. Do not invent a
  substitute library or copy a different model's sensor registry.

The same-model Fedora HEAD remains `ab123e7d1dbc0cbcd35661f9761197e977b15aa9`.
The current runtime already uses its hexagonrpc0.4.0 and three patches, libssc
0.4.4 and patched proxy3.9. A second wholesale copy would not correct the runner
defect. Fedora's `docs/PORT-KIT.md` also records a boot where sensor discovery
failed; its source reuse is not evidence that every SSC boot succeeds.

Historical Test372's missing-userspace-dependency attribution and Test373–377's
handoff commentary remain historical hypotheses, superseded by this analysis.
Do not rewrite raw verdicts or claim those tests passed. Current tracked
Test373–376 trees retain registration/tool inputs but lack their complete raw
physical outputs; use preserved Test372/Test377 evidence for reproducible claims.

## Next implementation

`userspace/sensors/servreg-domain-snapshot.py` sends one GET_DOMAIN_LIST query
for `tms/servreg` to an endpoint proven by a complete same-boot inventory. It
does not start remoteproc, register a mapper, change a listener or retry. It
retains the entire wire request/reply, enforces a2s registered bound (maximum3s),
validates peer/transaction/message/TLV/domain lengths and boot identity, and
requires a complete page before reporting complete evidence.

Response layout is explicit, since the pinned Linux mapper's nested strings
use u8 lengths (`SERVREG_NAME_LENGTH=64`) whereas pd-mapper1.1 uses u16
(`name[256]`). Sources are the actual Linux `qcom_pdr_msg.c`, `qmi_encdec.c`,
`pdr.h`, and Fedora-pinned `servreg_loc.c/.h`. Never silently choose the other
layout to make a malformed response pass. A verified sensor domain is still
not SSC publication or an accelerometer sample.

`userspace/sensors/ssc_lifecycle.py` names both rootPD and sensorsPD explicitly,
checks inactive state, persists each start intent, starts them in order, and
checks both processes. Lost replies consume the attempt. The caller retains
the existing boot/text/gate/trace/cleanup controls; this helper never starts
ADSP or installs a mapper. Process active is not protocol readiness.

Test378 integrates both helpers and reuses the unchanged early-ADSP vendor,
stock assets and Test370 kernel/modules. Its new question is whether the native
mapper actually supplies the correct domain before a complete ordered launch.
Duplicate/invalid/negative answers stop before RPC; sensor discovery has one
60s window. Restore baseline GNOME on either outcome. No extra userspace mapper,
registry rebuilding, kernel change, charging escalation or late ADSP start.

## RPC stat follow-up (offline)

A separately pinned diagnostic now repairs the real fstat-error descriptor leak
and incorrect errno reporting, and records successful size/mtime. The original
C callback reproduces the leak in a filesystem fault harness; the patched one
survives1024 injected failures. Successful96-byte metadata ABI, including the
Qualcomm reference's unusual ctime encoding, is unchanged. Test378 did not record
this failure, so this is not a proved SSC root-cause fix.

The X710 archive's35 cached config mtimes all match their archived files. This
is host-input evidence only; the next registered attempt must compare actual RPC
size/mtime and initialization/publication, not reset the registry. The independent
ARM64 diagnostic is compiled with an unchanged companion library,64 affected
host tests pass, and nothing was deployed. Qualification and exact hashes:
`reference/desktop-bringup/ssc-rpc-stat/RESULTS.md`.

## Core IMU cache comparison

The separate host checker `userspace/sensors/registry_core_audit.py` compares four
X710 core IMU leaves against the copied registry: platform bus settings,
orientation, accel and gyro config all match exactly. It reads the hash-bound
archive without extracting or changing anything. This is not selector/electrical
bus/SSC evidence. In particular, i3c_address alone does not identify active I3C;
bus_type3 remains an unverified X710 encoding despite the Ultra's SPI description.
No AP bus probe, registry rewrite or bus ownership change is justified by these
fields. Preserve factory calibration and vendor config extensions. Evidence and
42 affected host checks: `reference/desktop-bringup/ssc-core-registry/RESULTS.md`.
Test379's live RPC metadata question remains unexecuted behind its voltage gate.

## Desktop observation

The read-only current snapshot records boot
`9d6d50ca-6886-4dd5-9e34-357e74e230ca`, `graphical.target`, GDM running and a
GNOME Wayland greeter with the built-in DSI monitor selected. Its screensaver
was active and DRM output disabled when sampled. This is evidence of an idle
greeter; it cannot establish what the user saw earlier or prove that a reported
persistent log screen is fixed. User wake/visual confirmation remains separate.
