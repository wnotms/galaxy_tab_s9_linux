# Test391: stopped before notifier query, exact Test370 restored

Candidate `9004368f-dd70-43f6-a2ad-c380df78c63b` passed attributed early ADSP
startup, exact five partition/181 module/config/notes checks, ADB/device NCM,
and kernel health. Kernel/firmware/charging/USB/input remain unchanged.

Runtime prepare stopped at its first identity check. The host passed the stored
32-character UUID hex to a runtime check comparing the captured canonical UUID
with hyphens. Both represent the same boot. This is a host input defect, not a
CPU stall or evidence about sensor PD readiness. The initial source/registration,
raw error and first failure remain unchanged.

No runtime ledger/gate was created; no RPC daemon start or notifier query was
performed. sensor_pd state, SSC publication, accelerometer and rotation remain
unverified. Failure collection lacks RPC metadata because RPC never started;
those collection errors are retained, not fabricated as a pass.

Automatic cleanup restored exact Test370 five partitions/181 modules/config/
notes and removed/restored only owned overlay/stock assets. Restored boot and
normal GNOME/palm/ADB/device NCM are in `summary.json` and the complete rollback
evidence. Windows32 staged files were hash/set verified and deleted. PPS/pump/
DCC remain OFF. No physical retry of Test391.

Results-only tests executed:false; reuse registered12 scope tests and50 notifier/
domain tests plus unchanged build qualification. No kernel build/full tests/
Actions. Next change must normalize the host runtime boot ID and exercise a
real captured identity against the runtime validator before any new attempt.
Sensor PD has still not been queried; do not infer UP/DOWN from this result.
