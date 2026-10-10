# SSC initialization: next evidence boundary after Test380

The Test380 failure remains unchanged: metadata matched, no SSC400 or actual
accelerometer sample in the registered window, accepted Test370 restored.
Do not rerun that profile, reset registry, guess bus addresses or late-start ADSP
on the normal GNOME boot.

## Evidence already available

The new host replay follows actual sensor-PD FD lifetimes, each linear read and
close. In boot `16971083-2297-4220-a24f-24e113ba612d`, PID1985 read **178/178
nonempty cached groups**, **203 reads / 44,863 returned bytes**. Every individual
session closed with exactly its frozen manifest length. `sensors_registry` is a
zero-byte marker, not a 179th observed group read. The separate version-marker
read is also not a cached group. The trace has no logged read failure, seek or
write during these sessions.

This proves logged returned lengths at the AP callback, **not** payload content
delivery to DSP, valid DSP parsing, active hardware transport, IMU response,
completed firmware initialization or SSC publication. The stat and read callbacks
print before the listener's next response invocation; they do not expose the
remote consumer's result. No root cause or electrical success follows from them.
The existing four core IMU leaf comparisons remain separate input evidence.

Exact raw inputs, per-file replay and qualification are in
[ssc-registry-read](../reference/desktop-bringup/ssc-registry-read/RESULTS.md).
Preserve all failed tests and their original manifests; this is a new derivative,
not an edit to Test380 evidence.

## Source comparison and rejected shortcuts

* Fedora X710 HEAD remains `ab123e7d1dbc0cbcd35661f9761197e977b15aa9`.
  Its root/sensor RPC ordering and registry mapping are already implemented in
  Test380. Its ADSP DTS also drops the unresolved LPASS interconnect and assigns
  hub4 pinctrl to remoteproc while hub3 uses GPI DMA. Re-copying those inputs
  does not introduce a new tested hypothesis. No new Fedora hardware fix was
  found in that comparison.
* S9 Ultra snapshot `4ff9d4b0ba1ae40e7605ad54c0ffe561c1e26a60` is cross-model
  evidence only. Its 64KiB listener patch is not a missing X710 fix: the
  qualified Fedora listener already fetches larger input buffers in a second
  invocation. Test380 has no logged oversized-buffer/decoder/method failure.
  Do not copy Ultra's registry timestamp reset or treat its SPI description as
  proof of X710's raw `bus_type` encoding.
* Samsung `msm-kernel/drivers/char/adsprpc.c` routes sensors attach to PD2;
  Linux `FASTRPC_IOCTL_INIT_ATTACH_SNS` uses the same PD2. Domain74 was actually
  returned by native Servreg in Test380. This does not establish successful
  sensor initialization and does not justify changing TCPM or DSP bus ownership.
* The collected X710 stock DSP set has no `oemconfig.so`. Its failed lookup is
  still of unknown necessity. No fabricated stub or foreign binary is justified.

## DSP log transport: inspect before enabling

