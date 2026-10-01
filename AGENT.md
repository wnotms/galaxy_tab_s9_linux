# AGENT.md — SM-X710 mainline port working rules

## Current state (2026-10-01)

Test265 Fedora-derived unwired PM core implemented: suspend latch/revoke grant,
checked OFF/fixed/measure/switching exit; resume never auto-arms and refuses
fault/epoch/inhibit.38 actual-C tests (10 new PM) and full1369 pass. Isolated
policy-offline Image/DTB/modules build passes; exact config delta only
X710_CHARGING_POLICY n->y, DTB byte-identical263; W1/sparse pass (knownVDSO
warning only, unchanged object hash). Final committed-source artifact audit
pending; initial precommit-revision mismatch report retained as host attribution
setup, not build failure. No device/flash/PPS/pumpON/USB/current/thermal change.
Read docs/X710_FEDORA_PM_PORT.md. Installed263 stays; activeStage3 NOT READY.

Test265 registers OFFLINE Fedora-derived PM transitions in unwired C core;
read Test265 README/registration. Adopt drain/OFF/fixed-before-suspend order,
revoke arming/latch suspend, checked errors and no resume auto-arm. No live
adapter/notifier/hardware API/device command; installed Test263 untouched.
One isolated policy-offline build/full qualification after implementation;
expected config delta only X710_CHARGING_POLICY=y, identical DTB/protected
hardware/containers/DCC. ActiveStage3 NOT READY. No physical test authorized.

Test264 OFFLINE review/helper PASS:55 affected tests, zero failures/errors/skips;
new future completion helper uses fresh child directory, preserves parent raw/
STOP, tests actual Recorder overwrite guard. Read Test264 RESULTS/summary/seal.
Fedora reuse approved; implement its drain/OFF/fixed-before-PM semantics with
checked errors, not unchecked fallback. No device/kernel/config/DT/USB change;
no build/full rerun, reuse ea938b24. Installed Test263 remains device accepted.
ActiveStage3 NOT READY; next unwired PM core, no automatic physical test.

Test264 continues OFFLINE from655d39fa: protection/watchdog/PM audit against
Samsung X710 and Fedora ab123e7d, plus future isolated completion evidence helper.
Read docs/SM5440_ACTIVE_PROTECTION_PM_PLAN.md and Test264 README/sources.
Owner permits direct use/port of Fedora same-model logic: adopt its OFF-before-
refresh and drain/OFF/fixed-before-PM order, with checked errors/readback rather
than copying unchecked restore or introducing private frameworks. No device
command/flash/reboot/PPS/pumpON/current/protection/config/DT/USB change.
Installed Test263 device acceptance stays complete; Test260 rollback intact.
Source review confirms unsupported HW OCP and vendor unchecked mode/WDT writes;
activeStage3 remains NOT READY. Reuse ea938b24 kernel qualification for this
host/docs-only phase; affected helper tests only, no kernel/full repeat.

## Current state (2026-09-30)

Test263 attempt01 DEVICE ACCEPTANCE COMPLETED under updated owner criteria:
PC30.220s/PD30.420s/unplug15.370s and final separate read-onlyADB/NCM/SSH/
Wi-Fi/config/notes/DCC/health pass on33435db7, no Code43/newfault. Original
pc-endpoint host filename-collision STOP preserved; not original runnerCLEAN.
Owner says device normal completes test, so no rollback/reflash/reboot/retrial
for this host defect; device remains Test263 with Test260 rollback intact.
Read attempt01 RESULTS/summary/CURRENT_STATUS/device-completion/raw seal.
Future physical acceptance: judge the registered device behavior; host-only
logging/parser errors are recorded separately and do not by themselves require
rollback or repeat physical windows when device evidence confirms normal state.
If device state is unknown, report incomplete evidence rather than invent a
pass. Actual device safety/identity/transport fault still stops; no current/
PPS/pumpON expansion. Results executed:false; exact qualification reused.
ActiveStage3 NOT READY (ADC calibration/OCP/PM/livehandoff unresolved).

Test263 attempt01 STOP at final PCendpoint: host recorder kernel-json filename
collision between Wi-Fi capture and ADB admit, original error/evidence retained.
PriorPC30.220s/PD30.420s/unplug15.370s pass; final1sample/ADB identity/no newfault
captured but NCM/Windows/DCC-service gate NOT complete. No observed devicefault
claim or retry-to-clean. Read attempt01 RESULTS/CURRENT_STATUS. Registered exact
Test260 rollback pending; no PPS/pumpON/current/protection/thermal/USB change.
Results executed:false; unchanged source qualification reused. ActiveStage3
NOT READY. Fix evidence namespaces offline with combined-recorder test before
any separately registered hardware attempt.

Test263 attempt01 unplug endpoint PASS15.370s/4samples on33435db7: offline
USB/TCPM/passive, Discharging -1.720..-1.063A, pack29.4C, SM5440 OFF/IBUS0/
validfresh/unchangedprotection, no new fault. Read UNPLUG_RESULTS/raw seal.
Detached4.096V is raw-zero ADC floor, not attachedsource/calibration. PCrescue
endpoint pending owner connection; no transition/recoverylatency claim.
Results executed:false, reuse15 focused checks/ea938b24 qualification; no
kernel/full repeat. No PPS/pumpON/config/current/thermal/USB change. Whole
series incomplete; activeStage3 NOT READY.

Test263 attempt01 fixed9V snapshot PASS30.420s/7samples on33435db7: reported
VBUS9.076..9.109V, IBUS0/OFF, validfresh/rawdecode/protection unchanged,
pack29.0..29.1C, netbatterymean7.813216W (not USBinputpower). Read PD_RESULTS/
CURRENT_STATUS/raw seal. Unplug15s endpoint and PCrescue remain pending owner
confirmation; no human-wait timer or transition/latency claim. Endpoint host
helper15 focused checks pass, no kernel/full repeat. No PPS/pumpON/current/
protection/thermal/USB change; whole series NOT complete, activeStage3 NOT READY.


Test263 attempt01 passivePC snapshot PASS30.220s/7samples on33435db7: exact
config/notes/partitions/181 modules, valid cachedraw/fresh age128..948ms/OFF/
unchangedprotection, bounded startup0x80 retained, no newfault/Code43. Read
attempt01 PC_RESULTS/CURRENT_STATUS/raw seal. Wi-Fi now10.191.121.33; PD host
uses verifiedpostboot address, 13 focused checks pass, no network setting change.
Fixed9V30s and unplug/PC endpoints pending owner cable confirmation. No PPS/
pumpON/protection/current/thermal/USB change; whole series NOT complete.


Test263 attempt01 boot/vendor and181 paired modules installed/readback verified;
original Test260 modules saved in .gts9-test263-original, older backups intact.
Root unmounted and BCB cleared. Candidate has not yet booted/accepted. Next one
normal Debian boot, exact config/notes/journal attribution and passivePC30s
snapshot observation. No PPS/pumpON/protection/current/thermal/USB change.


Test263 attempt01 verified TWRP identity/root/five original partitions/current181
modules and staged files; no boot/vendor/module write yet. Save/push this evidence
before paired installation. Exact Test260 rollback and older backups remain.
No PPS/pumpON/current/protection/USB change. Read attempt01 registration.


Owner authorizes Test263 physical acceptance (continue hardware test). Read
Test263 attempt-01 README/PACKAGE/STAGED_FILES before action. Reuse ea938b24
qualified snapshot candidate; host gate12/module adapter5/syntax/bundle pass,
no kernel/full repeat. Current18bce160 Test260 identity/rescue/safety passes.
Only paired boot/vendor/modules deployment, passivePC30s and owner-confirmed
fixed9V30s telemetry comparison, then endpoints; exact Test260 rollback in
fresh263 slots. Push registration before recovery/write; preserve oldbackups.
No PPS/pumpON/protection/current/thermal/USB change. Stop first non-clean;
no absolute ADC calibration claim or activeStage3 readiness.


Test263 OFFLINE QUALIFIED at ea938b245bff3ae9e3c1828751ea149a90337992: optional
root-read-only cached SM5440 raw ADC/freshness/startup/error snapshot, zero I2C
on read and unchanged hardware/charging policy. Read Test263 RESULTS/summary/
SHA256 and docs/SM5440_ADC_SNAPSHOT.md. Final build/embedded-config/DT/protected/
181-file pairing audit, 34 affected +11 PM checks and one full1351 pass; prior
1290 IDs retained. W=1/actual compatible sparse pass, known VDSO warning retained.
Config/DTB identical acceptedTest260;85 containers/DCC/96 protectedfiles intact.
No device command/deployment/rootfs/USB/current/thermal/protection/PPS/pumpON.
Device remains Test260/Test262. Next passive ADC evidence acceptance requires
new authorization/registration; no automatic physical test. Independent ADC
calibration/OCP/PM/live handoff still unresolved; ActiveStage3 NOT READY.
Results-only commits reuse exact qualification, executed:false, no rebuild/CI.


Owner requests next porting step. Test263 registers OFFLINE passiveSM5440 cached
ADC/raw/freshness evidence interface; read docs/SM5440_ADC_SNAPSHOT.md first.
No new register operation, PPS/liveadapter/pumpON/config/DT/current/thermal/
USB change or device command/deployment. Current Test260/Test262 fixed path
remains installed. New263 output directories; qualify source once with affected
checks + one build/full run, reuse for result commits. ActiveStage3 NOT READY;
ADC calibration/protection/PM still require separately authorized acceptance.


Test262 finalized COMPLETED_WITH_EVIDENCE_GAP: fixed9V/1.5A300.011s/61samples
chargingPASS (netbatterymean7.827W, SOC54→56%, pack28.4–29.2C); post-owner
unplug15.001s offline/Discharging endpointPASS and PCADB/NCM/Wi-Fi/config/
notes/DCC/health endpointPASS on same18bce160. Original unplug observerSTOP
waiting300s is retained; no captured transition or precise recovery time claim,
not whole-seriesCLEAN. Read Test262 RESULTS/summary/SHA256. HostparserfirstSTOP
and pretestWindowschimes/rootcauseunknown retained. Device remains Test260
passive onPCUSB; no hardware/config/source change/reboot/flash/PPS/pumpON.
Reuse44 affected tests and Test260 pairing/build, results executed:false.
ActiveStage3 NOT READY; no automatic next physical test/current increase.


Test262 charging phasePASS retained. Original unplug observer STOP waiting300s
before owner removal; keep its rawSTOP and do not claim captured transition.
After owner's "已拔", separate read-only15.001s endpoint confirms offline/
Discharging/current-0.91..-1.129A/pack29.6C, same18bce160/no newfault. No new
charging trial. PC rescue attachment/check now pending owner confirmation; use
one bounded check afterward, not a human-wait timer. WholeTest262 has an evidence
gap and must not be labeled whollyCLEAN. No PPS/pumpON/config/reboot/flash.


Test262 attempt02 fixed9V/1.5A charging phase PASS300.011s/61samples on18bce160:
netbatterymean7.827W, SOC54→56%, pack28.4–29.2C, passiveSM5440 OFF/IBUS0,
no newkernel/CPU/failedunit/passivefault. Read CURRENT_STATUS/charging RESULTS.
Unplug15s verification and freshPCADB/NCM/Wi-Fi gates pending; wholeTest262
not yet complete. FirsthostparserSTOP and Windowschimeincident retained.
No actual inputpower/calibratedVBUS claim, no20min extension, no PPS/pumpON/
configuration/reboot/flash. Reuse44 affectedhosttests and Test260 pairing/build.


