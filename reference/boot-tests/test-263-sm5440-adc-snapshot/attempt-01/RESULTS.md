# Test263 attempt01 — device acceptance completed

Owner updated acceptance on2026-09-30: device-side normal operation completes
the test; a host collection defect alone does not mandate rollback/retrial.
No rollback/reboot/reflash occurred after the original host STOP. Candidate
Test263 remains installed, with exact Test260 rollback retained.

PC cached snapshot30.220s/7samples, fixed9V30.420s/7samples, and unplug
15.370s/4samples passed on33435db741e94574aeb2c209730acf67. Final separate
read-only device-completion capture confirmed ADB shell/config/notes, healthy
battery/passiveOFF, Sink/Device, DCC absence and active SSH/adbd. Windows NCM
and authenticated SSH matched the same boot, with one readiness sample/no
authentication retry/delayed readiness; no Code43/new kernel/CPU/systemd fault.
Wi-Fi was responsive for the preceding PC endpoint/full failure journal.
Readiness capture13.434s is not a measured physical reconnect latency.

Reported fixed9V VBUS9.076..9.109V, pack29.0..29.1C, telemetry-derived netbattery
power mean7.813216W (not measured USB inputpower). Pump remainedOFF/IBUS0;
no PPS, current/protection/thermal/USB change. Independent ADC calibration,
active OCP/PM/live handoff are unqualified; ActiveStage3 remains NOT READY.

The original pc-endpoint STOP/raw files below are retained without alteration.
The later device-completion namespace supplies the missing final acceptance,
not a second charging trial or rewriting the failed host orchestration as clean.
summary.json distinguishes device completion from original strict runner clean.
No build/full rerun (executed:false); reuse ea938b24 qualification. The host
filename collision remains a known tooling issue for future offline correction.

## Original first host STOP record (historical; rollback superseded by owner)

# Test263 attempt01 — STOP at PC endpoint evidence collection

The registered series stops at its first non-clean endpoint. PC snapshot30.220s,
fixed9V snapshot30.420s, and owner-confirmed unplug15.370s passed on unique boot
33435db741e94574aeb2c209730acf67. Their raw evidence/verdicts remain unchanged.
See PC_RESULTS, PD_RESULTS and UNPLUG_RESULTS for bounded results and limits.

After owner-confirmed PC attachment, one1.021s sample showed Sink/Device,
reportedVBUS4.915V, SM5440 OFF/IBUS0/Good, valid cached snapshot age1032ms,
pack29.2C and no new kernel/CPU/systemd fault in full Wi-Fi journal. ADB identity
matched boot/config/notes. Complete NCM/Windows/DCC-service acceptance was not
reached: endpoint.py first records Wi-Fi journal as kernel-json, then admit()
tries to use the same recorder filename for ADB journal. Recorder correctly
refuses overwrite; the original first error and additional failure evidence
are retained. This is a host evidence namespace defect, not an observed device
charging/CPU/USB fault. It does not establish complete PC rescue acceptance.

Do not retry this attempt or relabel it clean. Exact Test260 rollback is required
by registration; recovery is pending at this record. No PPS, pumpON, current,
protection, thermal or USB software change occurred. Future host correction must
use separate evidence namespaces and a functional combined-capture test before
a separately registered physical attempt. ActiveStage3 remains NOT READY.

No rebuild/full regression for these results (executed:false). Reuse unchanged
ea938b24 kernel qualification; previously15 endpoint tests did not cover the
combined Wi-Fi-journal/admit recorder interaction. Independent ADC calibration,
OCP/PM and live handoff remain unresolved. No input-power/recovery-latency claim.
