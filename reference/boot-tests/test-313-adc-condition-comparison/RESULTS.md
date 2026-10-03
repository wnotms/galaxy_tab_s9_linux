# Test313 — first device fault stopped / accepted311 restored

Verdict: **STOP_LIVE_REVBLK_AND_NONZERO_OFF_IBUS_ACCEPTED311_RESTORED**.
One registered candidate boot41c7fe02731a4be2912d6e81e98e8c0a; no15s endpoint or device acceptance.
Original error `pump current/new fault` preserved; it covers nonzero observed
IBUS/new fault and is NOT proof that CHG_ON was enabled. Driver reports no pump
activation support and captured mode01/01(OFF).

Baseline45f6c912 at38%,3.801V,31.9C passed exact notes/config/allfive/181/controls,
thermal and rescue. Candidate boot/181 installed/read back, BCB cleared.
Candidate current-state saved before refusal; full first-failure kernel JSON
1060 rows with source timestamps preserved. Offline unique attribution
proved from saved preflight and rollback target history after refusal. This
completes evidence, not a clean reclassification. Matched CPU/panic/stall counts
empty; original SM5440 fault remains first failure.

Measured single conversion ADC-start152ms/read286ms; gauge-start/end286ms.
VBAT ADC3.7995V versus gauge3.802V:2.5mV difference. VBUS5.010V,IBUS30.625mA,
die28C. Original INT=00 00 62 00, live STATUS=00 00 22 00 andfault0x80:
REVBLK is LIVE, unlike the earlier inactive0x20 startup latch. Never whitelist
this as an old startup event. Condition valid0/fault1, no sampling/freshness grant.
CNTL6 before89/during09/restored89 all read-valid; ADC-off/ENHIZ cleanup completed,
condition/restore error0,restore_pending0. A close single VBAT pair is not
independent calibration, a validated passive recipe or proof of fault cause.
No pre-clear STATUS3 sample exists; cannot claim the bit change caused REVBLK.

Automatic exact accepted311(Test308) boot+181 restoration completed once;
allfive readback,BCBclear,normal final1f1e01bfde9643b08e363237a92dcd80 at39%,3.796V,30.2C,
config/notes/ordinaryQ4/input500/fast500/float4440/real thermal/deviceADB/NCM and
attribution verified. Host NCM TCP255 separately recorded. Restored passive
startup refusal remains known diagnostic evidence, not full ADC acceptance.
rollback_required=false;313terminal/no replay. No PPS,pumpON,current raise,
SM5714/DTS/USB/adbd/rootfs change. Full Stage3 remains NOT READY.

51affected host tests PASS0.324407s reused; no build/full/Actions for results-only
work (`executed:false`). Original156 source inputs unchanged. Preserve complete
raw evidence and failure-analysis.json. Do not erase actual flags/current or
relax a gate to turn this failure into PASS.

Next compare original operating context: stock sets ENHIZ for attached+OFF and
avoids normal ADC below CHECK_VBAT; Fedora active init clears ENHIZ as part of
reset/protection/ADC initialization after switching handoff at fixed9V. Our
bit7-only PC5V experiment is neither production recipe. Before another trial,
require a source-backed design with pre-change live status/fresh actual VBUS,
matched fixed-contract and pack state; keep protections and OFF verification,
original errors and exact restoration. Do not copy resets/protection-disable
magic or guess that9V alone cures the issue.