Test262 charging attempt01 STOP before charger prompt/window due host parser
empty@@failed EOF recognition, no physical charging fault or device change.
Retain charging/RESULTS/raw STOP/seal. EOF correction44 affected tests+syntax
pass, no kernel/full repeat. Fresh charging-attempt-02 uses same18bce160 boot,
unchanged300s5V/9V limits and first-fault stops. Push registration, start Wi-Fi
collector, wait ARMED, then request18W C2 connection. No PPS/pumpON/reboot.

Test262 charging has NOT started yet. Owner reports Windows connection sounds
resolved after manual PC-USB replug; fresh ADB/NCM/Wi-Fi/boot/battery/passive-OFF
gates pass. Read usb-chime-incident RESULTS/summary/raw seal. Root cause unknown;
no USB/kernel/service change or repeated-reconnect qualification. Keep incident
separate from charging results. Resume registered300s fixed-PD via Wi-Fi only
once collector is ARMED, then request the owner's18W source connection.

Owner authorizes ordinary charging test. Test262 registers300s SM5714 fixedPD
on currentTest260/18bce160, priorLenovoYG65G C2 18W source, WiFi10.191.121.145.
Read Test262 README before cable action. No PPS/pumpON/current/config change,
reflash/reboot or automatic20min extension. Keep SM5440 passive/OFF and first
fault stops; record battery netpower vs contract/ICL ceilings separately.
PassiveADC is uncalibrated; no inputpower/absolutevoltage safety-proof claim.
Qualify affected host tests only, reuse Test260 artifact/kernel qualification.

Test260 attempt02 PASS bounded passivePCUSB: boot18bce160,150.197s/30samples,
181 modulehashes/partitionreadbacks/config/notes match. First-only0x80 retained:
pending0.290025s/event0.290045s/confirmed2.609795s; two fresh safe conversions,
Good health/IBUS0 throughout, no newkernel/CPU/failedunit/Code43. ADB/NCM/WiFi
pass; dynamicAPIPA169.254.59.206 matchesWSLeth2, one-shotboundauth, no retries.
Read attempt02 RESULTS/summary/rawseal; historicalTest258/259 failures unchanged.
Device now stays on passedTest260 passive, exactTest255 original modules in
.gts9-test260-original plus rollback images retained, older tested backups intact.
No PPS/pumpON/protection/current/thermal/USB change. No automaticnextphysicaltest.
Passive pass is NOT ADC calibration/OCP/PM/direct readiness; ActiveStage3 NOT READY.

Test260 attempt02 installed sealed boot/vendor_boot and181 paired modules with
five-partition readback; exact Test255 original modules saved in fresh260slot.
TWRP root unmounted/BCB cleared, candidate not yet booted/accepted at this record.
Next one normal Debian boot, ADB-first admission and150s passivePCUSB observation;
stop first and restore Test255 if needed. No PPS/pumpON/protection/currentchange.

Test260 attempt01 STOP before deployment: unsupported journalctl --no-legend
auxiliary capture, raw firsterror retained; no recovery/devicewrites occurred.
Attempt02 corrects the host spelling before first physical test; inherited
preflight timestamps are explicit and sameboot/config/notes/battery/history
refresh passes. Same sealed artifacts/slots, affected6+actualarchive5 reused.
Read attempt02 README; original owner flash authorization still applies to
this predeployment correction, not to retry after a physical failure.

Owner now authorizes "开始刷机测试": Test260 attempt01 passive PCUSB150s only,
superseding prior no-flash scope for this attempt/rollback. Read its README.
Reuse source6fbafede sealed candidate/full1290, no rebuild/fullrepeat. ADB-first
hardware admission unchanged; explicit30s host-readiness adapter/source-bound
one-shotSSH, first unready delay retained as suspect. Keep first faults and exact
Test255 rollback/new260 module slots/older tested backups. No PPS/pumpON/current/
protection/thermal/USB change. Register/push before recovery/write; stop first.

Test261 source3ecf2093: explicit NCM host-readiness/source-bound SSH entry passes
one read-only check on acceptedTest255 bootcfb09d01. Windows NIC9 preferred
169.254.74.160/16 matches WSLeth2/directroute; noCode43, oneSSH0.83s, sameboot.
First metadata capture13.883s is not APIPA recovery time.109 affectedhosttests
and syntax pass, no routing/kernel/build changes or full/buildrepeat. Read
Test261 RESULTS/summary and docs/NCM_HOST_READINESS.md. HistoricalTest259 early
~9.3s SSHtimeout cause remains unknown; no startup/reconnect qualification.
No flash/reboot/configuration/device writes; Test260 stays offline/unaccepted.

Owner clarifies "先修 NCM，暂不刷机". Test261 registers host-only bounded NCM
readiness and one source-bound SSH connection on unchanged Test255. Read
docs/NCM_HOST_READINESS.md and Test261 README. No flash/reboot/rootfs/network/
USB/kernel/charging changes; Test260 remains offline. Preserve first unready
metadata/first SSH failure; no retry-to-clean. New helper is opt-in for fresh
registrations, never silently changes old runner deadlines. Historical Test259
timeout cause is not established. Qualify affected host tests only; no rebuild
or repeated full kernel regression for this host-only change.

Test260 offline correction source6fbafede now qualifies: startupREVBLK first-only
confirmation state; build/bundle/protected/config/DT/181module audit andfull1290
pass, all prior1270IDs retained. Driverfocused23 and W=1/sparse pass (one retained
VDSO warning). Host-only followup5ee5ce56 captures tablet-side state on every
transport failure; affected12 admission checks pass, no rebuild/fullrepeat.
Config/DTB identicalTest259;96 protectedfiles/85containers/DCC unchanged. Read
Test260 RESULTS/summary/PHYSICAL_PLAN. No physicalattempt/flash/reboot/settings
change: currentcfb09d01 remains acceptedTest255. Readonly transport works now,
historicalNCMtimeout rootcause unresolved. Startupfix has NOhardwareacceptance;
noautomaticphysicalretry, no0x82whitelist/PPS/pumpON/protection/currentchange.
ActiveStage3 NOT READY. Futurepassive test needs fresh registration and retained
startup-warning classification; qualified artifacts are reused, not rebuilt.


Owner requests continued repair. Test260 is OFFLINE: narrow first-only inactive
startupREVBLK confirmation (two new safe conversions within5s), retained raw
startup event, UNKNOWN/noADC publication while pending. Live/recurrentREVBLK,
allVBAT_OVP (including0x82), unsafeADC/I2C/deadline/protectionchange/PM still
stop. Read docs/SM5440_PASSIVE_STARTUP_STATE.md and Test260 registration.
ADB-first host admission saves hardware evidence before NCM; first transport
failure is retained, no retry-to-clean. Current read-only Windows/WSL snapshots
show mirroredAPIPA eth2 and working boundbanner/NCM on restoredcfb09d01;
historicalTest259 timeout cause remains unknown. No USB/config/rootfs change,
no physical retry/reboot/flash/PPS/pumpON authorized by this offline correction.
Qualify changed candidate once; preserve frozenTest258/259/Test255 artifacts.
ActiveStage3 remains NOT READY; passive hardware acceptance pending.


Test259 source74e75de6 fixes first-fault INT/STATUS/ADC/protection provenance;
passive build/bundle/protected/config/DT audit/full1270/related15/archive5 pass.
Attempt01 hosthelperpath STOP before permanentwrites retained. Attempt02 installed
and booted08af1c86, then firstNCM SSHtimeout + source0x80: INT3=0x62 vs live
STATUS3=0x20, modeOFF, ADC4.867V/3.938V/0A/28.5C. See RESULTS/FAILURE_ANALYSIS.
No150s pass, no retry-to-clean, no PPS/pumpON/protection/current change. This
cannot prove priorTest2580x82 benign. ExactTest255 fivepartitions/181modules
restored; finalbootcfb09d01 passes13 health/rescue gates, WiFi10.191.121.114;
Test258/Test259 testedmodules preserved. ActiveStage3 NOT READY. Next is offline
vendor startup-latch/state/protection audit and separateNCM timing diagnosis,
not faultmasking or another automaticphysicalattempt. Results commits reuse
unchanged qualifications (executed:false); no CI or rebuild/fullrerun.


Owner requests "修复并继续测试". Test259 fixes passive first-fault provenance
only, retaining all fault stops and fixed-PD behavior. Read its registration.
Qualify changed source once, seal/push before the authorized PC-USB passive
physical test; use distinct Test259 slots and preserve Test258 failed modules.
No PPS/pump ON/protection/current change. On first fault retain raw evidence,
stop and restore exact Test255. Do not mask0x82 to obtain a pass. Prior offline-
only next-step restriction is superseded for this bounded diagnostic test.


Test258 attempt02 physically installed/booted the qualified passive candidate:
paired boot/vendor_boot and181 modules passed readback, SM5440 revision2 probed
on0-0063, ADB/NCM/Wi-Fi/Sink-Device/no-Code43 gates passed. First source fault
at1.608590s is software bitmap0x82 (VBAT_OVP+REVBLK); first host sample30.07s
reports Unspecified failure with stale/unavailable ADC fields. STOP, no150s
pass and no retry. No PPS/pump ON/current increase. Exact Test255 rollback
boot/vendor/181 modules completed; all five partition readbacks match, candidate
modules retained at .gts9-test258-tested. Final bootf965e054 has12 health/identity/
rescue gates passed, Wi-Fi10.191.121.242, battery62%,29.2C,4018mV,Good.
Read attempt02 RESULTS/FAILURE_ANALYSIS/summary. Raw fault provenance is missing
(INT latches merged with STATUS); actual overvoltage is not established. Next
is offline first-fault raw-snapshot/vendor-state audit, not another physical
attempt/PPS activation. Active Stage3 remains NOT READY. Reused build/full1264
and5 focused archive checks; no repeated build/full run for result commits.

Owner now requests "继续实机测试": Test258 attempt02 registers the SAME passive
candidate with the release-root install helper. Read attempt02 README first.
Fresh runtime preflight on0456f423 finds ADB/NCM/Wi-Fi10.191.121.119 working;
old Wi-Fi failures are retained, cause/recovery timing unknown. Reuse f3a266b5
build/full1264 and a4437ece five actual-archive host tests, no rebuild/full rerun.
Push registration before recovery. TWRP verifies baseline partitions/modules
before installing paired boot/vendor_boot/modules;150s PC USB passive only.
No PPS/pump/current increase. Stop first, retain evidence and restore accepted
Test255 if needed. Earlier stopped attempt below is immutable, not continued.

Test258 physical deployment STOPPED before image writes/current-module rename:
the qualified module archive is release-root, while the historical staging
helper expected lib/modules. Keep the first failure, raw recovery and results.
Five partitions and181 original modules verified unchanged; failed extraction
removed, root unmounted/BCB cleared, ordinary Test255 returned on0456f423.
ADB/NCM remain working, no Code43/new kernel fault/failed unit; Wi-Fi SSH to
new DHCP10.191.121.119 failed initially and in one read-only diagnostic retry.
Do not call Test258 booted/passed; its150s candidate observation never started.
No candidate retry/PPS/pump. A release-root helper is prepared offline separately
with real-archive transaction tests; it has not been sent to the device.
Next deployment needs a fresh bounded registration and working rescue preflight,
using unchanged qualified artifacts without another kernel/full host run.

