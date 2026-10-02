# Test282 results — stopped before acquisition, rollback completed

**STOP_UNCLASSIFIED_PASSIVE_STARTUP_EVENT_EXACT263_ROLLBACK_COMPLETED.**
One sealed272 candidate boot was deployed; zero observer loads, fresh requests,
tracefs writes or portable-device tool transfers. No trace/request timing result.
The rejected attempt is retained and has not been rewritten as clean.

## First stop

Candidate `dd9a0205-53c4-42df-ae29-e90392ac86cb` had exact272 notes, unchanged
configf2891de2, accepted normalcmdline, unique boot attribution, healthy battery,
PCSDP500/Sink+Device, ADB/authenticatedWi-Fi/deviceNCM/noCode43. Full journal was
preserved. Frozen275 retained-startup classifier rejected one early passive
fault line because INT=`00 00 62 01`, versus accepted `00 00 62 00`.

At0.269739s the line retained REVBLK bitmap0x80, pumpOFF01/01, IBUS0,
VBUS4.789V/VBAT3.9645V/die26.5C and unchanged protection registers. The driver
logged two-fresh-confirmation completion at2.569853s (2.300114s later). Current
cached snapshot was healthy/fault0/OFF/IBUS0. Full raw kernel source timestamps
and original scan suspects are retained under `candidate-admission/`.
These endpoint facts do not waive the registered startup admission failure.
No additional candidate boot, observer retry, timeout/ADC change or exemption.

## Offline interpretation, not a new acceptance

Samsung `SM5440_INT4_ADCUPDATED = 1 << 0`, current `SM5440_ADC_READY = BIT(0)`.
Current fault decoder treats INT4 bits2/1 as watchdog/timer; bit0 itself does not
set those faults. Sampling ORs read-to-clear events into the logged INT bytes.
Thus the differing bit is consistent with a retained ADC-completion event,
not independently proof of new pump activity, CPU failure or ADC hardware fault.
REVBLK remains a retained event; its precise latch cause/timing is unresolved.
See hashed inputs/facts in `startup-source-analysis.json`. No gate was modified.

A future offline classifier review should classify bitfields with explicit
bounds, preserve startup REVBLK evidence, require the original safe raw/OFF/
protection/chronology/current-health conditions, and reject watchdog/timer/
unknown bits. It needs separate tests and any future physical registration.
This run grants no fresh-API/ADC timing/charging acceptance.

## Exact baseline restoration

Unconditional TWRP rollback restored Test263 bootcc31efa0 and original181modules.
All five partitions and all181module hashes match accepted263. Tested272modules
remain under `.gts9-test282-tested`; older backups retained. Root unmounted,
BCB cleared. Readback and raw command evidence are under `rollback-install/`.

Final263 boot `60b572d1-27b1-4921-b4f5-f7332f04d923`, Wi-Fi `10.125.29.204`, has
exact263 notesfea0613f/configf2891de2/normalcmdline and unique Debian history.
ADB/authenticatedWi-Fi/deviceNCM/sshd normal, noCode43, healthy battery/cache,
pumpOFF/IBUS0/fault0, observer/debugfs/freshAPI absent, DCC absent. Full final
journal passes frozen diagnostic gate with no new CPU fault signature; known
startup SMMU findings remain unresolved. Host NCM TCP was not rerun.
This is a bounded endpoint, not reliability, ADC or high-power qualification.

## Host issues retained

Initial BCB helper check inherited ADB `/data/local/tmp` which does not exist;
no BCB write occurred. Command-local TMPDIR=/tmp follows prior277 usage. Host
entry polling mistakenly expected TWRP `device`, while saved native ADB state
reported `recovery`; recovery kernel/root/partition checks proved entry, no
second reboot. Neither error was hidden or used to waive a device gate.

## Qualification and immutable behavior

Test282 portable18mocktests+syntax/package checks passed before registration.
Results-only checks: executed:false; reuse272provider/27626affected+full1481/
W=1/sparse,27950 and28024. All198 protected inputs and historical275/277/278/
279/280 seals unchanged. Portable/staged identities checked. No kernel build,
full regression or GitHub Actions repeated for evidence-only work.

No kernel/config/DTS/ADC/deadline/USB/adbd/rootfs/charging-policy changes.
Fixed5V<=1.8A/9V<=1.5A,4440mV/failclosed thermal/suspend/DCC=n/container config
retained. No PPS, pumpON or current increase. Active Stage3 **NOT READY**.
