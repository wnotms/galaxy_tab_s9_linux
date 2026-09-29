# Test255: offline candidate result

**READY for separately authorized bounded physical acceptance. No physical
Test255 has run.** Installed Test254/Stage1/Test253 and its rollback remain
unchanged; this task issued no device command and did not query live state.
Read [BUILD_RESULTS](BUILD_RESULTS.md), [machine summary](validation/summary.json),
[artifact identities](ARTIFACTS.json), [source audit](SOURCE_AUDIT.md) and
[future physical registration](README.md).

Stage1 remains ordinary SM5714 switching charge with BC1.2 classification,
4.44V float, rated8160mAh/typical8400mAh metadata, pack thermistor, original
NORMAL/REDUCED/STOP thresholds/hysteresis, read/programming fail-safe and
suspend stop-charge. Stage2 adds TCPC hardware transport and stock Linux TCPM
fixed5V/9V Sink negotiation. It does not replace Stage1 or port Samsung policy.

Fedora fetched main still equals ab123e7d1dbc0cbcd35661f9761197e977b15aa9.
Transport register/CC/RX/TX/IRQ/init/resync sequences and same-model board
wiring informed this candidate. Both retained-role TCPM patches address powered
dock warm-reboot roles, not basic Sink: neither was imported. Source/VCONN/boost,
OTG/dock, PR_SWAP/DR_SWAP, DP/PS5169/SBU, SM5440/PPS/direct-charge and fast-charge
paths were excluded. Samsung X710 sm5714_typec.c/header supplied register,
interrupt, role/reset/clear semantics; X710 stock DTS and charger source supplied
wiring/current encoding. Local GPL extraction is hash-pinned, not falsely
identified as a git commit. [Reference SHA record](validation/reference-sources.json)
and [register table](SOURCE_AUDIT.md) document each write sequence.

New TCPC callbacks expose get_vbus/get_current_limit/get_cc/set_cc/polarity,
PD RX/TX and stock-required set_roles/set_vbus/set_vconn. Only Rd/open,
Sink/Device and VCONN-off are supported; Source/Host/boost are rejected. TCPM
chooses PDOs/state transitions/resets/roles. A transport guard checks the actual
source PDO/RDO and prevents non-fixed/>9V/out-of-budget requests; stock
CAP_MISMATCH semantics do not permit excess operating current.

PDOs are5V/1.8A and9V/1.5A. Actual9V input never programs above1500mA(13.5W),
5V above1800mA, or a positive grant>=100mA. Pack current cap stays2100mA;
thermal-reduced input/pack remain500mA. Zero/sub100mA grant, pending TCPC probe,
fault or suspend opens Q4 and applies100mA hardware input minimum. **Q4 is not
complete VSYS isolation; zero total VBUS draw is not claimed.** First TCPC
transport or charger safety/programming fault latches charge inhibition until
fresh charger probe. No automatic recovery or reset loop was added, and no
protection-limit experiment was performed.

Final kernel/modules and boot package validators passed. Full config delta is
only CONFIG_TYPEC_SM5714 absent->y; all Test254 prerequisites/HVC_DCC=n retained.
Compiled DTB has23 approved semantic changes, zero unexpected changes. DWC3
peripheral/USB2 graph remains; delete inherited stale role-switch flag to avoid
probe deferral. Existing SM5440 DT child is disabled/unlinked only; its controller
setup and all registers/drivers remain untouched. No TCPM/DWC3/gadget/adbd/
rootfs/OPP/GPU/display/Wi-Fi/Bluetooth code or policy change.

Changed/wrapper/full each execute1183 tests with zero failures/errors/skips.
The old1148 remain;35 new checks cover actual C failure paths, grants, thermal/
suspend gates, first-fault/rebind, init failures, fixed request validation,
CC/roles, RX partial/cable frames, hard-reset completion and IRQ-storm inhibit.
No GitHub Actions ran. Separate logical plan, host-fixture repair, candidate
implementation and result commits are pushed only to origin/test.

## Physical limits and unresolved work

Offline checks cannot certify electrical safety or prove a9V contract. TCPC
initialization/timing/IRQ and PC enumeration still need Test255. Default-Rp
BC1.2 classification can conservatively stay500mA until a new detection event.
Water detection, USB3 orientation, dock/OTG/DP and suspend/resume PD continuity
are not accepted. TCPM voltage_now is negotiated state, not an independent
VBUS ADC; actual9.5V stop gate needs a suitable inline PD meter.

Test254 Docker I/O CLI issue, GUdev assertions, direct registry access and
unexecuted network/rootless/cable gates remain independent unresolved history.
No current stability finding overwrites Test249/247's bounded DCC conclusion.

Future Test255 must recheck rescue/identities and retain Test254 boot+vendor_boot
and181 files without overwriting Test252/Test249 pairs. Then battery-only150s,
PC Sink/UFP ADB/NCM/Code43 check,5V source, proven fixed9V Request/Accept/PS_RDY,
5min then20min bounded charge, unplug150s and same-boot charger->PC reconnect
<=60s plus150s responsive observation. Stop first anomaly, including actual
VBUS>9.5V, VBAT>4.44V, first-run pack>=45°C/rapid rise, resets/I2C failures,
CPU/kernel fault, unexplained reboot, lost rescue channels, Code43, abnormal
current, requested PPS/APDO or SM5440 probe. Never heat/overvolt/raise current
for protection testing. Restore original Test254 boot+vendor_boot+matched modules
through label/card-verified TWRP if a later authorized attempt fails; preserve
init_boot/dtbo/vbmeta/rootfs and older rollback pairs. No deployment/rollback,
Stage3 or physical protection-limit test was performed here.

Stage2 fixed-PD candidate: READY
