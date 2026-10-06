# Test330 — first PPS attempt STOP, Test323 restored

The host-only opt-in separator fix passed15 new tests plus23 unchanged guardian
tests. Registered31376fb9, installed same c064e61a boot-only opt-in and181
unchanged Fedora modules, allfive partitions readback/BCBclear/rootunmount.
PC candidate32a075d2 uniquely attributed from222efdcc,54%/3.960V/30.5°C;
exact kernel/config/notes/orderedcmdline, pumpOFF, nativeADB/Code0/WiFi/deviceNCM.
Armed autonomous guard before owner C1attach; no driver/config/DTS/rootfs changes.

Source negotiated fixed9V then TCPM PPS8.72V/1.8A. Two source samples show
ONLINE2, CURRENT_NOW1.8A, CURRENT_MAX3A. This validates a short protocol state,
not delivered charging power. Start failed-11, kernel physical fixed-return
confirmation failed-110 and kept switching inhibited. Guardian preserved first
fault and unbound the worker; its cleanup reported `fixed9 not restored`.
169 raw samples show zero modeON samples and no start-success log. Registered
30s pump window NOT COMPLETED, no repeat/5min/20min/current escalation.
Pack27.9–31.7°C and3.903–3.971V in raw samples; no observed CPU/panic signature.
Continuous ADC is uncalibrated; cannot turn this into a high-power or independently
measured voltage/power acceptance. See ANALYSIS.md for separate source findings
and the observer USB_TYPE capability versus active ONLINE classification bug.

Owner unplugged C1 immediately on request and returned PC. Emergency rollback
restored exact Test323 bootf8f7d0d and saved `.gts9-test327-original`181 modules,
five partition readbacks verified, BCBclear/rootunmount, one normal67673895 boot
uniquely attributed from failed32a075d2 using existing journal histories. The
original admission's history-unavailable label is retained; summary records the
later pure attribution of already captured evidence, no physical replay.
Current provider sm5440-passive/pumpOFF,54%/3.954V/30.6°C/ordinaryPC charging,
ADB/no43/deviceNCM/authenticatedWiFi10.139.153.109/no new kernel fault.
Rollback_required=false. Original327 backup slot has been consumed by restoration;
failed Fedora modules are in `.gts9-test327-tested`, formal artifacts retained.
Do not reuse the old module-swap installation as though its original slot exists.

Driver issue identified offline: final coherence read in `sm5440_read_pack()`
uses the public fixed-only snapshot API even during owned PPS. Also physical
fixed-return proof fails its unchanged100mV ADC criterion; do not loosen it or
resume custom ADC work. No fixes or new hardware test in this stopped series.
Next candidate needs phase-correct source snapshots and correct observer mode
classification, with fault tests; source/sensor/contract return still requires
review before another run. Same Fedora ADC, fixed ceilings and safety retained.

No kernel rebuild/full suite/Actions: exact kernel qualification reused;38
host tests executed for the host-only adapter. Final report: PPS protocol partly
observed, direct charging NOT ACCEPTED. Stage3/higher-power candidate NOT_READY.