The owner requests reduced checking overhead. The change-scoped workflow below
supersedes historical requirements to rebuild/retest after every commit. Qualify
each candidate once; documentation/results commits do not invalidate unchanged
source or artifacts. Do not repeat a full build/regression because HEAD changed.
Test258 source f3a266b5 already passed its passive build, artifact/bundle audit
and all1264 host tests. Reuse those exact hashed artifacts for the authorized
test; retain essential device identity, rescue/rollback, battery safety and
write/readback gates. Active PPS/pump authorization remains unchanged.

The owner now explicitly requests "刷入测试吧". Test258 registers ONLY the
separate SM5440 passive profile: pumpOFF, no PPS/live transaction core, ordinary
PC USB150s. Read its README/preflight before any action. Preliminary current
boot c1716879 has accepted Test255 five-partition/config/notes/181-module and
rescue identities, but vendor lpcharge=1 differs from the accepted command line.
Read-only diagnosis passed every other gate. Registration permits ONE ordinary
baseline reboot after push to restore normal entry; no image/module repair or
candidate flash before a fresh normal-preflight passes. Keep all STOP evidence.
This authorization supersedes the earlier offline-only restriction for these
specific Test258 actions; active PPS/pump tests remain NOT READY/unapproved.

The owner has requested continued OFFLINE development without flashing.
Continuation starts at a3ddd0de on test. Test257 registers transaction source-
offer/freshness/monitor-deadline guards and a deeper software-OCP audit. Keep
Test256 evidence sealed. This does not authorize device commands, a live PPS
adapter, pump ON, new APDO, configuration/DT/current/float/thermal changes.
Read docs/SM5440_SOFTWARE_OCP_AUDIT.md and Test257 registration first.

Test257 source31ca86ca now has offline source-offer/freshness/monitor guards.
Full1253 host tests passed, with all1239 previous IDs retained and14 new.
Default fixed Image/DTB/config/notes/module archive are byte-identical to Test256;
isolated policy build retains the same config/DT gates and181 module-directory
files. No DTS/config/hardware-driver changes. The core remains unwired and
unarmed by default;500ms facts/100ms ADC-monitor refusal limits do NOT qualify
physical software OCP. Actual protection, ADC, sensors and live transaction/PM
adapter remain unresolved. Read Test257 RESULTS/summary before continuing.
No flash, tablet command or hardware acceptance occurred; active PPS NOT READY.

Test257 post-record build/config/DT/protected audit passed at260133f0. Its host
rerun exposed global sync waiting on WSL/Windows mounts; three interrupted runs
are preserved, not passed. Follow-up scopes ONLY temporary host boot-record/
misc.img fixture sync to real syncfs on that filesystem and adds30s waits;
device scripts unchanged. Focused66 and changed/full1255 passed with zero
failures/errors/skips; all1253 Test257 IDs retained,2 fixture checks added.
Read Test257 POST_RECORD_CHECKS.md and post-record evidence/summary. Original
Test257/Test256 seals and qualified outputs remain immutable. No device action.

The owner now authorizes **offline X710 vendor charging audit and staged
refactor/SM5440 development only**. Start HEAD is ebf4af1c, work branch test.
Read docs/X710_VENDOR_CHARGING_AUDIT.md, X710_CHARGING_ARCHITECTURE.md,
SM5440_REGISTER_AUDIT.md, SM5714_SM5440_HANDOFF.md and
X710_CHARGING_TEST_PLAN.md, plus Test256 registration. Samsung sources under
/home/ms/Samsung/kernel_platform are read-only evidence; Fedora snapshot is
ab123e7d. Preserve sealed Test255 and its installed fixed5/9V limits, float,
thermal, Test253 adbd/Test254 container gates and rollback pairs. No device
commands, deploy/flash/reboot/modules/rootfs changes, live PPS or pump activation.
Keep Stage3A/default fixed behavior separate from passive Stage3B/profile.
Direct activation remains blocked by actual ADC/OCP/sensor/transaction acceptance;
vendor aggregate protection init must not be copied blindly. Use the current
change-scoped validation rules below; push origin/test, no CI/main merge.
The earlier physical history below is retained, not new device authorization.

Test256 offline source revision61336aff is now qualified. Read its RESULTS.md,
BUILD_RESULTS.md, summary.json and validation evidence. All1239 host checks
passed with no failures/errors/skips (1200 retained +39 added). Default
fixed-refactor config adds only CHARGER_SM5440_DIRECT=n; DTB is byte-identical
to Test255. Separate passive/policy profiles enable only the pump monitor and
optional unused transaction core, with only charger@63 status changed. Each
candidate has181 paired module-directory files;96 protected files,8 Stage1
helpers,62 reference sources and frozen Stage2 artifacts are intact. W=1/sparse
reported no changed-driver diagnostics; dtbs_check retains the baseline unbound
PS5169 usb-role-switch type diagnostic, not a clean whole-board schema result.
No device commands or deployment occurred. Live PPS/pump-ON remains unavailable:
software OCP/protection, actual ADC/sensors and live transaction/PM adapter are
unaccepted. Active Stage3 candidate NOT READY. Next requires separately registered
passive probe/ADC acceptance, never automatic PPS or pump activation. The
stage2-fixed-pd-known-good tag preserves ebf4af1c; use the accepted artifact pair
for an authorized device rollback, not a rebuilt refactor image.

The owner has revised the Test255 workflow to connect the existing Lenovo
YG65G USB-C2 18W PD supply directly and inspect power/battery telemetry.
Attempt03 registers this bounded observation without an external VBUS meter or
separate5V-only supply. Read its README before continuing: measured battery net
power is VBAT*IBAT; TCPM voltage/current and switching input-current limits are
policy values, not actual charger input watts. No kernel/driver/DTS/rootfs or
charging-policy change, reboot, flash or Stage3 is authorized by this revision.
Registration b63fad60 and23 fresh Wi-Fi identity gates preceded attachment.
Attempt03 first300.011s fixed9V/1500mA battery telemetry passed:61 positive
current samples, mean battery net7.771W, SOC59->61%,28.7..29.7°C.
The full1500.060s charging window now passed:301 positive-current samples,
fixed9V/1500mA, mean battery net7.828W, SOC59->69%,28.7..31.5°C,
no detected new kernel fault/failed unit. Unplug150.005s passed; nativeADB/
NCM recovery<=14.056s with no failed initial command/new warning, followed
by156.412s PC USB stability, passed on the same boot/PID827. Fresh final22
identity gates, native binary-config transfer, PnP/banner/NCM/Wi-Fi and
all three181-file rollback directories/settings match. PC temperature
34.1..35.1°C(final35.2), input500mA; net battery discharge on PC is recorded
separately. Charger is disconnected, computer USB/Wi-Fi retained. Read
attempt03 RESULTS.md/summary.json. No reboot/flash/config/driver/rootfs
change or Stage3 occurred; no independent actual input watts/VBUS claim.
Final all1200 host checks passed in96.129s with zero failures/errors/skips;
all retained tests remain present, no CI. Per-stage/raw evidence is sealed.
The independent physical-VBUS gate remains unobserved, not passed. Earlier
sealed attempt01/02 results remain unchanged.

Latest installed Test255 Stage2 candidate boot is `d745248e…`, following the
owner's reported manual reboot after attempt01 battery testing. Attempt02
initial27/final26 identity/health gates and a fresh162.143-second PC USB window
passed: ADB binary-config transfer, NCM authenticated SSH/interface-bound
Windows banner, Wi-Fi, Sink/Device, no Code43/new kernel fault/failed unit.
Candidate boot/vendor_boot/config/notes/exact181 modules and all three181-file
Test254/Test252/Test249 rollback directories plus Test253 settings are intact.
No reboot or software/hardware change was commanded in attempt02. Read its
`RESULTS.md`/`summary.json` under Test255 before continuing. A fresh changed
host invocation executed all1183 tests with zero failures/errors/skips in98.483s;
the earlier WSL sync interruption remains preserved as a separate failed run.
Attempt01's155.473-second battery-only pass is retained; its following same-boot
PC reconnect was interrupted by the manual reboot and is not passed. Fixed-PD
5V-only/9V charging and charger-to-PC acceptance remain unexecuted: no independent
VBUS meter/5V-only source is available. No PD charger was connected by this
attempt, no full Stage2 acceptance or Stage3 work is claimed.

### Earlier first-boot physical checkpoint (superseded by attempt02)

Test255 attempt01 Stage2 candidate has now been installed and booted under the
owner's physical-test authorization. TWRP readback and Debian first-boot
identity passed: boot26ef6bd1…, vendor_boot d80d03cd…, config cd7ec9cb…,
notes fb3d2496…, exact181 modules; init_boot/dtbo/vbmeta stayed Test254.
The new boot a5b8b87f… reports Type-C Sink/Device; ADB, NCM and Wi-Fi work,
Windows has no Code43, and first-boot plus a 991-second same-boot kernel scan
found no new fault. Test254 boot/vendor_boot images and 181 modules are retained
as a distinct rollback pair beside the Test252/Test249 backups. See
`reference/boot-tests/test-255-sm5714-fixed-pd/attempt-01/CURRENT_STATUS.md`
and its raw preflight/recovery/install/boot/postboot/holding-status evidence.
The first 300-second USB-connected waiting monitor did not count as battery
testing. After the owner disconnected the PC cable, a fresh 155.473-second
battery-only window passed on the same boot, with USB offline, Discharging,
negative current, Good health, stable temperature and no new kernel fault.
Await manual PC USB reconnect, then verify ADB/NCM/SSH for 150 seconds on
the same boot. The Lenovo 18W PD charger
has not been connected; no independent VBUS meter or 5V-only source is
available, so fixed 5V/9V acceptance remains pending. Do not start Stage3.

### Earlier offline-candidate record (before physical authorization)

Test255 was an **offline Stage2 fixed-PD candidate**, prepared under the
owner's explicit no-device-command/no-flash instruction. Installed state stays
Test254 with Test252 Stage1 and Test253 userspace adbd repair; no live identity
query, reboot, partition/module/rootfs change or Stage3 occurred. Starting local
and origin/test HEAD was26d62393; plan c799fadf preceded implementation814788a3.
Read docs/SM5714_STAGE2_PD_PLAN.md and Test255 README/SOURCE_AUDIT/BUILD_RESULTS/
RESULTS/ARTIFACTS/validation/summary.json before proposing hardware work.

Candidate uses stock Linux7.2-rc3 TCPM and a built-in SM5714 TCPC transport at
hub9/0x33/400kHz/GPIO133-low. Sink+Device only, fixed5V1800/9V1500mA; actual9V
switching input<=1500mA(13.5W), positive grant honored. Q4 charge-off plus100mA
hardware input minimum covers zero/subminimum budget, pending TCPC probe/fault;
it is not complete VBUS/VSYS isolation. Original4440mV float, pack thermistor,
2100mA pack cap, thermal helpers and suspend stop-charge remain. No Source/OTG,
role-swap/dock/DP/PS5169/SBU/PPS/SM5440 driver or register operation was added.
Inherited SM5440 DT child is disabled/unlinked; hub3/GPI remains unchanged.
DWC3 stays peripheral with retained USB2 graph; delete its inherited inactive
usb-role-switch flag so TCPM does not defer waiting for an absent provider.
TCPM/DWC3/gadget/adbd/rootfs and OPP sources are unchanged.

