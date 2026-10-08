# X710 charging acceptance progression

## Current progression — 2026-10-08

Current implementation/identity are in [AGENT.md](../AGENT.md) and
[X710 charging architecture](X710_CHARGING_ARCHITECTURE.md). The original
Test256 plan below is historical; its thresholds and150s cable windows are not
substitutes for later independently registered scope.

- Short conservative pump step D: [Test345](../reference/boot-tests/test-345-final-refresh-reserve/PHYSICAL_RESULTS.md) closed after one<=30s run with native completion, fixed9 ordinary return, discharge/PC rescue and exact331 restoration. Prior failed rounds remain failed.
- Five-minute step E: [Test346](../reference/boot-tests/test-346-bounded-pps-five-minute/PHYSICAL_RESULTS.md) closed at the manual-handoff timeout before any PPS/pump activation, followed by exact Test331 restoration. It is neither a five-minute acceptance nor a charging hardware failure; its original STOP is retained and its guardian must not restart.
- Five-minute step E accepted in [Test347](../reference/boot-tests/test-347-confirmed-c1-five-minute/PHYSICAL_RESULTS.md): one native300s attempt,62 refreshes/63 parked-zero proofs, fixed9 ordinary charge31.022s, discharge15.606s and onePC rescue passed. Hardware1700/PPS+raw1800mA unchanged. Exact331/allfive/original181 restored offline; device stays **TWRP** per owner request. No restored Debian boot/runtime acceptance was executed. The one300s grant is consumed; no reactivation.
- Step F20min is independently prepared in [Test348](../reference/boot-tests/test-348-confirmed-c1-twenty-minute/README.md), using the [qualified1200s profile](../reference/charging/test347-twenty-minute-followup/RESULTS.md).49 runner/parser/transport tests pass; preparation/activationSOC<=60%, hardware1700/PPS+raw1800mA unchanged. The owner has now authorized one1200s physical attempt; preparation remains pending and the device stays restored331 in TWRP. Do not reuse Test347's consumed300s grant or repeatedly rebind300s. Final restoration again ends in TWRP.
- Higher-current step G is later and independent; no2/2.25/2.5/3A activation or vendor-equivalent45W claim is granted by short or longer-duration acceptance.

The closed Test347 used its registered runner: freshPC preflight/deployment admission,
drain the initial worker and verify OFF/unbound, then wait for the owner C1
handoff with no guardian running. A fresh candidate-boot-bound C1 reply,
received within120s, and fixed9 admission precede immediate guardian launch
and the sole300s activation. Persist the launch request before starting; a
lost launch response permits adoption of its original PID only, never replay.
Follow that guardian for native collection,
ordinary fixed9 charge30s, unplug/discharge15s, onePC device rescue check and
unconditional exact331 paired restoration. First non-clean stops; a host
observation timeout can only resume the same confirmed live guardian PID, not
start another pump run. Device evidence and transport uncertainty are separate.
The owner changed only the final restoration endpoint to TWRP. The charging
guardian and preparation watchers are terminal; no helper may restart this run.
No new PPS/pump operation is performed by this documentation update.

Independent ADC/current accuracy, protection calibration, hard-realtime cutoff,
long-term reliability and all vendor production behavior remain unproven.
Never provoke OVP/OCP/thermal protection or substitute source advertised power
for physical measurements. Record entry/stop/rollback criteria in every later
registration; do not implement future escalation before its prerequisites.

Documentation-only validation: `executed: false` for host tests/kernel build;
reviewed links and status against closed346/closed347/qualified0b731/registered348 evidence.
Reuse those qualifications; no new regression pass or hardware acceptance.

## Historical Test256 Stage3 plan — not a current registration


Offline Test256 preserves Stage2/Test255 and registers staged candidates. Every
physical test needs fresh authorization, registration pushed to origin/test,
current rescue/rollback/identity checks, and a distinct evidence directory.
No Stage3 hardware test or deployment is authorized by this document.

