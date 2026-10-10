# Test390 — status69 acknowledged, SSC absent, Test370 restored

One physical candidate boot `73210d40-86e8-4c61-a744-4ca9c4d7da99` followed pushed
registration860a748a. No repeated candidate startup or additional experiment.
The qualified daemon changed only actual missing-file status/diagnostics over
Test389; firmware, registry, library and other userspace inputs were unchanged.
The separate libssc wait and proxy early-claim fixes were not deployed.

The exact historical method19 request for `oemconfig.so`, environment
`ADSP_LIBRARY_PATH`, delimiter`;`, mode`rb` returned69 once at sensor-PD seq6.
The listener ioctl returned0, uniquely attributed to PID1787 and this boot.
This proves the corrected host callback/transport response, not DSP parsing
or a requirement to provide that library. No other failed callback was found.

All178 nonempty registry sessions match their exact stock byte hashes, and
35/35 config stat metadata match. The1030 sensor calls and pending final call
remain separately recorded. Final pending root handshake/sensor closedir replies
are not called acknowledged. Full raw kernel/unit JSON and parsed frames/content
are retained; matching returns do not prove firmware semantic initialization.

SSC400 stayed absent and no accelerometer measurement appeared in21 probes.
The registered query window was60s; the last probe ended59.437s after recorded
runtime start. The runner's63.905s `observation_seconds` includes the ending
sleep, evidence collection and verdict work; it is not an extended query window.
The original runtime summary is preserved unchanged. Top-level summary.json
distinguishes the registered window from elapsed time through the verdict.

GLINK collection is complete:2534bytes,17 events and zero overrun/commit-overrun/
dropped events on all8 CPUs. Candidate kernel classification found no CPU/
panic/RCU/CSD or new severe fault. This is a bounded observation, not a claim
that the historical stalls are all fixed. Sensor acceptance and physical
automatic rotation remain unproven. Verdict: `STOP_STATUS69_SSC_ABSENT`.

## Recovery and host state

Owned daemons stopped, then exact accepted Test370 was restored through TWRP:
all five partitions,181 modules, resolved config/notes and ordinary cmdline
matched; eight temporary overlay files and isolated stock assets were restored/
removed using their ledgers. No firmware substitution or registry reset occurred.
The subsequent ordinary boot `e43402eb-08bc-4528-853b-f5c423bd2974` was uniquely
attributed. GNOME/palm/ADB/device NCM are active, ADSP offline, no failed unit
or new kernel fault. Original rollback acceptance and raw evidence are retained.
Resume read confirms the same boot/desktop/ADB,100%,35.3C,4.446V.

Only ADB was the control transport; Wi-Fi and host NCM/SSH were not acceptance
requirements and were not claimed tested. PPS/pump/DCC stayed OFF. No kernel/
config/DTS/module/charging/USB/input implementation changed. Test390's31 exact
Windows staging files were hash-checked and deleted after recovery, reclaiming
225122695bytes. The recent image window is381–390; no Test380 image was present
in the controlled out/backups search and no new Image was built.

32 namespace/runtime/overlay/status host tests and105 callback/dependency tests,
18 ARM64 actual-C/VFS runs and2 upstream tests were reused unchanged. Results
only: additional regression `executed:false`, kernel build `executed:false`,
no GitHub Actions. Initial host fixture's NULL initial-handshake assumption and
the cache-inclusive draft seal were preserved and corrected before deployment;
neither was a device failure or a physical retry. REGISTRATION_SHA256.json seals
the registration, and RESULT_SHA256.json separately seals physical results.

## Next boundary

The missing-file return correction is real but is insufficient to start SSC.
Do not replay this candidate or add an unknown `oemconfig.so`. Continue with
firmware sensor initialization/selected X710 prerequisites and compare the exact
Fedora/vendor inputs; any new physical attempt needs a concrete changed input.
Sensor publication/sample acceptance precedes proxy/orientation acceptance.
