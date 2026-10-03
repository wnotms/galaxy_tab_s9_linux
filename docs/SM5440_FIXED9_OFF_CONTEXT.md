# Source-bound fixed9V OFF measurement context

Test315 replaces the diagnostic worker's former unconditional PC5V bit-only
experiment. It uses the existing default-off sm5440-adc-condition profile;
accepted ordinary/passive builds remain identical after preprocessing. No new
profile/config symbol, PPS request, CHG_ON, TCPM/DTS/USB/rootfs change.

[VENDOR] attached+OFF sets ENHIZ, while direct initialization clears it after
entering CHECK_VBAT. [FEDORA ab123e7d] first acquires the SM5714 switching path
at existing fixed9V. Test313's live REVBLK lacks pre-change STATUS provenance.
This is the missing operating-context experiment, not a claim9V cures it.

The single drained diagnostic worker waits up to40 read-only100ms readiness
checks for the standard TCPM fixed snapshot. Once observed it must be fixed9V,
1000..1500mA, source-bound instance/source/budget generation, healthy standard
PD supply and charge requested. A valid5V/PPS/unknown contract is refused, not
waited out or promoted. No converter or switching write precedes admission.

Read real standard battery presence/health/SOC/VBAT/pack thermistor within500ms:
SOC5..<80,3500<=VBAT<4300mV,20<=Tpack<38C. Capture one unchanged OFF ADC conversion,
then disable/readback ADC. Require physical8500..9500mV VBUS, zero IBUS, OFF
before/after, die22.5..<42C, ready bit and oldest acquisition age<=500ms.
This500ms window is diagnostic only; the100ms charging/lease-release APIs and
all active validity rules are unchanged. No cache publication becomes a grant.

Preserve an initial exact inactive REVBLK latch if live STATUS is fault-free,
mode OFF and physical context otherwise valid; require two new fault-free,
unchanged-control conversions on the same source before proceeding. Any live,
repeated or different fault stops. Retain the original and confirmations in
read-only debugfs. This follows the existing vendor state/mode distinction and
accepted passive confirmation model, scoped to this OFF-only diagnostic; it
adds no active-mode exemption or ADC calibration claim.

Revalidate source/pack, acquire the real checked SM5714 lease (Q4 OFF +100mA),
then obtain another physical9V sample and revalidate epoch/lease/pack. Prepare
three audited OFF settings via Test314's checked transaction, using the actual
fixed budget (never more than1500mA),4437.5mV regulation and vendor frequency.
Immediately before ENHIZ write capture and validate live STATUS under io_lock.
Run the unchanged converter and adjacent gauge comparison, always restore
ENHIZ/ADC-off with readback, then restore original OFF settings. Keep operation
and cleanup errors separately, and do not retry a failed cleanup in the worker.
PM/remove drain it before their one bounded cleanup attempt. No charger/TCPM/
registry lock across waits or foreign power_supply calls.

The lease remains inhibited and is reported even on failure. Diagnostic500ms
measurements cannot authorize its100ms source-atomic release; do not call a
looser release or restamp evidence. A later separately registered physical test
must unconditionally restore accepted311 kernel/modules after capture. Before
that, no device deployment. This is not full active fallback/PM acceptance.

Host tests must execute the actual coordinator for source5V/PPS rejection,
physical VBUS/fault/IBUS/age refusal, inactive-latch confirmation, pack failure,
lease failure, source change/detach/PM at each stage, control/condition/cleanup
faults and successful OFF comparison with lease retained. Preserve old transaction
fault tests and ordinary preprocessing equality. Standard pinned ARM64 build,
source/config/DT/protected/module audit and W1/sparse precede physical registration.
