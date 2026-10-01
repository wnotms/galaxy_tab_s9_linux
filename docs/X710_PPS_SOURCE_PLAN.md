# PPS supply identification after Test272

## Completed identification — Test273 (2026-10-01)

[CAPTURED] One C1/C2empty attach: complete counted TCPM Source_Capabilities and
currentpartner sysfs agree, fixed5/9/12/15V3A,20V3.25A, position6PPS5–11V3A.
Actual selected fixed9V1500mA/ONLINE1,30.883s/7samples healthy ordinary charging;
PCADB/deviceNCM/Wi-Fi endpoint sameboot/noCode43. See Test273 RESULTS/summary/
raw evidence. Original hostobserver STOPs preserved, separately completed;
original20 startupSMMU messages still unresolved. No PPS request/pumpON/flash/
reboot/current/software change.13.5W contract ceiling is not measured USB draw.

TCPM USB_TYPE[PD_PPS] reflects source capability even in fixedPD. Pinned
ONLINE1=fixed,2=activePPS,3=activeAVS; don't confuse capability with activation.
An initial5V3A Rp budget is not SM5714 programmed draw. A pending HARD_RESET
transition is a scheduled timeout, not an actual reset. Archive the consuming
ring's first read; standard source-capabilities/power/ is not a PDO directory.

The sourceAPDO gap for this attach is resolved; independent calibration/nonzero
current/OCP/fresh100ms on-device consumer/liveadapter/PM safety remain unqualified.
No active charging admission or45W proof follows. ActiveStage3 NOT READY.
The owner-report and original future procedure below are historical planning.


## Owner-provided source (2026-10-01)

[OWNER_REPORTED] Lenovo YG65G USB-C1 is rated up to65W and has supplied roughly
45W under stock Android. The measurement method is unspecified; this is not
independently measured mainline power or a captured APDO list. Earlier label
photo lists C1 fixed5/9/12/15/20V, up to20V3.25A single-port; C2 up to18W.
An omitted PPS line on the label cannot determine live Source_Capabilities.

Use C1 as the next source-capability identification candidate with C2 empty.
Current installed Test263 remains the frozen fixed Sink/Device software, with
fixed5V<=1.8A /9V<=1.5A ordinary SM5714 input limits. Mainline does not inherit
stock Android's45W setting, enable SM5440 or authorize a PPS Request merely from
this owner report. No cable action is requested or performed by this document.

## Minimal future identification procedure

Register one ordinary fixed-PD source attach on unchanged baseline, after a
current boot/health/rescue snapshot. Preserve raw TCPM Source_Capabilities and
selected fixed contract, passive reported VBUS/VBAT/temperature and full journal
at the boundary. Do not rehash unchanged partitions/modules or sample full
journals repeatedly. Discover the actual TCPM debugfs log node rather than
assuming its name; pinned tcpm_debug_show() consumes log entries, so archive the
first raw read and avoid exploratory reads that lose the source list.

`tcpm_log_source_caps()` in pinned7.2-rc3 distinguishes fixed PDO and type3 PPS
APDO voltage/current ranges. Require unique same-boot/attach attribution. If a
complete current source list includes PPS, retain exact position/min/max/current
and validate against future board/source ceilings. If no APDO appears in a
complete list, record NO_PPS_ADVERTISED and preserve object kinds; do not call
variable/battery source lists fixed-only. Missing/truncated/stale log means UNKNOWN,
not proof of no PPS and not admission. No PPS power_supply write or pumpON.

This only identifies source capability; it does not prove a negotiated PPS
contract, independent VBUS accuracy, nonzero IBUS accuracy, OCP/cutoff response,
active ADC timing or live PM/lifetime safety. A subsequent separately qualified
consumer/adapter and conservative entry gates are still required. Initial current
cap stays<=1.8A; higher2.0/2.25/2.5/3.0A stages remain independent later work.
Known-good fixed9V input stays<=1.5A; never select>9V during this source-only check.

Test272 fresh-request candidate is offline-qualified and not installed. Its
actual OFF-mode request timing will require a bounded read-only kernel consumer;
source identification can occur independently without flashing that candidate.

## This documentation change

No device commands, source/config/DT/build-input changes. Kernel build/full/host
tests executed:false; reuse final399eb497 Test272 qualification and sealed91dc8c04
results. This is a future plan and owner-report record, not a physical result.
