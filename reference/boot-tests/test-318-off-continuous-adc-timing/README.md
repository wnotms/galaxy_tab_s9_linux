# Test318 — one OFF continuous ADC timing boot

Purpose: measure software brackets for eight continuous SM5440 READY events on
PC fixed5V, using the actual integrated `44c2190a` OFF diagnostic. Test317's
one-shot interval did not isolate continuous cadence. No repeated unchanged
Test317, PPS Request, pump ON, current increase or protection qualification.

Current/rollback is original Test308 passive kernel, physically accepted in
Test311; full paired boot/config/notes/181 module values are in PACKAGE.json.
This retained operational rollback is attributed to this new registration,
within the Test309–Test318 retention window despite original artifact names.
Candidate changes only diagnostic configuration/source; DTB exactly unchanged.
Reuse final ARM6483.143s/W1-sparse6.177s and affected196-test qualification under
`reference/charging/sm5440-continuous-timing/`. Packaging is offline: exact
qualified artifacts, header4/100663296bytes, unpacked Image.gz+DTB verified, no
cmdline change. No new kernel build, full regression or Actions.

## Entry and one physical sequence

At preparation, accepted311 boot ac442c81 is on PC USB and battery draining.
Latest independently recorded maintenance packet has SOC4%,3.634V,31.2°C,
Good/present, signedcurrent -1.058A, ordinary SDP500mA. No flash is permitted
at that state. Owner has been asked to connect accepted C2 ordinary18W charging;
no connection or charge recovery is inferred. Wait for genuine SOC20–<80%
reserve before entering recovery; actual pack20–<38°C/VBAT3.5–<4.3V/Good/present.
Do not modify charging settings to meet a gate.

After charge recovery, PC USB remains connected for this experiment. Capture
fresh baseline/config/notes/normal cmdline, allfive hashes, exact181 modules,
cached pump OFF, real pack thermal, services, Sink/Device, ADB/device NCM and
authenticated Wi-Fi rescue. One host NCM probe is recorded separately; it
does not impose repeated host waits on normal device acceptance. WindowsCode43
is an actual STOP. Snapshot reads are cached, not register triggers.

Commit/push this registration and exact frozen INPUTS before mutation. One
validated normal Debian→TWRP transition, machine/root/partition checks, paired
module install, boot-only write and allfive readback. Clear BCB/unmount and one
normal candidate reboot on PC fixed5V. No charger change/cable dance/OTG.

Readiness is bounded150s, stopping immediately on a reported driver refusal.
The converter itself is one attempt: vendor50ms rearm/AVG32/RATE1, eight new
READY events each≤500ms, entire transaction including exact disable/restore
≤2000ms. These diagnostic limits do not change the active100ms gate.
Save complete boot-attributed kernel journal/history, full cached snapshot,
native source/pack brackets and allraw ADC/INT/status/controls before judging.
Require fixed5V source/current epochs and healthy pumpOFF/zeroIBUS, original
fixed budget ceilings, no native/ADC/cleanup/role/rescue/thermal/newkernel fault.
One15s endpoint in same boot checks response and unchanged cached evidence;
no second conversion, resume experiment or replay on a first non-clean.

Unconditionally restore exact accepted311 boot/original181 modules, verify
allfive, clear BCB and ordinary final boot/config/notes/pack/thermal/ADB/device
NCM. A failed command/unknown layout never authorizes blind partition writes;
manual TWRP recovery if automatic access fails. Preserve first error and missing
attribution, never mark a refused/partial timing run successful. No progress
push is required before immediate rollback. Freeze/commit result afterward.

## Interpretation

Completion means this bounded OFF experiment captured attributed READY/raw-read
brackets and restored the baseline. It does not prove exact chip conversion
instants, coherent channels, physical calibration, current response/cutoff,
active100ms sampling/OCP, PPS refresh, direct ON or long-term reliability.
Software OCP remains unverified, and complete high-power port remains NOTREADY.
Any first failure leads to source/evidence analysis, not another identical boot.

Commands are explicit `host_flow.py preflight`, `run`, or emergency `restore
--from-recovery`; import/packaging/unit tests perform no device IO. The runner
uses accepted helpers for baseline/recovery/hashes; its timing parser has separate
semantics and never inherits the old diagnostic getty/watchdog arming gate.

Entry filter update: a bounded8s ADB boot/real-pack packet precedes all expensive
partition/module/Windows probes. Actual initial refusal at SOC4% took0.092s,
retained under reserve-checks; no full preflight or device mutation ran. This is
a maintenance-entry refusal, not an executed candidate round or successful ADC
result. Entry safety/identity gates remain unchanged; full preflight follows only
once the reserve filter passes. Final16 parser/lifecycle tests PASS0.033s; prior
15-test registration evidence remains retained, no kernel rebuild needed.