The primary [linux-msm QRTR service table](https://github.com/linux-msm/qrtr/blob/master/src/lookup.c)
identifies SSC as400, DIAG as4097, and769 as SLIMbus control. Test380's complete
failure lookup has769 but **no4097**. Do not send diagnostic packets to769 or
mislabel it a DIAG endpoint. Absence from this lookup does not establish that
firmware offers no RPMSG diagnostic channel.

Source-only examination of [linux-msm/diag at23c12c1](https://github.com/linux-msm/diag/tree/23c12c167e93215853af4e59c021551767f6fec8)
finds RPMSG channels `DIAG`, `DIAG_CNTL`, `DIAG_CMD` and a QRTR backend for4097.
Its control handler negotiates features and sends masks; running the router is
**not passive read-only collection**. Its sample USB FunctionFS setup is not
appropriate for the accepted ADB/NCM gadget. No router, udev rule, USB function,
driver override or control packet has been installed or sent.

Current accepted config has `RPMSG_CHAR=y`, `RPMSG_CTRL=n`.
Linux7.2 `rpmsg_char` can create an endpoint when a matching RPMSG channel binds;
this does not prove any X710 DIAG channel exists or qualify rebinding one.
Do not enable RPMSG_CTRL or another kernel option just to satisfy old DIAG udev
examples. First establish the actual channel names and endpoint topology.

A fresh read-only probe on accepted boot178facf3 finds all six existing GLINK
version/version-ack/open/open-ack/close/close-ack trace formats available, all
disabled, tracer `nop`, no trace instances. ADSP is offline and the RPMSG list
empty, so this inventory cannot answer which channels a running ADSP opens.
It establishes that this next trace design does not need a new kernel option
or kernel rebuild. Formats are preserved in `trace-capability.stdout`; no trace
enable, mount, instance creation or ADSP start occurred.

## Next independently registered scope

The next physical scope must observe firmware/channel initialization, not
repeat the config-stat question. A suitable bounded design is:

1. Reuse exact accepted kernel/config/DTB/modules and qualified early-ADSP
   vendor inputs; freeze any new trace setup before registering/pushing.
2. Before early ADSP starts, use a dedicated bounded trace instance **only if
   the existing kernel actually exposes** GLINK version/open/close events.
   These events are defined in `drivers/rpmsg/qcom_glink_trace.h`; names and
   format must be verified against that exact kernel. Preserve original trace
   state and never trace all payload traffic. Missing events stop this plan
   before deployment, rather than prompting an automatic kernel rebuild.
3. Capture channel names/remote labels, RPMSG sysfs ancestry, driver bindings,
   QRTR announcements and full kernel journal at early-start and after one
   ordered root/sensors startup. Record source timestamps and trace overrun
   statistics; an overwritten or un-attributed trace is not complete evidence.
4. Cap observation at60s and collection at2MiB; no service restart or diagnostic
   packet, RPMSG bind, bus probe, registry write, firmware replacement or retry.
   A DIAG channel inventory is a diagnostic result, not a sensor PASS.
5. Restore Test370/vendor and all owned trace/text/assets on either result,
   then normal GNOME. Stop immediately for new CPU/kernel/USB fault, unexplained
   reboot, lost rescue, or the existing battery/OFF gates. Preserve fixed-PD,
   4.44V float, thermal fail-closed, DCC/PPS/pumpOFF.

This design is **not yet a registered/qualified deployment**. There is no
Test381 hardware acceptance or permission to silently add DIAG control traffic.
If channels are absent, analyze their initialization/open handshake first. If
present, separately qualify a bounded decoder/control protocol from actual
X710/primary source before requesting firmware log masks. No automatic rotation
claim is valid until actual accel samples and SensorProxy orientation pass.

## Test383 result and the next transport boundary (2026-10-10)

Test383 now completed the registered early-to-post-RPC GLINK observation:
17/17 events, zero loss on all eight CPUs, no additional channel events after
the early QRTR/FastRPC handshakes. Both RPC roles started once, 35 config-stat
checks match, no SSC400/sample in60s, no DIAG-named channel or QRTR4097. Exact
Test370/GNOME restored. This is a bounded absence observation, not proof that
firmware cannot respond to an AP-initiated diagnostic channel. Preserve the
original preflight STOP, exact enrollment amendment and host interruption.

Source-supported next route: upstream GLINK registers an rpmsg_ctrl parent
even with the control driver disabled. Fedora X710 resolves RPMSG_CTRL=m;
our config has it disabled. The unmodified Linux7.2 control module is now
offline compiled against the accepted provider with32 matching CRCs and exact
ELF/config identity. This does not enable an old udev recipe or fix SSC by
itself. No module/endpoint/diagnostic router has been deployed. See
[offline qualification](../reference/desktop-bringup/ssc-rpmsg-control/RESULTS.md).

Next Test384 should ask only whether the exact ADSP parent accepts one local
DIAG endpoint OPEN. Register/push before loading the qualified temporary module
in a controlled early-ADSP text boot. Admit exact boot/config/notes/module
build-ID and unique controller ancestry. Use standard CREATE_EPT, then one
read-only endpoint open (GLINK's5s+5s wait under15s external deadline); capture
raw control events and at most one64KiB unsolicited packet with1s poll. No
DIAG_CNTL/DIAG_CMD, feature/mask/data writes, driver override, RPC restart or
foreign firmware. Close/destroy through the same FD; on failure don't reopen
or unload a live control driver. Always restore370/vendor/owned overlay and
normal GNOME by reboot. A temporary external module is diagnostic runtime,
not unchanged production, despite an unchanged Image/config/181-file directory.

This new offline helper is not yet a complete Test384 deployment runner. A
positive handshake would justify a separately bounded decoder/control design
from actual X710 responses; a negative result needs its first complete failure
analysis. Neither permits silent full-router/mask activation or a sensor PASS.

## Test386: ACK alone is not an endpoint (2026-10-10)

The earlier next384 plan is historical. Test384 stopped on recovery ADB closure
before candidate installation; Test385 passed stable recovery admission but
found an inherited8-file installer allowlist versus5-file minimal manifest.
Both first failures and recovery evidence are preserved. Test386 corrected that
actual host defect and exercised12 real temporary-root install/restore/fault
cases before physical deployment;83 affected host tests passed, zero skips.
No Image/config/DTB/181-module rebuild or USB/charging driver change.

One attributed candidate `26ad9a13-4f2d-4a9a-a42f-9c8c7491027d` loaded the matched
native control module and issued exactly one local DIAG open. The complete
zero-loss GLINK trace contains19/19 events (2754bytes): `tx OPEN DIAG[3/0]`,
`rx OPEN_ACK DIAG[3/0]`, **no reciprocal remote OPEN**. The character-device
open returnedEINVAL after about5.22s of host command time. Stock7.2 GLINK waits
first forACK, then forremoteOPEN,5s each. Timeout returnsERR_PTR, create_ept
maps that toNULL, and rpmsg_char mapsNULL toEINVAL with `failed to open DIAG`.
This supports a second-stage wait timeout; it does not show malformed UAPI,
complete application service, firmware's permanent lack of DIAG, or SSC rootcause.
The trace clock islocal; do not subtract crossCPUtimestamps for exact latency.

The first failed-open journal suspect remains intact. No payload/mask/feature
request, RPC launch, endpoint reopen or live module unload occurred. Mandatory
baseline reboot cleared the orphan endpoint/module. Exact Test370/GNOME was
restored in boot `d8654881-69bd-4603-92ee-8e14a3f81ad9`, with all five partitions,
181modules/config/notes/fullkernel/ADB/deviceusb0/palm accepted. WiFiSSH/hostNCM
TCP were outside the currentADB-only scope. See
[Test386 raw result](../reference/boot-tests/test-386-diag-minimal-overlay/RESULTS.md)
and its `GLINK_ANALYSIS.json`/source excerpts/first failure/rollback evidence.

The next source comparison must distinguish transport acknowledgement from
remote application initialization. Check the exact X710 firmware's DIAG channel
lifecycle and whether its stock/Fedora RPC startup or control-channel sequence
actually supplies a documented prerequisite. The primary linux-msm/diag router
opensDIAG beforeDIAG_CNTL/DIAG_CMD; a generic router is neither an explanation of
this reciprocal-open gap nor passive collection. Its feature/mask writes remain
outside all completed registrations. No demonstrated source prerequisite yet
justifies those writes or a TCPM/USB/kernel change.

Do not repeat the unchanged one-shot probe, guess firmware channel names, reset
registry, fabricateoemconfig.so, or claim a sensor fix from this ACK. Select a
new bounded action only after a source-supported difference or actual startup
prerequisite is identified. Existing Fedora RPC implementation is already
imported; reference reuse must introduce a real change rather than another
unchanged60s SSC wait. Actual accelerometer samples and SensorProxy orientation
remain required for sensor/rotation completion.

Documentation-only update: `executed: false`; reuse Test386's83 host tests and
exact build qualification. No device operation, build/full regression orCI.

## New offline RPC repair after the source comparison

The Fedora0.4 transport is already in use (including Test378's exact verbose
daemon); its current HEAD remains the auditedab123e7d. Comparing primary
Qualcomm `listener_buf.h` against the actual pinned codec found an actionable
wire defect: zero-length input parameters are not advanced, and zero-length
output size calculation pads a header that the encoder does not pad. Odd-size
payloads also leave the next size header unaligned. Native tests compile the
original C and reproduce the first two failures, then verify a one-file patch
against independent wire vectors. ARM64/QEMU and native UBSan pass. See
[wire qualification](../reference/desktop-bringup/ssc-rpc-wire/RESULTS.md).

This is a new source change, not an unchanged DIAG retry or wholesale RPC API
upgrade. It is still **not an established SSC rootcause**: old text traces did
not expose encoded buffer sizes or prove a real empty-parameter invocation.
Do not retroactively claim a prior failure was explained. A future independently
registered one-startup/60s SSC test can evaluate this corrected Fedora-derived
daemon with the accepted Image/config/DTB/181 and isolated stock data unchanged.
It needs actual400/sample/orientation evidence for acceptance and mandatory
exact370/GNOME restore, first-failure preservation, no masks/restart loop/PPS.
No new hardware attempt has been registered or performed in this offline step.
