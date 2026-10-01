# Test273 — USB-C1 source capability identification

One owner-confirmed Lenovo YG65G USB-C1 attach (C2 empty) on unchanged installed
Test263, fixed5/9V Sink/Device policy;30s/5s observation after one5s settle and
fresh source capability attribution. No flash/reboot/PD write/pumpON/software
change. C1 rating<=65W and owner-reported Android~45W are source hints only.

Current preflight: same846248af boot, exact263config/notes, battery77%/4.133V/
32.7°C Good, passiveGood/fault0/fresh/OFF/IBUS0, ADB/Wi-Fi10.125.29.77 normal,
noCode43/failedunit/DCC. Full raw journal saved; original20 startupSMMU variants
exactly unchanged, remain unresolved, no global parser/allowlist expansion.
Discovery found `/sys/kernel/debug/usb/tcpm-3-0033/log` without consuming it.

Push registration/runner/parser and passing affected tests before cable action.
`capture.py prepare` archives the first existing PC TCPM ring read and cursor.
Then ask owner to remove PC USB and attach onlyC1; no test timer before confirmation.
`capture.py source --owner-confirmed` archives new TCPM log, counted attached SOP
Source_Capabilities and current Type-C partner's standard sysfs source objects.
Require sameboot and exact agreement; raw logs/sysfs retained. Complete list
with PPS -> PPS_ADVERTISED; complete list without PPS -> NO_PPS_ADVERTISED.
Absent/truncated/overflow/reset/stale/malformed/mismatch -> UNKNOWN/STOP, never
false PPS absence or charging grant. Source offered20V is different from selected
voltage; only fixed5/9V remains permitted. No source Request is forced.

TCPM's initial5V/3A Rp budget is not measured draw: pinned SNK_DISCOVERY reports
available Rp current, and SM5714 stores the grant then separately clamps input.
This sequence already exists in accepted Test263. Archive that budget distinctly;
actual charger input remains5V<=1800mA/9V<=1500mA, and the final fixed contract
must satisfy those bounds. Never treat advertised or logged budget as power drawn.

Collect one30s ordinary fixed-PD window with coherent state/boot/config/notes,
ADC/thermal/protection/service gates and incremental kernel evidence; full journal
at boundaries/first anomaly. PC return is one owner-confirmed cable transition,
oneADB/device endpoint and Windows noCode43. No repeated partition/module hashes,
full kernel download per sample, reboots or charging retries.

Stop first new safety/kernel/transport/evidence problem and preserve raw state.
Known unchanged startupSMMU gap is retained, not an original CLEAN claim; device
normal criterion and host-only defect separation remain. No gate relaxation or
fault clear. Caller may collect ordinary rescue PC endpoint after a stopped
source stage, but cannot rerun the source stage. No rollback software needed.

Offline qualification: affected parser/collector tests and syntax only. Test272
kernel/all1424 checks reused while inputs unchanged. No build/full/Actions.
This source identification is neither negotiated PPS nor independent physical
voltage/current calibration, OCP/cutoff or active acquisition qualification.
Test272 fresh-request API is not installed. ActiveStage3 remains NOT READY.
