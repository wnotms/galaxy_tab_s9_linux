# SM-X710 Stage2: fixed-PD Sink plan

Planning audit, 2026-09-29, before implementation. Starting local and remote
`test` HEAD: `26d62393efbd002f185ba759a7cca8638667dee9`. This task authorizes
offline source/config/DTS/tests/build only. **No device command, flash, module
replacement, rootfs change or reboot is authorized in this phase.**

## Current evidence

Read AGENT.md, HOST_TEST_WORKFLOW, Test252 RESULTS/SAFETY_REVIEW, Test253
CURRENT_STATUS/RESULTS/attempt04 RESULTS, and Test254 CURRENT_STATUS/RESULTS/
PHYSICAL_SUMMARY. Their older prepared-only statements do not replace their
final installed-state records. Installed Test254 incorporates Stage1 and the
Test253 userspace fix, with exact Test252/Test249 rollback retained. Test252's
original USB stop and Test254's Docker I/O stop remain historical stops.

Stage1 implements charger0x49/gauge0x71/MUIC0x25 on hub8, BC1.2 classification,
SDP500/500, CDP1500/1500 and DCP1800/2100mA input/battery limits. Pack IIO
ADC5 Gen3 channel0x144 is mandatory. Float4440mV, NORMAL/REDUCED/STOP, cold/hot
hysteresis, missing-temperature inhibit, OVP/WDT/programming fail-safe and
suspend/shutdown stop-charge remain. Typical8400mAh versus rated8160mAh is
already documented; do not change the rated design metadata.

Test254 config SHA256:
`c80d3c661cca3588fc85c93ba3402356bd99b7e4fe85674773230914fb8e6b71`.
It already has TYPEC/TCPM/USB_ROLE_SWITCH=y, HVC_DCC=n and USER_NS/mqueue/
container prerequisites. No TCPC transport binds the existing SM5714 node.
UPower activation is accepted; independent GUdev assertions, Docker client
I/O limits/registry access and complete container/network acceptance remain
outside this task. Preserve all existing config and adbd/rootfs files.

## Reference audit and hardware