## Common entry and stop rules

Entry: working ADB/NCM/Wi-Fi; exact boot/vendor_boot/config/notes/DTB/paired
modules and accepted Stage2 rollback manifests; battery present/Good;
SOC5..<80, pack20..<38°C, VBAT3500..<4300mV. Preserve Test252/249 rollback,
Test253 reconnect, Test254 USER_NS/Docker and DCC absence. Save raw journals,
PowerSupply/Type-C data, I2C faults, initial/final identity and all transport
events. TCPM V/I is a contract; VBAT*IBAT is battery net power, not input power.

Stop first: pack>=42°C, abnormal rise/die temperature, VBAT approaching4440mV
or policy4300 limit, actual VBUS outside registered target/board range, any
REVBLK/OVP/UVLO/OCP/thermal fault, invalid/stale ADC/temp, TCPC/pump I2C error,
reset/attach loop, CHG_ON/VBUSPOK lost, unexpected reboot, kernel Oops/panic/
CPU/RCU/CSD stall, rescue loss or Code43. Do not provoke thermal/OVP/OCP limits.
OFF verification failure requires unplug/recovery; no blind voltage change.

## Ordered tests

| Test | Entry criteria beyond common gates | Expected evidence | Stop/rollback |
| --- | --- | --- | --- |
| A: passive probe | isolated Stage3B config/DT; no APDO/live coordinator | ID low nibble1/revision, modeOFF; unchanged ordinary charge and USB;150s | first fault; no pump activation; restore exact Stage2 pair if required |
| B: ADC on fixed PD | A accepted, known source, pumpOFF | new ADC_UPDATED per sample; real VBUS/VBAT/IBUS/die; compare external calibrated meter; no stale raw0 | timeout/scaling/settle discrepancy; remainOFF then rollback |
| C: PPS, pumpOFF | B + source APDO range; live adapter reviewed; OCP/sensor gates understood | actual contract/range, real VBUS tracking, timed refresh/exit,150s; no pumpON | PPS/TCPC/ADC fault; verifiedOFF, safe fixed restore; else unplug |
| D: <=1.8A short pump | C + approved protections/software OCP timing/PM/abort; explicit new authorization | initial30s,actual VBUS/IBUS/VBAT/gauge/temp, ON last, fresh samples, refreshOFF/settle/ON | first fault; verifyOFF -> PPSexit -> safe fixed -> switching; else recovery |
| E:5min | D clean; fresh same config/source/epoch gates | <=1.8A bounded300s, status/current/temp/fault/refresh history | common stops; same verified rollback |
| F:20min | E clean; no source/config substitution | bounded1200s, currents/temp/SOC, no resets/faults | common stops; same verified rollback |
| G:2/2.25/2.5/3A | each preceding current accepted, independent registration/review | repeat D/E/F with source/board/OCP caps; no cap changed by user sysfs | stop first at each level; return <=1.8A or Stage2 after review |

No Test G current is enabled here. Each pump stage must also prove charger
unplug150s -> PC reconnect using fresh Test253-style bounded ADB/NCM evidence
on the same boot, Sink/Device and no Code43. Fixed5V/9V ordinary limits cannot
increase. PM test comes only after transactional OFF/exit acceptance; do not
suspend with unverified pump state. Battery-only/cold/dock/OTG/DP remain outside
this registration and need separate tests.

## Rollback

The frozen `stage2-fixed-pd-known-good` reference points to the starting commit;
Test255 manifests identify its boot/vendor_boot/181-file module pair. A code
checkout alone is not a device rollback. After a separately authorized recovery
procedure, restore the exact accepted boot/vendor_boot and paired modules;
init_boot/dtbo/vbmeta/rootfs/USB/adbd stay as recorded. Read back hashes before
boot, then verify all three rescue paths/config/DCC/charging limits/journal.
No automatic rollback is performed by this offline task. Any inability to verify
pumpOFF or safe source voltage calls for physical disconnect and recovery.
