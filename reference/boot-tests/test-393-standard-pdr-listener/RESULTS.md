# Test393: sensor PD UP before and after RPC; SSC still absent

Candidate boot `dc892d1d-6129-4db8-b1ea-423042c7210b` passed exact five partition/
181 module/config/notes, early ADSP, native mapper/domain inventory, ADB/device
NCM and kernel health checks. Reused kernel/firmware/charging/USB/input unchanged.

Both private listener cycles succeeded. Notifier66/version1/instance74 at5:3
returned the initial sensor_pd state0x1fffffff **UP** before RPC and after the
registered30s observation. Each registration response arrived in about1.2ms;
each same-client unregister received result0/error0. Total cycle durations were
25.98ms and19.70ms including quiet drain. Both sockets closed, no retained
listener. No indications arrived, so device-side indication ACK was **not**
exercised; its interleaving/fault handling remains host tested only.

This is two attributed state snapshots, **not continuous UP-state history**.
The fresh-client unregister rejection in Test392 was an observer limitation;
the standard register/read/unregister sequence is now verified on this firmware.
UP does not establish SNS initialization, sensor availability or rotation.

One root→sensor RPC launch, healthy registered30s window. Complete raw kernel
and unit journals retained. All178 returned registry sessions/content hashes
and35 stat results matched; one missing oemconfig.so callback status69 was
acknowledged. Complete GLINK capture and RPC framing have no fault. The complete
QRTR inventory still contained no SSC400, so no accelerometer probe was issued.
Sensor data/physical rotation remain unverified. The pending final closedir
response is retained as pending, not fabricated as acknowledged/DSP parsed.

Exact Test370 five partitions/181 modules/config/notes and only owned overlay/
stock assets restored. Normal GNOME/palm/ADB/device NCM active on the restored
boot recorded in `summary.json`. No CPU/new severe kernel fault. Windows33
staging files were set/hash verified and deleted. PPS/pump/DCC remain OFF.

Results-only tests executed:false; reuse86 observer/domain and14 scope tests,
plus unchanged build qualification. No kernel rebuild/full regression/Actions.
Original Test392 rejection and both registration/result seals remain unchanged.

Next focus: SNS initialization after the now-observed UP domain. Compare the
exact X710 stock initialization inputs/callback semantics with the same-model
Fedora implementation. Do not reset/restart a domain already shown UP, guess
foreign firmware/configuration or replay this unchanged startup. Real SSC
publication, samples and rotation are still required to finish sensor bring-up.
