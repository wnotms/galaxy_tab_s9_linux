# Test273 — USB-C1 source identification and device endpoint completed

One owner-confirmed LenovoYG65G C1 attach with C2empty, unchanged installed
Test263, same846248af boot throughout. Complete attached TCPM frame/header0x61a1
NDO6 matches currentpartner sysfs; advertised fixed5/9/12/15V3A,20V3.25A,
PPSAPDO at position6:5–11V3A. Actual Request was fixedPDO2 (zero-basedPDO1),
9V1500mA. No APDO Request, pumpON or selected voltage>9V. PPS_ADVERTISED is
capability evidence, not a PPS contract, measured45W or permission to increase power.

Same-attach source-completion observed30.883s/7samples: SOC77, gauge4.227–4.233V,
charging+1.298..1.952A, pack29°C; exact config/notes/cmdline/Sink/Device/services/
DCC absence. SM5714input1500mA, passiveGood/fault0/OFF/IBUS0, cachedVBUS
9.136–9.148V and die34.5–35°C; protection unchanged, cached sample advances.
No new CPU/kernel/passive fault; original20 startupSMMU messages unchanged and
unresolved. Full journals/raw ring/currentpartner attributes/telemetry retained.
See SOURCE_RESULTS and summary.json for ranges and raw evidence.

Nominal9V*1.5A is a13.5W contract ceiling, not actual USB input power. Gauge V*I
estimates net battery power5.493–8.257W, not charger output power. PassiveADC is
uncalibrated cached telemetry (76–1012ms), not the offlineTest272 fresh100ms API.
No independent meter/calibration or active current/OCP/PM qualification claimed.

Owner-confirmed charger→PC reconnect completed once: ADB responsive, sameboot
Wi-Fi authenticated, usb0=169.254.42.1/sshd/adbd/gadget service active, no failed
unit or WindowsCode43. Sink/Device, PCSDP500mA, passiveOFF/fault0/IBUS0 and
batteryGood. PCnetbatterycurrent−248mA is reported as observed under500mA input;
STATUS=Charging does not imply positive netbatterycurrent. HostNCM TCP/banner
was not tested; device endpoint satisfies the owner's device-normal scope.

Original prepare/ STOP (omitted@@dcc) and source/ STOP (USB_TYPE capability
mistaken for activePPS), both zero-window, remain unchanged. Fresh namespaces
supplement missing evidence; no reattach/hardware retry/reboot/flash. PinnedTCPM
USB_TYPE=PD_PPS indicates source support, whileONLINE1=fixed,2=activePPS,
3=activeAVS. All active2/3/voltage/current/thermal/fault gates remain. Pendingreset
timeout log is distinct from actual reset; genericpower directory is not PDO.
Original observer results were not rewritten CLEAN. Device acceptance completed
under owner instruction; startupSMMU uncertainty and host corrections retained.

Changed only host parser/collector/tests and documentation/evidence. No kernel,
config/DTS/modules/TCPM/DWC3/gadget/adbd/rootfs/SM5714policy/protection/current
change. CONFIG_HVC_DCC remainsn;4.44V/frozen5V<=1.8A/9V<=1.5A retained.
Affected31parser+18collector tests and syntax passed at616fd891; results-phase
tests/build/full executed:false, reuse unchangedTest272 kernel399eb497/all1424.
No Actions/CI. Historical seals verified against their recorded revisions;
finalSHA256.json seals this complete record. No software rollback needed.

Next: qualify the live fresh-acquisition consumer, nonzero ADC accuracy and
OCP/cutoff/PM adapter before any PPS/pumpON. SourceAPDO gap is now resolved for
this C1/C2empty attach only. ActiveStage3 remainsNOT READY. This bounded fixed-PD
observation does not validate45W, high-power charging or long-term reliability.
