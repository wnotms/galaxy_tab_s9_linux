# After Test345: bounded duration progression, not registered or enabled

Offline implementation/build now qualified (source5c90a4b5/defaultOFF); see RESULTS.md. The physical300s guardian/registration and authorization remain pending.

Accepted short-test source:01747a5f44dacb7fa6a5d45ea814e8827998c4e1. Test345 native completion and sameboot ordinary fixed9 charging30.845s/discharge15.650s passed; PC rescue and exact331 restoration subsequently passed (finalboot64440dd59caa45c1a4a393510a1119b8). Test345 is closed with bounded acceptance; no next hardware authorization is inferred here.

## Next question

Can the accepted short-cycle PPS/SM5440 path maintain the same conservative current policy for five minutes and perform the same safe fixed9 return? This follows step E of docs/X710_CHARGING_TEST_PLAN.md. Do not raise current or simultaneously change register programming, ADC averaging, TCPM/SM5714, config/DT, USB/adbd or thermal policy. Preserve the immutable Test345 source/artifact/evidence pair.

The accepted Test345 kernel fixes SM5440_ONCE_MS=30000, and Test345 native_proof requires max_ms=30000 and a29..30s start/deadline relation. The current candidate must never be reused as a five-minute test by weakening the observer or rebinding the consumed worker. Implement a separate explicit bounded-duration profile only after Test345 closure; default must remain OFF, and existing <=30s mode remains30000ms. Longer duration needs its own opt-in identity and sole-activation proof, no writable runtime extension, no deadline restart, no automatic retry/reattach/resume. All admitted refreshes keep the same deadline; final<=2000ms reserve still defers a new transaction while maintaining fault/measurement/watchdog checks.

The independent future runner must bind its expected duration to the new candidate/kernel witness and reject30s/300s mismatch, duplicate start/completion, changed deadline, refresh after deadline/deferral, unexplained boot and incomplete journal. Preserve fixed-return/lease0 proof, parkedzero>=3/span>=100ms, admitted refresh<=2s, response-gap and primary/cleanup separation. Never edit historical Test345 scripts or results to fit the new duration.

## Current and safety scope

Retain hardware input programming1700mA, PPS request<=1800mA and rawIBUS stop1800000uA. Current is not raised to2A/2.25A/2.5A/3A. Existing APDO/source/board voltage validation remains unchanged (PPS is distinct from Stage2 fixed5V/9V). The fixed-return switching ceilings remain5V<=1.8A and9V<=1.5A, float4440mV. EntrySOC20..75, VBAT3500..<4300mV, pack20..<38C; all current runtime thermal/VBAT/die/physical-voltage/fault/suspend/detach gates retained. Stop at first non-clean; never provoke protective limits.

Start the device-local guardian before asking for charger connection. Owner handoff has its own bounded waiting window and does not consume the pump duration. Pump duration begins at hardware start, not host setup. The kernel owns OFF/PPS/settle/ON, the guardian owns emergency stop/evidence. The guardian must remain active through the full new window and terminal cleanup; update outer observation limits explicitly, not transport/fault timeouts. Capture full journal only at boundaries/failure and raw per-sample telemetry throughout. Evaluate SOC rise before choosing a five-minute entry SOC ceiling; do not run into the existing80% stop merely to finish the timer.

## Reuse Fedora without removing local safety

Same-model reference ab123e7d1dbc0cbcd35661f9761197e977b15aa9, kernel/files/sm5440_direct.c: sm5440_work performs PPS refresh periodically and sm5440_renegotiate_pps uses the parked negotiation path. That existing hardware sequence is already the basis of this port. Duration progression does not require a new register recipe or replacing TCPM policy. Retain local switching leases, stale-source rejection, pumpOFF witnesses, bounded parkedzero handling and fail-closed cleanup. Fedora's unbounded retry worker is not the acceptance runner.

## Minimum offline qualification

Affected actual-C tests for30s unchanged,300s deadline/start/terminal/last-refresh reserve, I2C/ADC/source/fault/PM/detach during long run, no rearm after fault/completion and fixed restoration failure. Affected guardian tests for duration identity, streamed long history, sample gaps, malformed witness and stop-on-first-non-clean. One reused-cache incremental build plus exact331 config/DT/protected inputs/module pairing; no routine full-suite or Actions. No candidate built or new driver logic changed by this document.

## Future physical sequence

After current345 PCreturn/restoration acceptance: prepare independent candidate/registration and push; obtain explicit authorization for300s (existing<=30s scope does not authorize it). FreshPC rescue/identity/battery checks, one deployment/boot, local guard awaiting ownerC1, one activation, maximum300s, no restart. Then ordinary fixed9 charging30s, unplug/discharge15s, PC ADB/deviceNCM/noCode43 once and exact331 rollback. Any failure stops the series and preserves the first raw evidence. Only a clean five-minute round permits proposing20minutes; power escalation remains a later independent stage.

Independent ADC calibration/current-protection accuracy and hard-realtime cutoff remain unproven. This draft does not claim45W, vendor-equivalent charging, long-term reliability or completion of the full port. SM5440 long-duration and higher-power deployment remain unauthorized.