Exact Test254 resolved-config delta is only TYPEC_SM5714 absent->y; config
cd7ec9cb…, notes fb3d2496…, DCC off and all85 container gates preserved.
Final Image f1ce90a4…, DTB c6148471…, archive28e33cda… and181 paired files/
167 ko passed embedded-config/source/DTB/depmod/archive checks. Separate outputs
out/kernel-sm5714-stage2 and out/boot-bundle-sm5714-stage2 preserve rollback.
Boot26ef6bd1… and vendor_boot d80d03cd… both carry the new DTB; exact old cmdline,
bootconfig/ramdisk and init_boot/dtbo are retained. Generated vbmeta is not the
accepted installed vbmeta: never deploy generated init_boot/dtbo/vbmeta.
Changed/wrapper/full each execute1183 tests with zero failures/errors/skips;
35 new,1148 retained. An earlier PTY partial-read fixture failure was separately
fixed in a718bd89 without weakening assertions; raw failed evidence is retained.
No GitHub Actions or CI. No hardware acceptance/safety guarantee is implied.

At that time, future Test255 required fresh authorization plus pushed rescue registration,
retained Test254 boot+vendor_boot+181 modules alongside Test252/Test249 pairs,
and an independent measured-VBUS gate (TCPM voltage_now is contract state).
Use registered battery150s/PC Sink-UFP/5V/proven9V/5min-then20min/unplug150s/
same-boot charger-to-PC bounded reconnect gates; stop first anomaly. No device
work is authorized by this offline result. Water detection, USB3 orientation,
suspend PD continuity and BC1.2/PD timing remain unaccepted; no Stage3.
Test254's independent Docker I/O/registry/GUdev/network/rootless/cable limits
remain as recorded. Preserve every old sealed/stopped result and the bounded
Test247/Test249 DCC conclusion.

### Previously recorded installed-state history (preserved)

The owner subsequently authorized **“刷入测试”**. Test254 attempt01 stopped
before any device write on initial Windows Code43/absent rescue transports;
its result/raw evidence remain immutable. Owner confirmed manual reboot and
computer USB attachment. Attempt02 fresh full Test252 identity/rescue passed,
and registration369ebe3a was pushed before maintenance. TWRP installed only
candidate boot ea73e65836ab316af658ed53273be0ec6351b335750978095e509054164509f7
and181 paired modules, retaining exact Test252 modules at .gts9-test254-original
and the older Test249 backup. Temporary label-validated misc BCB was cleared.
TWRP blkid returned no UUID; raw ext4 superblock verified the original microSD
before any module/boot write. Four other partitions are unchanged/readback verified.
Current boot6c3dde80334e495589169a1e576c8024 has exact Test254 config c80d3c66…
and notes7bbb0dc3…, DCC absent, protected Test253/USB/SSH unchanged, no failed
unit/kernel fault and ADB/source-bound NCM/Wi-Fi working (Wi-Fi10.191.121.241).
Boot151.6s observation, USER_NS/mqueue/cgroup2 and unchanged PrivateUsers=yes
UPower activation/battery enumeration now pass. Two GUdev assertions remain
independently recorded. Debian Docker26.1.5/CLI/containerd/runc/iptables-nft/
uidmap/ipvsadm installed (11 new/no upgrades), daemon cgroup2/overlay2/seccomp
passes. Attempt02 stopped on first direct Docker Hub pull timeout; its raw
incident/full post-stop/seal remain preserved, no container/cable test run there.
Host official registry access works; separately registered attempt03 verified
four official ARM64 image source/config/layer/archive identities and loaded them
on the same boot. Actual hello-world/trixie/mqueue plus CPU/memory/pids/cpuset
controls pass. Attempt03 stopped at first ineffective I/O limit (io.max empty).
Fake-endpoint analysis proves the installed CLI sends empty throttle arrays
before contacting the real daemon; internal client cause not established.
BLK_DEV_THROTTLING=y/io controller/file exist: this is not proof of missing kernel
throttling. No Docker/client/kernel/service workaround applied. Test container
cleaned. DNS/outbound/NAT/publishing/optional networks/IPVS and physical cable
regression were not executed after the stop; do not claim full Docker acceptance.
UPower's two GUdev assertions and direct registry access remain unresolved;
rootless runtime/delegation unaccepted. Full final same-boot five partitions/
181 current+181 Test252+181 Test249/DCC/protected settings/three transports/kernel
and healthy battery pass (1430.74s,71%,29.0°C,4.062V,SDP500mA). No Stage2/3 or
extra charging test. Candidate remains installed, exact rollback retained, no
rollback executed. Read Test254 RESULTS/PHYSICAL_SUMMARY/CURRENT_STATUS and
attempt03 RESULTS before a separately scoped client-input investigation.
Preserve all old stopped results and original sealed offline documents.

The owner authorized offline UPower/OCI kernel configuration enablement only.
Test254 is a separate **unflashed candidate and future acceptance plan** under
`reference/boot-tests/test-254-debian-container-kernel/`; read its BUILD_RESULTS
and README before any later action. USER_NS resolves the missing kernel
prerequisite for shipped UPower PrivateUsers=yes, without a service workaround.
The container gate runs after olddefconfig. Preserve Linux7.2-rc3, DCC off,
SM5714/ADC5 Gen3 and all hardware/adbd/rootfs settings. Build outputs are
isolated in out/kernel-container-candidate so Test252/rollback artifacts remain
intact. Final offline kernel+modules and85 prerequisite gates pass; exact config
delta96 entries has zero unexpected changes (39 explicit+6 dependency enables).
DTB is byte-identical; all181 paired module archive files are verified. Required
wrapper/changed/full each execute1148 retained tests with zero failures/errors/
skips; new24 config checks pass. Host no-argument sync is qualified by real
syncfs on repo ext4 and /tmp tmpfs after an unrelated WSL global-sync block;
original incomplete runs are preserved, no helper/test/selector changed.
This task does not authorize deployment, device commands, hardware
acceptance or Stage2/3. Installed state and the unresolved installed UPower
issue remain as recorded below until a separately authorized physical test.

Current device is the authorized **Test252 Stage1 candidate**, not the exact
accepted Test249 production image. Battery-only/ordinary charge/plug-out windows
passed, but the attempt stopped on USB ADB offline after computer reconnect.
NCM and Wi-Fi SSH work; candidate identities/181 files and181 rollback files
remain verified. Stage1 full acceptance is incomplete; Stage2/3 have not started.
Read `reference/boot-tests/test-252-sm5714-stage1/RESULTS.md` before hardware work.
The historical accepted production baseline remains Test249 below.

The owner requested "先解决adb问题" then "继续修复adb吧". Test253 uses a
separate optional Debian34.0.5-12 userspace daemon at
/usr/local/libexec/gts9-adbd-reconnect, selected by gts9-adbd-run. It repairs
glibc worker-completion and retained-ep0/BIND handling, preserving packaged
adbd, restart guard/holder and NCM/SSH/kernel/charge settings. Initial preflight
stopped on UPower217/USER: shipped PrivateUsers=yes with USER_NS disabled.
The owner adopted an exact hash-pinned classification; that independent UPower
issue remains unresolved. Source/build and1088 host checks pass.

Attempt02 installed the fixed daemon/launcher/ExecStart and issued one normal
boot,461c1408e42643afae5b48162771d077, PID834. Exact Test252 config/notes/five
partitions/181 paired/181 original files and DCC/runtime profile still match.
Native shell and152.945s responsive observation passed. Connected Windows
`adb reconnect` then removed the host transport and native recovery could not
be established; attempt02 stopped before file transfer/physical cycles.
NCM/Wi-Fi SSH, device worker/monitor and PnP remain normal, no Code43/CPU fault.
The daemon is installed but reconnect acceptance is incomplete. No extra
reboot/reset/device-service restart occurred. Current Wi-Fi address is
10.191.121.29 (DHCP changed from195). Read attempt02 RESULTS/summary/evidence.

Attempt03 independently reopened the same37.0.1/LIBADBUSB Windows ADB server
once; native USB shell and1MiB byte/hash roundtrip now pass, with same boot/
PID834/hash and uninterrupted NCM SSH. The device was not rebooted or reset,
and no device service/config changed. Current native ADB works. The owner performed physical cycle01; native ADB recovered on the same
boot/PID/hash, but the sampler wrongly required UDC to stop showing configured
while USB supply was offline. Recovery<=60s/150s elapsed evidence was not
collected, so attempt03 is stopped with one cycle performed and zero accepted.
Full post-stop five-partition/config/notes/181+181/DCC/protected-settings and
ADB/NCM/Wi-Fi checks pass with no Code43/failed unit/kernel fault. A new
pre-enable FunctionFS DISABLE warning was recorded before ENABLE/new worker;
review source before future classification. No further cable cycle/reboot/reset
was made. Read attempt03 RESULTS/review; keep all old outcomes/seals intact.
`scripts/gts9-adb-host-rescan.sh` is the verified host recovery for the observed
missing table entry; raw `adb reconnect`37.0.1 remains an unresolved separate
limitation. Do not switch backend, modify production or start Stage2/3.

Attempt04 was explicitly adopted (reply: "使用新方案") and completed3/3
bounded physical cable-recovery cycles on the same boot461c.../PID834/hash.
Native+NCM recovery upper bounds14.100/15.346/15.060s, followed by real ADB/
NCM/Wi-Fi responsive windows155.487/155.466/151.345s. Each cycle's first NCM
8s timeout recovered inside60s and is retained; cycle02 also had first native
not-found before enumeration. This is accepted bounded recovery with observed
transients, not three transient-free Test250 CLEAN rounds. Two exact new
pre-enable DISABLE W events satisfied the adopted contextual/source/count/5s+1s
bounds; cycle03 had none. No other new daemon fault or CPU/kernel signature,
extra boot, Code43 or failed unit was detected.
Full final five-partition/config/notes/181 candidate+181 original/DCC/daemon/
protected-settings/kernel/three-channel acceptance passes; Windows37.0.1/
LIBADBUSB status is unchanged. The single final full check also serves cycle03's
post-gate. No software/backend/driver change, device or host-server restart,
reset/flash/reboot occurred in this attempt. Host implementation validation
1124 all+33 focused, adoption33 and final87 archive tests pass.
Read attempt04 RESULTS/summary/seals and Test253 CURRENT_STATUS.md. Physical
USB ADB reconnect is now verified within these windows; raw connected Windows
`adb reconnect` remains unaccepted with a separately verified host rescan
workaround. Preserve all earlier stopped attempts/seals. Current Test252 Stage1
kernel remains installed, its original attempt still stopped/unaccepted; do
not retroactively pass/promote it or begin Stage2/3/extra charging tests. Future
hardware work needs its own authorized registration and fresh preflight.


The production DCC-path repair is deployed and accepted on the SM-X710. The
pinned Linux 7.2-rc3 production build has `CONFIG_HVC_DCC=n`, matching boot and
vendor_boot images, and all 181 matching module files. Test249 verified the
first boot from TWRP for 158.22 s and one ordinary warm boot for 120.09 s; a
later same-boot check verified all five partition hashes, the 181 modules and
no new kernel fault. `/dev/hvc0` and `serial-getty@hvc0` are absent. Temporary
pseudo-NMI, CSD, last-activity, ECC and BBM diagnostics were removed from the
production build. There is no pending test249 flash or diagnostic rollback.
See `reference/boot-tests/test-249-no-dcc-production/RESULTS.md` and
`BUILD_RESULTS.md` for exact identities, hashes and validation limits.

