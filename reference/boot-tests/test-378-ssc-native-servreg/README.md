# Test378 — native Servreg response and complete Fedora RPC startup

Registered offline; not deployed or hardware-tested.

Purpose: distinguish an advertised/bound PD mapper from a real domain response,
then test one explicit rootPD-before-sensorsPD launch on the unchanged accepted
Test370 kernel. Test377 did not publish SSC and its runtime accidentally launched
only sensorsPD (`UNITS[1:-1]`). Its inactive rootPD was never evidence of a normal
handoff. Neither this defect nor duplicate mapper advertisements establish the
cause of the original Test372 failure, where both RPC units were active.

Use the existing native Linux mapper only. It already registers the X710
`msm/adsp/sensor_pd` domain, instance74. The unchanged stock asset archive includes
`adspr.jsn`, `adsps.jsn`, `adspua.jsn`; there is no missing-JSON justification for
another package installation. Preserve configuration mtimes and registry marker.
Do not clear/rebuild the registry or import another model's registry.

One physical attempt, after this registration and exact inputs are committed and
pushed to origin/test:

1. One baseline preflight: exact current boot/config/notes, all five partitions,
   181 paired modules, ADB/device NCM/authenticated Wi-Fi, healthy battery20–100%,
   10–<42°C and3.4–<4.44V. Reuse the byte-exact Test370 build qualification.
2. Install only the existing early-ADSP vendor_boot and five Test378-owned
   trace/text overlays plus the identical328 stock asset copies. No kernel,
   module, DTS, USB, charging, package or persistent desktop-policy change.
3. One ordinary boot, with GDM temporarily gated. Never late-start ADSP on the
   live desktop. Confirm changed/uniquely attributed boot, early ADSP firmware,
   FastRPC, native mapper and the registered health/rescue gates.
4. Complete same-boot QRTR inventory, requiring exactly one service64/instance257
   endpoint. Send exactly one read-only GET_DOMAIN_LIST (`tms/servreg`,2s), using
   the pinned Linux response layout. Retain request and full reply bytes. Require
   a complete response containing `msm/adsp/sensor_pd`, instance74 before RPC.
5. Launch rootPD, then sensorsPD, once each. Persist each intent before the start;
   require both processes active. A missing/skipped/exited rootPD stops, and is
   never interpreted as a handoff. Both trace units retain120s backstops,
   Restart=no,2MiB trace bound; no automatic restart or lost-reply retry.
6. Require an actual finite accelerometer sample within60s, then a15s SensorProxy
   backend check. Domain response/process active is not sensor acceptance.
7. Stop/deactivate owned runtime and restore the exact Test370 vendor/assets and
   ordinary GNOME endpoint on either outcome. Preserve the first failure and raw
   kernel/runtime/QRTR/domain evidence. No retry within this scope.

Stop on identity/boot/rescue/evidence failure, new kernel/thermal faults,
unexpected ADSP state, duplicate mapper, invalid/incomplete domain response,
missing sensor domain or RPC activation failure. All existing safety gates remain.
PPS, pump and HVC DCC stay off. Physical rotation is a later test after real samples.

Commands: `python3 host_flow.py verify|stage|preflight|install|discover|restore`.
Staging is host-only. No GitHub Actions, new kernel build or automatic main merge.
