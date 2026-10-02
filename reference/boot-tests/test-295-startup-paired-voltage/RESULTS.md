# Test295 — short startup paired-voltage diagnostic

**PAIRED_STARTUP_EVIDENCE_CAPTURED_STOP_NCM_TRANSPORT_EXACT263_RESTORED.**
Registration bb449a37 pushed before mutation; source1028ae06. Exactly one
candidate boot, three startup voltage pairs, no observer/trace/module load,
PPS/pump ON/current increase/converter/threshold/deadline/fault-reset change.
Inherited290/294 APIs remain inactive without consumers.

| Sequence | ADC oldest→reads completed (ms) | SM5440 VBAT | Gauge start→end (ms) | SM5714 VBAT | Difference |
|---|---|---|---|---|---|
| 1 |150→281|3.5985V|281→282|3.891V|292.5mV|
| 2 |1309→1437|3.6000V|1437→1437|3.844V|244mV|
| 3 |2461→2589|3.4990V|2589→2590|3.854V|355mV|

The comparison now uses nearby startup windows, rather than Test293's281-second
separation. Gauge SRAM reads succeeded. This establishes a repeatable discrepancy
in adjacent windows; it does not prove a constant calibration offset, true pack
voltage, physical cause, or exclude short startup voltage transients. ADC timestamps
bound software acquisition/read completion, not simultaneous hardware conversions.
The added gauge read took0–1ms at millisecond resolution; no timing grant inferred.

First REVBLK is retained. Third sample remains below the3.5V startup predicate;
confirmation fails at2.594914s. Existing refusal is neither cleared nor treated as
healthy. Mode01/01 is OFF in[3:2], IBUS0, protection f2/e7/37/fe retained. Full raw
kernel JSON and cached sample/initial sample are preserved; no charging grant.

## Device and transport

ADB/service/deviceNCM/roles/config/notes were present. Candidate NCM SSH timed
out on its first bounded check despite device ssh active and usb0 configured;
Windows composite/ADB/NCM Code0. Collection stopped there, before the15-second
endpoint, with no candidate retry or new boot. WiFi host was already unreachable
in preflight; authenticated NCM had worked before deployment. These transport
failures do not prove a CPU wedge or identify a kernel cause.

Allfive partitions and181 original modules were restored to exact263; old backups
kept in unique295 slots, BCB cleared and root unmounted. Final attributed263 boot,
exact config/notes/cmdline, ADB active, Sink/Device, battery Good45%3.831V29.9C,
no failed units, no detected CPU/panic signature. NCM host timeout persisted after
rollback, so overall transport acceptance is **not clean**. Passive startup health
also remains REFUSED. This result does not claim charging/stability acceptance.

## Scoped offline validation

208 affected SM5440 tests pass (10new diagnostic cases),8.218s;11initial runner
cases pass,0.081s. Recovery-safe handling of admission without a summary and the
actual sm5440-passive log prefix were corrected after the transport stop;
12runner cases pass,0.114s. Original failures/commands are retained. No physical
rerun, assertion weakening, runtime workaround, or rewritten suspect result.

ARM64 standard ccache build, W=1/sparse changed driver, artifact audit pass:
exact294 config/DTB, protected inputs unchanged,181paired module archive. Initial
relative build paths produced a config gate refusal; canonical absolute paths
passed without changing any config symbol. Full regression executed:false; reuse
unchanged294 qualification. No Actions/CI. Exact artifacts and empty config/DTB
diffs are recorded separately.

Next use the new paired evidence with Samsung/Fedora ADC operation conditions
before changing anything. No automatic threshold relaxation, guessed calibration,
PPS/pump enable or repeat of this failed transport profile. Active Stage3 NOT READY.
