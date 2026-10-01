# Test270 — high-power physical readiness preflight

Owner explicitly authorizes continued physical testing after Test269. This
read-only stage checks actual current readiness before any active test. Installed
Test263 is expected; Test269 was compiled/host-tested but has no live adapter.
No retarget function is claimed exercised on the tablet by this registration.

One bounded Wi-Fi command saves boot/config/notes, complete battery/USB/passive
properties, original cached snapshot, network/roles/services and failed units.
If reachable, save full source-timestamped kernel JSON and human-readable journal.
No repeated hashes of partitions/modules already unchanged; no build/full rerun.

A known failed/stale monitor, missing fresh ADC/current/protection/live adapter,
or out-of-range battery entry is NOT READY. Preserve fault0x80 rather than clear,
mask, unbind, restart, raise the <4.3V gate or request PPS/pumpON. Do not reflash
an unwired policy core as though that exercised high-power charging. This stage
has no charging window/cable action; stop at preflight when gates cannot pass.

Normal battery/SSH response is recorded separately from active-charge readiness.
Test267 STOP remains unchanged; the existing18W PD label does not prove APDO.
No flash/reboot/current/thermal/USB/rootfs change. No rollback needed. Evidence/
registration-only change reuses Test26955/all1396/build qualification; new host
regression/build executed:false. User physical authorization is recorded but
cannot supply missing implementation or measurement evidence.