Test247 captured a natural CPU4 stall in `hvc_dcc0_put_chars`: the DCC TX-busy
poll was unbounded while `hvc_write` held an IRQ-saving spinlock. Test248
validated the DCC-disabled diagnostic candidate, and test249 validated the
production transition on two boot paths. This supports repair of that concrete
DCC failure path; it does not prove that every earlier CPU stall shared the
same cause or rule out future stalls. Keep the accepted production images and
modules paired. Preserve the original230 and passing248 rollback pairs until a
separate, verified retention decision. A recurrence needs fresh boot-attributed
evidence before a new causal claim. See
`reference/boot-tests/test-247-early-csd-pnmi/RESULTS.md`,
`reference/boot-tests/test-248-no-dcc/RESULTS.md` and the test249 result above.

Native USB ADB and NCM/SSH are present in the production profile. A prior
Windows Code43 descriptor failure and a separate transient warm-boot NCM TCP
failure remain unresolved; test249 records both without attributing a cause.
The Debian login-screen `aux_bridge` deferred probe is a separate missing
PS5169/DisplayPort bridge-provider issue, not evidence of the DCC CPU fault.
See `reference/boot-tests/test-249-no-dcc-production/usb-incident/RESULTS.md`
and `docs/AUX_BRIDGE_LOGIN_MESSAGE.md` before changing USB or display wiring.