Fetched Fedora origin/main: still
`ab123e7d1dbc0cbcd35661f9761197e977b15aa9`; no kernel delta from the supplied
snapshot. [Same-model source](https://github.com/nacht20-de/gts9wifi-fedora-linux/tree/ab123e7d1dbc0cbcd35661f9761197e977b15aa9/kernel)
provides register transport, board wiring and ordinary switching limits.
Audit files: sm5714_usbpd.c, sm5714_battery.c, sm8550-samsung-gts9wifi.dts,
config-gts9wifi.fragment, prepare.sh and both TCPM patches.

Samsung local X710 GPL source is under /home/ms/Samsung/kernel_platform/
msm-kernel: drivers/usb/typec/sm/sm5714/sm5714_typec.c and its include header,
SM5714 charger code and gts9wifi r02/r04 DTS. Record source hashes with the
candidate audit; local files are source evidence, not a newly verified remote
release. The independently extracted official r04 board evidence lives under
.work/reference-samsung/official and reference/stock records preserve live DT.

Hub9 is SM8550 QUP hub SE9, MMIO0x9a4000, PDIC I2C0x33 at400kHz. Hub8 at
0x9a0000 carries Stage1. X710 downstream fragment44 targets qupv3_hub_i2c9,
with usbpd_int TLMM0x85=133; Fedora and current board use level-low GPIO133.
No runtime I2C scan or dynamic Linux adapter-number assumption is needed.

Fedora TCPM patches:

| Patch | Purpose | Stage2 decision |
| --- | --- | --- |
| tcpm-adopt-retained-source-ufp-role.patch | Powered dock retains Source/UFP; adopt local DFP | Exclude; basic charger/PC Sink/UFP has no need |
| tcpm-use-retained-sink-data-role.patch | Restore local Sink/DFP and maintain it across dock reset | Exclude; would introduce Host role outside scope |

Fedora's other DP HPD patch is display lifecycle, not basic PD. Its OTG boost,
CC PR_SWAP holds, retained-dock Rp pulses, source VCONN, PS5169, SBU/altmodes,
SM5440/PPS/direct-charging and fast-charge controls are excluded. No TCPM core
patch is planned. Samsung private policy/notifier framework is not imported.

## Minimum architecture and topology

New built-in sm5714_usbpd transport -> unmodified Linux7.2-rc3 struct tcpc_dev
-> stock TCPM -> fixed Sink PDO selection -> existing switching charger.
Required callbacks: init/get_vbus/get_cc/set_cc/set_polarity/set_pd_rx/
pd_transmit. Current API also mandates set_vconn/set_vbus/set_roles; implement
off-only VCONN, reject VBUS sourcing, require Sink/Device and program only PD
header role bits. get_current_limit uses Stage1 BC1.2 for default Rp;
set_current_limit propagates TCPM voltage/current budget. No autonomous DRP
start_toggling is required for a single-role sink.

The inherited connector currently advertises dual power/data roles, source
PDO and DP/SBU graph connections. Registering it unchanged can both enable
out-of-scope roles and defer probe on missing orientation/mux providers.
Replace only its policy with power-role=sink, data-role=device, two fixed
5V/9V Sink PDOs, no source PDO/dual-role/data-swap/altmode. Keep USB2 port0
connected to DWC3; unlink connector SS/SBU provider graphs and their reciprocal
endpoints. Do not bring up PS5169, SBU mux or DP. Existing inactive hardware
nodes remain undriven; explicitly disable the inherited SM5440 child and remove
its TCPM supply link without changing hub3 controller/GPI setup or accessing it.
Only GPIO133 belongs to the TCPC pinctrl; no OTG/discharge GPIO control.

DWC3 stays peripheral. Its lack of usb-role-switch provider means TCPM's
optional role-switch lookup returns NULL (roles/class.c checks provider
property). TCPM can manage Type-C PD/header roles without controlling DWC3.
Keep CONFIG_USB_ROLE_SWITCH=y because TCPM selects it; do not add the DTS
provider property or modify DWC3/gadget/FunctionFS/adbd. USB2 cable orientation
is covered by CC status; USB3/DP orientation bring-up is outside acceptance.
Any actual enumeration regression stops Test255.

## Current budget, charge gating and lifecycle

Sink capability and charger draw are separate. Advertise fixed5V and9V;
cap actual5V draw at existing1800mA and9V at1500mA (13.5W), also bounded by
TCPM's granted current. Battery current stays at most2100mA in NORMAL;
existing REDUCED500mA/STOP behavior stays. Never map a3A source offer to3A
charger draw. A zero or below-hardware-minimum budget disables Q4, so TCPM
standby/reset does not round a tiny current upward.

Extend Stage1 incrementally with a lifetime-serialized companion interface:
TCPM ownership, contract budget and charge-enable are distinct. The thermal
poller must never bypass TCPM's disabled/standby budget using stale BC1.2 DCP.
Gate registration on the ready charger, propagate failures, keep Q4 open on
error. PD failures latch charge-off until driver removal/rebind, not a silent
high-current retry. Clearing a contract/detach and driver shutdown clear budget.
Suspend must block both polling and asynchronous callbacks from enabling charge;
resume can restore only the current bounded budget through thermal validation.
Do not alter gauge conversion or infer current direction from charge status:
raw pack CURRENT_NOW may be negative even with Charging if system load exceeds
input. Record raw values, status, SOC trend and source/budget separately.

All register writes need source comments and a source/register audit before
build: interrupt read-to-clear, masks/status, CC Rd/open, role bits, RX ack/
flush, protocol reset, SOP TX and hard-reset completion. Error handling and IRQ
removal must not leave an unbounded interrupt storm or use an unregistered port.

Kbuild hook TYPEC_SM5714 depends I2C, TYPEC_TCPM and BATTERY_SM5714, selects
REGMAP_I2C, and is built-in. Stage1 and Test254 build gates stay intact; add
Stage2 resolved-config and voltage/topology guards rather than editing .config.

## Offline validation and candidate

Create independent .work/build/linux-src-sm5714-stage2 and linux-out-sm5714-stage2,
out/kernel-sm5714-stage2, leaving Test254/Test252/Test249 artifacts untouched.
Same Linux pin a13c140cc289c0b7b3770bce5b3ad42ab35074aa, LLVM/ccache/JOBS8 and
paired module build. Save Image.gz, DTB, resolved/embedded config, notes, module
archive/hash set. Compare all config symbols exactly to Test254; only new
TCPC/dependency symbols are expected. Produce semantic DTB diff to distinguish
real property changes from phandle renumbering. Verify protected sources and
all Test254 container prerequisites, HVC_DCC off and unchanged thermal helpers.

Host tests execute real C policy/transport functions with mocked register I/O,
cover fixed budgets, low current/zero/error/thermal gates and sink-only rejection;
also check DTB/fragment/source guards. Retain every old assertion. Run required
changed wrapper, changed report and final all --fail-on-skip. Host-only real
syncfs qualification from Test254 is permitted for WSL tests; no device helper
change. No GitHub Actions. Commit/push logical plan, implementation and evidence
on test only. READY means ready for separately authorized bounded acceptance,
not physically verified or proof of universal hardware safety.

## Test255 future physical acceptance and rollback

Register a new Test255; do not overwrite Test252/253/254. No physical action
until explicit authorization plus fresh pushed registration/rescue identity.
Use ADB at /mnt/d/android/platform-tools/adb.exe, NCM SSH and Wi-Fi SSH.
Verify installed five partitions/config/notes/181 matched and both rollback
directories, Test253 daemon/config hashes, SOC/temp and healthy battery.

After authorized matched candidate deployment: exact boot/DTB/config/notes/
modules identity; battery-only150s; PC USB Sink+Device with ADB/NCM/Windows
enumeration and no Code43;5V-only source before fixed9V charger. Prove9V via
raw TCPM negotiation and power_supply/typec state, not UI. TCPM voltage_now is
contract telemetry, not an independent ADC reading: use a suitable inline PD
meter for actual VBUS/overvoltage evidence unless a calibrated X710 ADC path
is separately justified. Log full journals/debugfs when already available,
raw readings/timestamps,5min then20min windows and SOC/VBAT/IBAT/pack temp/
USB type/voltage/current budget/input programmed limit. Unplug must restore
online0/Discharging and negative pack current with trend verified. Charger->PC
same-boot reconnect gets new bounded<=60s recovery and>=150s responsive evidence;
do not relabel Test253's old cycles as new proof.

Stop immediately: actualVBUS>9.5V, VBAT beyond4440mV design, rapidly rising or
>=45°C pack temp in first run, repeated I2C/TCPC errors, reset/attach loops,
reboot/panic/Oops/CPU stall, both rescue transports lost, Code43, abnormal current,
SM5440 probe or any requested PPS/APDO. Higher source capabilities may be logged
but must never be selected. No deliberate thermal/OVP/OCP protection-limit test.
Disconnect charger on electrical/thermal anomalies. Preserve first failure and
stop subsequent stages; no automatic parameter increase/core workaround.

Rollback in TWRP using fresh label/UUID-verified rescue, known Test254 boot
ea73e65836ab316af658ed53273be0ec6351b335750978095e509054164509f7 and its matched
181 files retained before Test255. Same release name is not module identity:
retain a distinct Test254 directory before replacing it. Preserve existing
.gts9-test254-original Test252 and .gts9-test252-original Test249 directories.
Read back exact restored hashes, keep the other four partitions and rootfs
untouched, then one authorized ordinary boot/identity check. Do not initiate
rollback or device maintenance during this offline task.
