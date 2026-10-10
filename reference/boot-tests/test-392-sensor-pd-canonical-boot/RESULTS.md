# Test392: notifier rejected unregister; domain state unknown

Canonical host identity correction worked: real candidate capture and runtime
prepare agree on boot `63a1a336-7a71-4354-9df9-54834e31a6be`. Exact partition/
module/config/notes, early ADSP, native mapper/domain inventory and ADB checks
passed. Kernel, charging, USB, firmware and registry content remain unchanged.

Fresh native domain inventory selected sensor_pd instance74; complete QRTR
inventory selected notifier66/version1/instance74 at5:3. Exactly one private
client sent REGISTER_LISTENER0x20 enable=0. Its same-peer response after1.095ms:

```
0201002000070002040001000900
```

This is QMI result1/error9, with no current-state TLV. The socket was closed;
the helper preserved raw request/reply and rejected completeness. The standard
QMI enumeration names9 INVALID_HANDLE ([primary implementation](https://github.com/openwrt/uqmi/blob/master/qmi-errors.h)).
Rejection of a fresh, never-registered client's unregister is consistent with
that name, but the firmware's internal reason is not proven. It does not prove
sensor_pd DOWN, UP, a dead DSP, or unsupported PD hardware.

Initial unknown state stopped **before RPC startup**. Runtime prepared-inactive
then deactivated/gated; no runtime-start command, second query, enable=1,
indication ACK or DSP restart was issued. No SSC/sample/rotation acceptance.
Missing RPC metadata in failure collection is expected because no RPC ran;
raw collection errors are retained.

Exact Test370 five partitions/181 modules/config/notes, normal GNOME/palm/ADB/
device NCM restored on the boot recorded in `summary.json`. Candidate and
restored journal checks have no CPU/new severe fault. Windows32 staging files
were verified and deleted. PPS/pump/DCC remain OFF; no physical retry.

Results-only tests executed:false, reuse13 scope and50 observer/domain checks
plus unchanged build qualification. No kernel rebuild/full regression/Actions.
Test391 format failure and both registration/result seals remain unchanged.

Next: qualify an observation using the actual Linux PDR listener lifecycle
(register, correlate state/indications, required ACK, unregister/close), including
bounded cleanup/failure tests. That is a **new separately registered scope**;
do not automatically escalate Test392 or repeat enable=0 on another fresh
client. Domain readiness remains unknown; firmware initialization, real sensor
samples and automatic rotation still need completion.