Historical D-drive test files live in ignored
`.work/d-drive-test-archive/2026-09-28/`, with tracked hashes in
`reference/d-drive-test-archive-20260928/SHA256SUMS`. Windows retains only the
rescue/rollback artifacts below `D:\android\gts9-active\`;
`gts9-stock/`, `gts9-test230/`, `gts9-test248/` and `gts9-test249/` are beneath
it. The owner subsequently explicitly requested that ADB tools remain directly
below `D:\android\platform-tools\` (2026-09-28). Current scripts therefore
use `/mnt/d/android/platform-tools/adb.exe`; this overrides the earlier tools
location under gts9-active without relocating test/rollback artifacts. Old absolute
paths in immutable test records describe where files were at test time. See
`reference/d-drive-test-archive-20260928/README.md`.

The test249 registration README and earlier dated reviews are historical plans;
its `RESULTS.md` is the final device-state record. Keep new physical tests
bounded, attributable and separately logged. Use the changed-file host test
selection for local iteration and the full retained suite when changing test
routing or reviewing a final candidate; see `docs/HOST_TEST_WORKFLOW.md`.

Test250 registered 20 unchanged-production warm reboots but stopped during
read-only preflight, before issuing any reboot (0/20 rounds). Test249 config,
notes, five partitions and all 181 modules still match and DCC remains absent.
The conservative parser flagged early warning/SMMU parameter variants; the
same SMMU fault class already exists in both accepted Test249 production boots,
so this is not proof of a new CPU stall. Supplemental same-boot transport
capture independently found two Windows NCM TCP timeouts followed by automatic
recovery, with ADB and authenticated SSH available and no Code43. Do not treat
the current boot as a clean Test250 round or retry automatically. Keep production
unchanged and review `reference/boot-tests/test-250-production-warm-reboot/RESULTS.md`
and its raw evidence before another hardware test. Test251 was not created.

The owner subsequently explicitly requested physical testing again. Test250
attempt 02 is separately registered in
`reference/boot-tests/test-250-production-warm-reboot/attempt-02/README.md`.
Use `--attempt 2` to preserve the stopped original records. Its host-only
parser recognizes tightly bounded startup classes from both manifest-verified
Test249 accepted production captures; it does not change the device or accept
USB transients as clean. The same 20-round/150-second, exact-production and
stop-on-first-non-clean requirements apply. Check attempt-02 results before
any further test; an explicit restart request is not permission to ignore a
new non-clean condition.

Attempt 02 subsequently passed full unchanged-production preflight and issued
one ordinary warm reboot, from `b08bbc9b-3bbf-417e-9935-619fcc5d7222` to
`188fd5c9-14ca-4818-9ded-e96669a9c836`. Round 01 stopped as suspect at the
20.11 s observation poll because ten early SMMU IOVAs exceeded its registered
range; no second reboot was issued and no 150 s window completed. Captured
journals show no CPU-stall/panic signature. Full post-stop read-only identity
still matches Test249, with DCC absent and no failed unit; an independent
same-boot NCM TCP transient recovered on its third attempt. Do not call this
round clean or broaden the gate after the stop. See attempt-02 `RESULTS.md`
and `summary.json` before further hardware work. Production remains unchanged.

The owner then explicitly requested completion of the full regression.
Test250 attempt 03 is separately registered under its `attempt-03/README.md`.
Read-only post-attempt02 analysis proves the production splash carveout is
43 MiB (`0xb8000000`–`0xbab00000`), larger than attempt 02's sampled 2 MiB gate;
attempt 03 derives the bound from the hash-verified accepted Test249 DTB and
checks the live property without changing it. It also records source-bound
Windows NCM socket endpoints; earlier TCP timeout causes remain unproven.
Only use `--attempt 3` after its pushed registration and accepted preflight.
All original 20/150-second exact-production and first-non-clean stop conditions
remain in force. Prior stopped attempts remain stopped, not clean or resumed.

Attempt 03 passed pushed exact-production preflight and issued one ordinary
warm reboot from `188fd5c9-14ca-4818-9ded-e96669a9c836` to
`830da717-5e6d-40be-8390-7398b55ff2e2`. It stopped as suspect at the 21.30 s
health poll on `Bluetooth: hci0: unexpected event for opcode 0xfc48`; no second
reboot was issued and no 150 s registered window completed. Exact Test249
config/notes/five partitions/all 181 modules and DCC absence remain verified.
ADB, source-bound NCM and authenticated SSH passed post-stop; Bluetooth setup
completed and the same boot remained responsive. No CPU-stall/panic signature
was detected. The HCI event mismatch remains unclassified, despite similar
historical Test241/Test247 logs; do not silently exempt it or call the round
clean. Keep the series stopped and production unchanged, read attempt-03
`RESULTS.md` and `round-01/offline-analysis/`, and do not create Test251.

A subsequent read-only source review identified `0xfc48` as the QCA UART
baudrate command encoded as `0x48, 0xFC`. A primary Qualcomm patch discussion
covers the same WCN6855 response-handling issue; this boot completed UART setup
0.808107 s after its event. This improves the explanation but does not prove
packet ordering or amend the stopped verdict. See Test250
`post-attempt03-analysis/README.md` for source evidence and an unapproved,
precisely bounded host-only classification proposal. Keep physical testing
stopped until the owner explicitly resolves that classification; production
and the current runner stay unchanged.

The owner subsequently explicitly adopted the bounded QCA classification
proposal (reply: "采用"). Test250 attempt 04 is a fresh registration under
`attempt-04/README.md` and `policy.json`, using `--attempt 4`. Its host parser
counts only the one exact early hci0/0xfc48 priority-3 event with WCN6855 setup
completed within 5 s, plus same-boot powered-controller/active-unit health.
The full 20-round/150-second Test249 identity, attribution, CPU/USB/evidence and
first-non-clean gates remain. Push registration/tests, then accepted full
preflight, before reboot. Previous attempts remain stopped and sealed; their
old plans do not authorize resumption. Production is not modified. Check
attempt-04 RESULTS/summary if present before starting any work on the device.

Attempt 04 subsequently passed full read-only preflight on boot
`830da717-5e6d-40be-8390-7398b55ff2e2`: exact Test249 config/notes, five partition
hashes, all 181 module hashes, DCC and backup absence, unchanged live splash
property, no failed unit and no CPU signature. Bluetooth is healthy and the
single early QCA event satisfies the owner-approved bounds. ADB and bound
NCM/authenticated SSH passed on their first attempts with no Code43. See its
`preflight/summary.json`; commit/push this accepted evidence before `run --attempt 4`.

Attempt 04 then issued five ordinary warm reboots. Rounds 01–04 were clean
through 153.71, 153.98, 154.04 and 153.51 s. Round 05, new boot
`457ecc1a-5d90-4d6f-8c5f-ad67e069bef3`, stopped as suspect at the 21.37 s poll
because two exact early `hci0/0xfc48` messages exceeded the approved maximum
of one per boot. Each belonged to a separate completed WCN6855 setup cycle;
this does not exempt the repeated count or prove a CPU fault. No sixth reboot
or final 20-round acceptance occurred. Full post-stop read-only config/notes,
five partitions and 181 modules still match Test249, DCC remains absent, and
Bluetooth/ADB/bound NCM/authenticated SSH are healthy. No CPU-stall/panic
signature was detected in the captured journals. See attempt-04 `RESULTS.md`,
`summary.json`, `EVIDENCE_AUDIT.json` and `round-05/post-stop/`. Keep the series
stopped and production unchanged; the 20-round goal is incomplete. Do not
silently broaden the QCA count, resume/reclassify this attempt or create Test251.
Further hardware work requires the owner to resolve this new non-clean bound.
Its post-stop `setup-cycle-review.json` compares eight raw journals and the
system timeline; `classification-proposal.json` proposes at most two events,
one per distinct completed cycle, at most three early cycles. That proposal
is unapproved and unimplemented; it does not authorize another reboot.

The owner subsequently explicitly adopted that bounded cycle proposal and
requested a fresh 20-round registration. Test250 attempt 05 lives under
`attempt-05/README.md` and `policy.json`; use only `--attempt 5` for this fresh
series. Its host-only rule permits at most two exact early priority-3 hci0
events, one per distinct completed WCN6855 cycle, at most three cycles, all
setup/event/completion times within 20 s and each event completed within 5 s.
Same-boot powered-controller and active-unit checks plus all original Test249
identity, CPU/USB/evidence/20-round/150-second/first-non-clean gates remain.
Earlier stopped attempts and seals remain unchanged. Push passing tests and
registration, then full accepted read-only preflight, before any reboot.
Production remains untouched; check attempt-05 results before further work.

Attempt 05 passed full read-only preflight on the still-current
`457ecc1a-5d90-4d6f-8c5f-ad67e069bef3` boot: exact Test249 config/notes, all five
partition hashes and 181 module hashes, DCC/backup absence, unchanged live
splash and runtime profile. The two earlier QCA events belong to separate
completed cycles and satisfy this newly approved policy; attempt 04's verdict
remains suspect. Bluetooth is powered with both units active, no failed unit or
CPU signature; ADB, bound NCM and authenticated SSH passed immediately, without
Code43. Push its sealed accepted preflight before `run --attempt 5`.

Attempt 05 issued twelve ordinary warm reboots and recorded twelve CLEAN
new boots, each observed beyond 150 s with exact attribution and no detected
CPU fault. Round 13 stopped during source preflight before any reboot: the
first Windows source-bound NCM SSH-banner PowerShell command timed out at its
20 s host deadline and the runner ended before bounded retries. Later
read-only probes on the same boot succeeded, but cannot classify the first
timeout's internal stage or make the source gate clean. Full post-stop
Test249 production identity (five partitions, 181 modules, config/notes,
DCC absence) still matches, and no CPU-stall/panic signature was detected.
See attempt-05 `RESULTS.md`, `summary.json`, `EVIDENCE_AUDIT.json` and
`round-13/post-stop/`. No thirteenth reboot, final 20-round acceptance or
Test251 occurred. The Test250 goal remains incomplete; keep this attempt
stopped and production unchanged. Any further physical series requires a
fresh registration and owner decision about this host probe timeout.
The post-attempt05 read-only review compares 29 successful host probes
(2.104–2.520 s, median 2.179 s) with the 20.025 s timeout and records an
unapproved attempt-06 proposal in `post-attempt05-analysis/README.md`.
It would add stage timestamps and allow 30 s for the outer Windows process
while keeping the 5 s TCP-connect/banner-read deadlines and every other
stop gate. It has not changed the runner or authorized a new hardware test.

The owner then explicitly changed the future Test250 completion criterion to
continue from round 13 and count the bounded warm-reboot series complete if
the prior CPU hang does not recur. A separately registered CPU-focused
continuation under `continuation-cpu-13-20/` kept attempt 05's original
stopped verdict intact. Eight more ordinary Test249-production warm reboots,
rounds 13–20, were uniquely attributed and each observed to at least 150 s;
no CPU-stall/panic signature was detected. Together with attempt 05's twelve
strictly CLEAN rounds, this completes **20 attributed CPU-focused warm-reboot
observations**, not 20 CLEAN rounds under the superseded strict transport gate.
Full final five-partition/181-module/config/notes/DCC and transport acceptance
passed; offline evidence replay passed. See continuation `RESULTS.md`,
`summary.json` and `EVIDENCE_AUDIT.json`. Production remained unchanged.
The earlier Windows probe timeout is unresolved. No Test251 was created or
run; cold/battery-only/Type-C power paths remain untested.

Stage0 X710 battery/charging audit is recorded in
`docs/X710_BATTERY_CHARGING_PORT_PLAN.md`. Stage1 is a **host-built, unflashed
SM5714 candidate**, independently registered under
`reference/boot-tests/test-252-sm5714-stage1/`. It adds the battery/ordinary
switching-charger driver and mandatory PMK8550 ADC5 Gen3 pack-thermistor
provider; the exact resolved delta is BATTERY_SM5714 absent -> y and
QCOM_SPMI_ADC5_GEN3 n -> y. The DTB, DCC-off CPU profile, cmdline, rootfs and
USB gadget remain unchanged. Source comparison is pinned to the same-model
`ab123e7d1dbc0cbcd35661f9761197e977b15aa9`; 8400mAh is typical capacity,
8160mAh is rated minimum and remains the design metadata. Read its
BUILD_RESULTS/SAFETY_REVIEW/ARTIFACTS before later deployment. No candidate
boot/probe/charge or new physical acceptance is claimed. Do not flash without
a new explicit owner request and fresh baseline preflight. Stage2 TCPM and
Stage3 SM5440 are not implemented and require the earlier stages' physical
acceptance. Installed production remains Test249 as accepted by Test250.

The owner subsequently requested Test252 physical testing ("开始测试吧").
Attempt01 is registered under `test-252-sm5714-stage1/attempt-01/README.md`.
Full read-only Test249 preflight and offline module install/restore rehearsal
passed. The candidate boot and paired181 modules are now installed, and boot
`fcb9a367-fa8e-43df-afb1-08db722ff2f1` has exact candidate notes/config/modules,
five-partition identity, DCC absence, both supplies and working ADB/NCM/Wi-Fi
SSH. Only boot changed; the other four partitions match accepted Test249.
Initial computer SDP input is limited500mA and does not overcome system load;
Charging labels alone are not charging acceptance. Battery-only151.021s passed
and ordinary Lenovo YG65G USB-C2 charging passed1201.035s/121 samples: SOC92 ->97,
actual pack current+432..1381mA, temperature30.6..31.2C, voltage4.330..4.418V.
No CPU/kernel/charge fault occurred. Plug-out passed151.127s, returning to
online0/Discharging with negative actual current. Final USB gate stopped on persistent ADB offline after reconnect, although
Windows enumerates both interfaces and source-bound NCM/Wi-Fi SSH work without
Code43. Post-stop exact candidate config/notes/five partitions/181 files and181
original files remain verified, DCC absent and no CPU/kernel fault or failed unit.
Stage1 full acceptance is incomplete. Preserve this stopped attempt/USB evidence;
no daemon restart, gadget reset, further experiment, rollback or cleanup was made.
Candidate remains installed for offline USB analysis, not promoted to production.
The on-device `.gts9-test252-original` contains all181 verified Test249 files;
external Test249 boot/module rollback is retained. Do not remove it or start
Stage2/3 before the results and retention decision. The original prepared-only
statements above describe the earlier phase, not the currently installed boot.
Check attempt01 RESULTS/summary before the next hardware action. ADB tools use
the owner's later `/mnt/d/android/platform-tools/adb.exe` location. One old GPU
firmware-file-not-found error was recorded separately during preflight; no GPU
or firmware change was made, and no CPU fault was observed in that evidence.

## Mission

Maintain a mainline-first Linux port for Samsung Galaxy Tab S9 Wi-Fi (`SM-X710`, Android codename `gts9wifi`) on Qualcomm SM8550 (`kalama`). Prefer upstream Linux interfaces and bindings. Samsung's downstream 5.15.153 sources/config/device tree are evidence about hardware, not the target architecture.

## Ground truth and pins

- Device: SM-X710 / gts9wifi, Wi-Fi model.
- SoC: SM8550 / Snapdragon 8 Gen 2; GPU Adreno 740.
- Samsung ABL selector values observed in the supplied live DTS:
  - `compatible = "qcom,kalama-mtp", "qcom,kalama", "qcom,mtp"`
  - `qcom,board-id = <0x10008 0x04>`
  - `qcom,msm-id = <0x218 0x20000 0x207 0x20000 0x207 0x10000 0x218 0x10000>`
- Stock config evidence: Linux 5.15.153, Android clang 14.0.7.
- Mainline build pin: Linux `v7.2-rc3`, commit `a13c140cc289c0b7b3770bce5b3ad42ab35074aa`.
- Bootstrap board DTS reference: `troikoss/gts9wifi-fedora` commit `656d2ded8031657b60cde22e6fdfbc0b722a9dff`.
- Earlier X710 bring-up reference: `Azkali/sm8550-mainline` branch `gts9wifi-7.0`, inspected at `c48fedbd799a2b792a095840eeb96746afe2f327`. See `docs/AZKALI_SM8550_MAINLINE_ANALYSIS.md` and `kernel/PROVENANCE.md`.

Do not silently change either pin. A kernel bump and a hardware-port change must be separate changes so regressions remain attributable.

## Stock evidence supplied by the owner

The owner supplied a live DTB, a decompiled live DTS and a full stock `.config`. Their SHA-256 values and extracted hardware facts are recorded in `reference/stock/MANIFEST.md`.

Important device-specific differences from the S9 Ultra/X910:

- SM-X710 panel: `GTS9_ANA38407_AMSA10FA01`.
- Touch: STM FTS1BA90A, not the X910 Goodix GT9916.
- Pen: Wacom W90xx / WEZ01 family on I2C.
- WLAN/BT: QCA6490/WCN6855-class, not X910 WCN7850/Kiwi v2.
- Power: SM5714 charger/fuel gauge/USB-PD plus SM5440 direct charger.
- Type-C redriver: Parade PS5169; eUSB2 repeater: NXP PTN3222.
- Audio: four CS35L45 speaker amplifiers are visible in the stock DTS.

Never copy the entire downstream DTS into `arch/arm64/boot/dts/qcom/` and call that a mainline port. Translate only evidenced hardware into upstream bindings and keep unsupported vendor-only properties out.

## Repository invariants

1. `scripts/fetch-mainline.sh` must verify the exact upstream commit.
2. The upstream checkout under `.work/linux-mainline` stays pristine.
3. Device changes are staged into a disposable worktree under `.work/build/`.
4. Kernel build output goes to `.work/build/linux-out` and `out/kernel-gts9wifi`; never commit it.
5. Use `USE_CCACHE=1 ARCH=arm64 LLVM=1`; ccache is required for builds. Do not introduce a GCC-only build path unless there is a demonstrated need.
6. Keep critical early-boot/storage/console providers built in when the port depends on them before the root filesystem is available.
7. The owner-extracted stock config is immutable evidence: reconstruct it with `scripts/materialize-stock-config.sh`, verify its recorded SHA-256, then use it as the Kconfig seed. A symbol requested by the mainline fragment but dropped by `olddefconfig` must be treated as a build/config issue, not ignored.
8. Kernel image, DTB, config and release string must be hashed in every build.
9. No build script may flash or repartition a physical device.
10. Do not claim hardware works because a driver compiles or probes. Record `compiled`, `booted`, `enumerated`, and `physically verified` as different states.

## Remote workflow (owner instruction, 2026-09-21)

- `main` is left alone unless the owner explicitly asks for it. Work happens on a
  branch (currently `test`) and is pushed there.
- One purpose per commit; do not batch unrelated work into one commit.
- **Push to `origin` after every operation.** Verified work must not exist only on
  the local disk: commit it and push the branch, so the remote always matches what
  was actually built, tested or documented.
- If an operation changes nothing in the tree (a read-only check, for example),
  there is nothing to push; do not create an empty commit.
- GitHub Actions is **manual-only** (`workflow_dispatch`). A normal push must not
  start a kernel build or packaging job.
- Routine development is validated **locally**. After pushing a commit, do not wait
  for, poll, or require GitHub Actions before continuing.
- Run the GitHub Actions workflow only when the owner explicitly requests a remote
  CI check. A local successful build/validation is sufficient evidence for
  `compiled` / `packaged` status; it is still not evidence of a physical boot.

## Historical bring-up findings and physical-test workflow (owner instruction, 2026-09-21)

The milestones below describe their individual test dates. The current
production state is recorded at the top of this file and in test249 results.

- **Milestone reached (test 010, `reference/boot-tests/test-010-.../`): the
  owner watched the tablet power itself off while running this port's kernel.**
  `ABL -> mainline Linux -> BusyBox /init` is therefore established on hardware.
  A hung kernel cannot power a tablet off and `panic=0` removes the only way it
  could fake it. Everything below applies to work *beyond* that chain.
- The "stuck on the Samsung logo" state is a **running initramfs** waiting on a
  console that does not exist (no panel driver, unreachable UART, and a
  `console=null` the bootloader appends). Do not read it as a kernel failure.
- **Do not use the sec_log ring as evidence.** Test 007 measured the
  bootloader's own log spanning 2,096,187 of the 2,097,136 bytes of
  `sec_log_buf`, so mainline writes are overwritten before recovery can read
  them. An empty ring proves nothing. Live channels (USB, once it probes) or
  physical observation are the evidence paths.
- **Storage is up** (test 020): the missing provider was `CONFIG_QCOM_PDC`, the
  interrupt controller the SPMI arbiter hangs off.  With it the microSD (`mmc1`)
  and UFS (`sda`..`sdf`) both enumerate, the PMIC GPIO card detect works, and the
  bring-up report reaches the card - see tests 020 and 028.
- **The evidence loop is closed** (test 028): `/init` writes the report to the
  microSD card, waits ten seconds and resets into TWRP through the Android
  bootloader control block, so a test costs about half a minute and needs no
  hand-carried recovery boot.  `scripts/read-bringup-report.sh` reads the card.
- **The display pipeline is up** (test 035): the ported ANA38407 panel driver
  probes, `card0`/`card0-DSI-1` exist, the connector reports `connected`,
  `2560x1600` appears twice (the panel's 120 Hz and 60 Hz mode sets) and
  `/proc/fb` is `msm-kmsdrmfb`, so fbcon finally has a real surface.  Two things
  had to be true at once: `msm.separate_gpu_kms=1` (the Adreno is a component of
  the msm DRM master and fails without GPU firmware, which fails the card), and
  that parameter must sit near the *front* of our cmdline - the bootloader appends
  kilobytes of its own and was dropping the last token of ours.
- **Display status update (offline audit, 2026-09-22):** test 038's fb blank
  cycle recovered panel ID `80 00 04`, but CTL/vblank timeouts and partial
  pixels remain. Test 039's no-DSC modes exceed the DSI OPP limit and provide
  no decoding verdict. DSC/120 Hz is the default again; premature kickoff
  patch 0005 is held in pending because normal MSM kickoff follows modeset
  enable and DSC preparation. See `docs/DISPLAY_OFFLINE_AUDIT.md`.
- **Official-source candidate v1 (2026-09-22):** the owner supplied the full
  X710 source archive, including vendor display commands. The panel now uses
  X710 slew/PM_EN/TSP-sync/120HS programming, exposes only DSC/120 Hz and uses
  236 x 148 mm dimensions. Stock PPS matches the pinned helpers byte-for-byte
  over its 88 supplied bytes. Kernel, six host tests and an isolated boot
  bundle validate locally. See `docs/DISPLAY_X710_OFFICIAL_V1.md`.
- **The panel displays (test 040, `reference/boot-tests/test-040-.../`):** the
  official candidate was flashed to `boot` only and it works. The owner saw the
  boot command line on the panel, then a green/black marker, then three lines
  written two seconds apart appearing live - so the console both decodes and
  updates. `ctl start` failures are zero, where tests 037-039 never completed a
  command-mode start. What fixed it was the DDIC's own power-on and refresh-mode
  programming (`0x60`/`DD 0x13`/`B9 0x10 = 80 00 00 00` for 120HS), not DSC and
  not the DPU. The panel still cold-boots dark and is still recovered by the
  framebuffer blank cycle, now in 8 s. Unvalidated: the brightness/gamma/ACL
  stack, 60 Hz, other panel revisions, and long-run stability.
- **Pogo keyboard: input driver registered, application startup unresolved (test 045,
  `reference/boot-tests/test-045-.../`).** The driver
  (`kernel/drivers/keyboard-samsung-pogo.c`, `0006-input-add-samsung-pogo-keyboard.patch`)
  binds on hardware, registers `Book Cover Keyboard Slim (EF-DX710)` as event0,
  powers the rail, pulses the MCU's reset and reads its version actively, which is
  how Samsung's own driver proves presence. Five real faults were found and fixed
  along the way: the connect line is an edge not a presence level, cycling the
  rail on every edge reset the STM32 before it could answer, the diagnostic
  flooded the panel console, the handshake was passive, and the SWD pins were not
  owned by the driver.
  At that stage every application read returned `-ENXIO` (a NACK:
  the transfer ran, the bus was idle, nothing acknowledged) and a quick-write scan
  of the whole adapter finds **no device at any address**, while TWRP's stock
  kernel enumerates the same cover minutes earlier as `EF-DX710_v1.4.1.0`,
  `con:1/1`, `model_id 0x2`. The controller, pins (`qup2_se7` on gpio72/106),
  address, IRQ type, reset and rail model all match the vendor node. Two
  candidates were fitted and did not help: patch 0007
  (`samsung,reset-before-trans`, now in `pending/`) and an explicit rail
  power-cycle; both are retired with that result recorded.
  Round 2 compared the stock and mainline regulator tables: the pogo rail is
  enabled in **both** (`fixed_regulator${#}` / `pogo-vdd`, use=1, each with its
  client as consumer), no relevant rail differs, and the rail's source is not
  modelled as a parent in either tree.  It also established that gpiolib refuses
  to hand out gpio72/106 while they are multiplexed to `qup2_se7` (-EINVAL) and
  that `of_get_named_gpio()` no longer exists, which is why the vendor reads those
  lines with `gpio_get_value()` on numbers it never claims.
  Round 3 read the tree TWRP is built from: it uses a **prebuilt stock kernel**
  plus stock `dtb.img`/`dtbo.img` and Samsung's module stack, so its working
  environment is not reproducible in mainline.  Two facts came out of it.  Stock's
  log shows `rst:0`, so the MCU answered first try and was *already running* when
  the stock driver probed - nothing in that driver powers it from cold.  And
  `stm32_pogo_v3_start()` begins by instantiating a second I2C client at
  **`boot_addr = 0x51`**, the STM32's **system bootloader** interface, then runs
  `stm32_dev_firmware_update_menu(stm32, 0)`; the application interface at 0x2a is
  used only after that, and `client->addr != 0x51` guards the driver's power-reset
  and connect-state paths.
  Round 4 implemented that handshake and it answered: `MCU bootloader took the
  0xFF sync`, then `MCU bootloader version 0x12`.  **The MCU is powered and
  executing** - rail, bus, pins and address are all correct, and the whole
  power/supply line of investigation is closed.  What does not happen is the
  *application*: after the vendor's `sysboot_disconnect()` sequence the bootloader
  goes quiet and 0x2a never answers, which is what a boot-mode selection problem
  looks like.
  Round 5 tried both app-entry mechanisms on hardware and both failed: the
  vendor's exact `stm32_sysboot_disconnect()` timings leave 0x2a NAKing, and the
  bootloader's `GO` (0x21) write then times out because by that point the MCU
  answers on neither interface.  It has left the bootloader without the
  application coming up on i2c.
  Round 6 disproved the read-first hypothesis: with no rail cycle, no reset and no
  bootloader dance the application does not answer either, so the MCU genuinely
  sits in its system bootloader and goes quiet on both interfaces after any
  app-entry attempt.  It also established that the gpio12/13 sharing with the DMIC
  is genuine hardware sharing present in the vendor tree as well
  (`dmic45_clk_active`/`dmic45_data_active`, `function = "func1"`), and inactive
  here - the pinmux still shows those pins owned by `5-002a` minutes in.
  Round 7 offline audit (2026-09-22): commit `776b7d4` sends GO while the
  bootloader session is live, but leaves Get Version's final ACK unread. Samsung's
  `stm32_sysboot_i2c_get_info()` and ST AN4221 both require ACK/version/ACK.
  The caller also unconditionally resets after app entry, and the read-first
  success path skips mode checking, leaving `ready` false. These are driver
  defects; the earlier assertion that the remaining issue lies outside the driver
  was not established. The new candidate consumes the full version response,
  restarts a failed version session before GO, preserves successful application
  startup and checks mode on both success paths. Bus recovery now runs only after
  an application read fails. See `docs/POGO_STARTUP_REPAIR.md` for validation.
  Test 046 (`reference/boot-tests/test-046-20260922T055740Z/`) booted that
  candidate and returned safely to TWRP. The owner saw the console, but version
  exchange timed out (-110), GO was refused, and the application still NAKed
  after reset. The version error did not identify a transfer stage. Stock's
  `stm32_sysboot_connect()` then revealed a missing STEP3: after probing with
  unknown command 0xFF it resets into the bootloader again, without another
  probe, before issuing commands. The follow-up candidate now mirrors that
  sequence, tested against the actual GPIO/reset helper on the host.
  Test 047 (`reference/boot-tests/test-047-20260922T060344Z/`) validates that
  correction: the full version exchange returns 0x12 and both GO command/address
  ACKs succeed. Application 0x2a still NAKs after 150 ms; the fallback resets it
  and 40 further retries fail. The owner confirmed the keyboard stayed attached
  and unfolded. Pretest TWRP identifies EF-DX710, firmware 34, con:1/1, rst:0.
  Both tests returned safely to TWRP; 1d8a977 remains installed with read-back
  hashes verified. No key has been typed through mainline yet.
