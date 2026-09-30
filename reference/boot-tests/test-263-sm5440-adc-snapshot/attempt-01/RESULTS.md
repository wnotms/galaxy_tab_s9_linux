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
