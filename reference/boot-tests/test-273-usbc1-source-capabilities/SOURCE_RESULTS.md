# Test273 source identification completed; PC endpoint pending

One owner-confirmed C1 attach/C2empty on unchanged installed263/same846248af.
Fresh attached SOP header0x61a1 NDO6, complete TCPM decoded frame and current
partner source sysfs agree, no later detach/reset/overflow/source change:

| Source object | Advertised range | Maximum advertised current |
| --- | --- | --- |
| 1 fixed | 5V | 3A |
| 2 fixed | 9V | 3A |
| 3 fixed | 12V | 3A |
| 4 fixed | 15V | 3A |
| 5 fixed | 20V | 3.25A |
| 6 PPS APDO | 5–11V | 3A |

PPS_ADVERTISED is actual advertised capability, not independently metered output
or a PPS/current/pump grant. Fixed12/15/20V were offered, never selected.
Actual TCPM RequestingPDO1 (zero-based) was fixed9V/1500mA, ONLINE1. Initial5V3A
Rp budget is not physical input draw. Selected9V/1500mA and programmedSM5714
input1500mA throughout30.883s/7samples; no APDO Request or pumpON.

Battery SOC77, gauge4.227–4.233V, charging+1.298..1.952A, pack29.0°C. Net battery
power estimate from gauge V*I is about5.49–8.26W, not USB input power. Negotiated
9V*1.5A gives13.5W contract ceiling, not measured instantaneous USB draw.
Cached uncalibrated passiveADC VBUS9.136–9.148V, VBAT4.1375–4.1385V, IBUS0,
die34.5–35.0°C, cache76–1012ms/advancing; Good/fault0/OFF/protectionunchanged.
Not independent calibration or the Test272 fresh100ms consumer qualification.

Exact config/notes/cmdline/sameboot, Sink/Device, services normal, DCCabsent,
Wi-Fi authenticated; full journals saved at boundaries. No new CPU/kernel/
passive fault. Original20 startupSMMU variants still unresolved/unchanged.
Original source STOP/zero-window from capability-vs-protocol host check retained;
source-completion supplements that missingwindow on sameattach, no physical retry.
See SOURCE_OBSERVER_CORRECTION; original result is not rewritten CLEAN.

No flash/reboot/kernel/config/DTS/modules/rootfs/USB/charging-policy/current-limit
change, PPS request or pump enable. Parser31/collector18 tests passed earlier;
results-only executed:false/no build/full/CI rerun, reuse unchanged272 qualification.
Still pending one owner-confirmed charger-to-PC endpoint (no discharge window).
ActiveStage3 NOT READY: liveadapter/freshADC timing/nonzero calibration/OCP/PM
qualification remains; supplyAPDO discovery removes only the source-capability gap.