- **The acknowledged GO was the wrong command (2026-09-22, round 6).**  Tests 048
  and 049 settled it: no reset timing and no polling window makes the application
  answer after `GO 0x08000000`, and the READ path (now working, framed exactly like
  `stm32_sysboot_i2c_read`) shows `0x08000000` holds a Cortex-M vector table
  (SP `0x200056c0`, reset vector `0x0800c4a5`), not Samsung's `"STM32"` header -
  that header sits at offset `0xbc`/`0xc0` *inside* the image. After the GO the MCU
  answered on neither `0x2a` nor `0x51`. The vendor's own bring-up, run on every
  stock boot, never sends GO: `stm32_sysboot_mcu_validation()` enters the system
  bootloader, `stm32_sysboot_i2c_read()` takes the IC version from `0x08000200`
  (stock prints its last byte as `mcu_fw(ic):34`) and `stm32_sysboot_disconnect()`
  - BOOT0 low, one NRST pulse, 150 ms - releases the part so the application runs
  from flash. The port now does exactly that, plus stock's
  `stm32_set_mode(MODE_APP)`: a part reporting DFU mode gets the ABORT command
  (`0x17`) before it is read again. Test 050 measures it.
- **The host harness is not a compile test (2026-09-22).**  `tests/test_pogo_startup.py`
  strips forward declarations (`re.sub(r'^static [^\n]+;\n', ...)`) and mocks the
  helpers it does not extract, so it passed while the driver still called
  `pogo_recover_bus()` and `pogo_scan_bus()` after their definitions had been
  deleted. Always run `scripts/build-kernel.sh` before flashing, and treat the
  kernel build - not the harness - as the gate.
- **Display regression, found and fixed (2026-09-22, round 5).**  The owner
  reported a blank screen; `display_recover` was cycling the framebuffer as soon as
  `fb0` appeared, 5.91 s, before the panel driver's first read at 6.29 s, and had
  no retry - so test 040's working display stayed dark.  It now waits for the
  driver's own line and retries the full cycle up to three times; cycle 1 recovers
  `80 00 04` at 6.5 s and the owner confirms the console is visible again.
- **Physical tests need a recorded owner request (2026-09-22).** The test 040
  flash was made on one and tests 041-045 continued under the same recorded
  authorization, which each test's `source.txt` quotes. Do not flash, reboot or
  claim a hardware observation without a current request; ccache builds are
  always authorized. Compilation is not screen or keyboard validation.
- The microSD Debian rootfs, USB ADB/NCM/SSH and panel login were established
  after these early bring-up tests. Use current evidence before declaring a
  touchscreen, keyboard or other feature physically verified.
- **The USB rescue channel works** (test 029): with `gts9_usb_gadget=msc` the
  gadget exports the microSD partition read-only, Windows mounts it by itself,
  and the report can be read off the running tablet over USB - no TWRP, no power
  button, no owner.  Bulk transfers are therefore fine; the CDC-ACM function is
  what fails (the host sees its control interface and never its data interface),
  so a serial console is a gadget-side fix rather than a PHY problem.
- Known blockers on the way: an SPMI *write* blocks this kernel uninterruptibly,
  so `reboot recovery` through the SDAM and the RTC state word are both out until
  it is understood - the BCB path (a UFS write) replaces the former.  Nothing on
  this device clears that BCB afterwards (TWRP's cmdline still said
  `androidboot.boot_recovery=1` after a `gts9-to-recovery` boot), so `/init` now
  clears a stale block on every mainline boot: one request, one boot.  Reaching
  mainline at all means the request was served, so this is safe by construction.
- USB re-enumeration is marginal: the gadget comes up on most boots, but test 035
  lost it after a DSI host rebind under a live DRM master, and Windows then
  reported a failed device-descriptor request (code 43).  Do not rebind the DSI
  host while DRM holds it; a real suspend/resume is the documented recovery for
  the panel's cold-boot state.
- The generic initramfs lives in **init_boot**, so include init_boot whenever the
  new bundle differs from the flashed version. `gts9_userspace_proof=<seconds>`
  stays an opt-in in the initramfs (it powers the tablet off by itself) and is
  deliberately absent from `boot/cmdline.example.txt`; re-add it to reproduce
  test 010.
- Early candidate flashes were authorized and recorded per test. For later
  hardware work, follow the owner's authorization in the current session and
  the specific test registration. Validate the bundle, device identity,
  partition sizes, backups and per-partition write/read-back hashes before
  writing. Build and validation scripts must remain non-flashing. Do not rewrite
  recovery, vbmeta, bootloaders, userdata or the partition table as part of a
  boot-image test.
- Start log capture before reboot and use the test's registered observation
  window and stop conditions. If ADB is absent, correlate device-side and
  Windows-side evidence and ask for a physical observation only when needed;
  absence of ADB alone does not establish a crash.
- **Every subsequent physical test must have a committed log directory** under
  `reference/boot-tests/test-NNN-*/`, including failed or aborted
  attempts. Save raw last_kmsg, available pstore, recovery dmesg (labelled as
  recovery), device/layout checks, flash/read-back transcript, artifact hashes,
  source commit, bundle metadata and an observation/result README. Mark absent
  logs explicitly; never fabricate a successful capture or overwrite an older
  test directory. A directory containing only a summary is insufficient when
  raw logs are available. Do not commit firmware images or partition backups.
- Hash the archived evidence and commit/push it to `origin/test` after each
  test, before changing the next kernel/config/DTB. `.work` or external folders
  are staging locations, not the sole home of test evidence. The capture tool
  defaults to the tracked archive; pass CAPTURE_DIR for the specific test.
- Mainline log/marker present: follow the last proven stage and the actual
  panic/probe output. Init reached: verify persistence, then storage and USB
  rescue. Reboots without mainline evidence require independent kernel-handoff
  and retention checks; the measured `sec_log` ring is not a reliable Linux log.
  An absent write-back marker, empty pstore or a compressed-file DTB offset does
  not prove that Linux was never entered.
- Keep experiments attributable: change one failure hypothesis per follow-up
  test. MMU-off/head.S or Gunyah watchdog instrumentation remains a separate
  diagnostic branch, not a default workaround. Record the final device state
  and any stock restoration with read-back hashes in the test record.

## Pogo audit (2026-09-22; historical candidate after f6c5c6b)

That candidate restored DATA to IRQ_TYPE_LEVEL_LOW: announce-gpios is
GPIO_ACTIVE_LOW, so descriptor 1 means a physical low, not a high pulse. The
normal startup now releases the protocol mutex before enabling DATA, with only
50 ms power settling and no bootloader/scan/rail cycle. A model event makes a
single version-read attempt, not a minute-long loop under that same mutex.
Previous local startup experiments remain opt-in through
`keyboard_samsung_pogo.startup_diagnostics=1`; do not enable this for normal
keyboard validation. See `docs/POGO_EVENT_STARTUP.md` for the pinned S9U source
comparison and limits. The S9U firmware-update result is not permission or proof
that X710 needs another MCU image. Host tests pass; record physical results
separately and keep pre-existing test-087 logs distinct from new tests.

## Build commands

### Change-scoped validation (owner instruction, 2026-09-30)

- Kernel/driver/config/DTS or build integration changes: build once after the
  implementation is ready; validate resolved config, DT, protected files and
  paired artifacts. Run affected host tests during development and one full
  regression for final candidate review. Do not run wrapper/changed/all in
  succession when they select the same tests.
- Host runner/parser changes: run affected tests and syntax checks. Rebuild only
  if those changes also affect kernel inputs or packaging. Routing changes still
  require one full host regression; never delete or weaken tests to save time.
- Documentation/status/results changes: review the diff; check newly recorded
  evidence hashes and summary consistency as appropriate. No kernel rebuild or
  full host regression. Record `executed: false` for tests not run and reference
  the existing qualification separately. Changed-mode's conservative fallback
  is not a requirement to run all tests for a reviewed prose-only commit.
- Reuse qualification only while relevant source, profile, upstream pin,
  toolchain, build inputs and artifact hashes are unchanged. New source/input,
  artifact mismatch, failed validation or a relevant unresolved concern
  invalidates the affected qualification; commit SHA alone does not.
- Device testing: one full baseline check before deployment; verify staged
  files and written partitions/modules at the write boundary. Check current
  boot/config/notes, rescue transports and battery safety after boot. During a
  same-candidate observation, collect boot ID, telemetry, transport and new
  faults together; do not repeatedly hash every partition and rollback module
  directory or fetch an unchanged full journal for every sample. Save full
  journal at observation boundaries and on first anomaly. A new reboot or
  unexplained identity change requires fresh applicable checks. Keep registered
  observation windows, stop conditions and rollback; reduce duplicate checks,
  not safety limits or evidence needed to attribute a failure.

Host regression uses `bash scripts/check-stall-offline.sh` (changed files by default).
Use `--changed --base REV` for committed changes, `--core` for unconditional core
regression, or `--full` for all tests. A clean worktree against HEAD runs no tests;
it does not establish a regression pass. Unknown dependencies select all tests.
See `docs/HOST_TEST_WORKFLOW.md` for artifact/archive triggers and exact suite
selection. `--full` remains exhaustive; run it after changing suite routing or
retiring tests. New tests default to core. Do not interpret skipped prerequisites
as successful artifact validation; use `--fail-on-skip` on the Python runner when
complete validation is required. These commands do not contact the device.

Normal build:

```bash
./scripts/fetch-mainline.sh
./scripts/build-kernel.sh
```

Clean source-level comparison:

```bash
KERNEL_CLEAN=1 ./scripts/build-kernel.sh
```

Faster compile-only iteration when modules are irrelevant:

```bash
BUILD_MODULES=0 ./scripts/build-kernel.sh
```

Audit stock evidence supplied locally:

```bash
./scripts/audit-stock.sh /path/to/stock.config /path/to/live-device-tree.dts
```

Before committing a script change, at minimum run:

```bash
for script in scripts/*.sh scripts/lib/*.sh boot/*.sh; do
    bash -n "$script"
done
```

If the build environment is available, also perform `BUILD_MODULES=0 ./scripts/build-kernel.sh`. For config/DTS/patch changes, a clean build is preferred.

## Bring-up order

Do not debug everything at once. Work in this order unless logs prove another dependency is blocking:

1. ABL accepts the Android v4 image and enters Linux.
2. persistent log / serial diagnostics survive reboot;
3. reserved-memory is safe and there are no TrustZone fatal resets;
4. UFS and/or microSD root storage;
5. USB gadget/Ethernet rescue path;
6. panel/display;
7. touch, buttons and S Pen;
8. GPU/Turnip;
9. Wi-Fi and Bluetooth;
10. audio and DSPs;
11. charging/Type-C/DisplayPort;
12. cameras, sensors and fingerprint/SPSS.

A failure before Linux entry must be debugged as an ABL/boot-image/DT selection problem. An empty pstore is not evidence of a kernel crash if the bootloader never transferred control.

## Boot architecture after the Debian userspace split (2026-09-24)

The minimal profile (`gts9_minimal_rootfs=1`) now does one thing: find the TF
card, mount it, and `switch_root` into Debian. Everything that used to happen
in the initramfs before that - panel recovery, the USB ACM gadget, the report
channels - is Debian's job:

- `boot/minimal-rootfs-init.sh` + `boot/minimal-rootfs-state.sh` write the
  persistent stage record `/var/log/gts9-minimal-last-boot` on the Debian root
  (atomic replace, `switch-root` flushed before the exec).
- `rootfs-overlay/` carries the Debian units and helpers:
  `gts9-debian-entered/basic/getty/multi-user-stage.service` continue the same
  record from systemd, `gts9-usb-acm.service` creates only `acm.usb0`,
  `gts9-panel-recover.service` runs the X710 framebuffer blank/unblank cycle,
  and the ttyGS0 drop-in auto-logs in root on that console only.
- `scripts/install-debian-rootfs.sh` installs that overlay into a mounted
  Debian root or builds `out/gts9-debian-overlay.tar` for TWRP.  Kernel
  modules and firmware live in Debian under `lib/modules/<release>` and
  `lib/firmware/`; the minimal initramfs carries neither.
- `scripts/twrp-mount-debian.sh` and `docs/TWRP_DEBIAN_RECOVERY.md` are the
  offline path: identify the ext4 partition, mount it read-only and read the
  record when the panel is black and no USB console appears.

Rules that follow from this:

- Never make USB, DRM or tty1 a dependency of the root handoff. Panel and USB
  must fail independently of each other.
- A black screen plus no COM port is not a rootfs failure verdict; read the
  persistent record first (live or from TWRP).
- Do not modify regulator/PMIC parameters without stage evidence proving that
  the card never appeared.
- Keep the boot-critical providers built in (MMC/SDHCI, ext4, RPMh, PMIC, PDC,
  clock, pinctrl); do not move Pogo or the panel to modules yet.

## Samsung ABL constraints

Keep the legacy Samsung selectors in the board DTS unless a physical test proves they are no longer required. The X710 Azkali bring-up and sibling X910 work both demonstrate that Samsung ABL can reject an otherwise valid upstream-style DTB before Linux starts. Preserve `/__symbols__` in DTBs used in experiments that exercise Samsung's DT overlay path (`DTC_FLAGS_... := -@`).

For the pinned Linux 7.2-rc3 baseline, keep `kernel/patches/0001-arm64-dts-qcom-sm8550-add-samsung-abl-labels.patch`: Samsung ABL expects `qcom_tzlog`, `arch_timer`, and `qcom_scm` labels in the SM8550 base tree. Re-check whether the patch is still needed whenever the upstream kernel pin changes.

The current boot-bundle script uses the safer appended-DTB fallback pattern and deliberately does not flash anything. Do not change `dtbo` strategy casually; document the reason and recovery path first.

## Working with the stock config

The owner-extracted stock 5.15.153 `.config` is the **immutable seed and evidence baseline**, but it is not assumed to map one-for-one onto Linux 7.2. It is stored as deterministic Base64/gzip parts under `reference/stock/config/`; `scripts/materialize-stock-config.sh` reconstructs the original bytes and refuses a SHA-256 mismatch.

Use the stock config to answer questions such as:

- was a hardware block enabled in Samsung's kernel?
- was a driver built-in or modular?
- what compiler/Kconfig features did stock use?

For the mainline build, reconstruct the stock config, merge `kernel/config/gts9wifi-mainline.fragment`, then run Linux 7.2 `olddefconfig`. Unknown Samsung/Android-only 5.15 symbols are expected to disappear; required upstream symbols must be asserted explicitly by the fragment/build checks. Never edit the stock seed in place. A refreshed stock extraction must be added as a new identified artifact with updated hashes.

## Patch discipline

- Prefer upstream commits/backports over local patches.
- Every local patch should have one purpose and an explanatory commit message.
- Keep device-specific quirks gated to SM-X710/SM8550 where practical.
- If a patch becomes upstream, replace the local copy on the next controlled kernel rebase.
- Do not add Android-rooting/security modifications to this repository; keep the mainline hardware port focused.
- Do not import Azkali's `c48fedbd799a` early-boot framebuffer/Gunyah watchdog instrumentation into the default patch queue. If conventional logs are unavailable, reproduce it only as a temporary diagnostic series on a dedicated branch.

## Logs to request after physical tests

Ask for the smallest useful evidence set, typically:

```bash
uname -a
cat /proc/cmdline
dmesg -T > dmesg.txt
cat /proc/iomem > iomem.txt
cat /sys/firmware/devicetree/base/model 2>/dev/null
ls -l /dev/dri /dev/mmcblk* /dev/sd* 2>/dev/null
lspci -nn 2>/dev/null
ip -br link
```

For boot failures also collect Samsung/TWRP `last_kmsg` or ramoops/pstore if available. Record the exact artifact hashes that were flashed/tested.
