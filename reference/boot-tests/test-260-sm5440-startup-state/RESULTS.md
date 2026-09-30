# Test260 offline repair outcome

SM5440 startup state corrected: a first-only preconversionREVBLK with livefaults
clear, verifiedmodeOFF, PCVBUS and zeroIBUS is retained as a suspect event.
HealthUNKNOWN/noADC publication until TWO subsequent clean conversions within
5s, unchanged protections and safe values. Live/recurrentREVBLK, ANYVBATOVP
(including0x82), I2C/ADC/deadline/detach/PM faults latch failure. No faultdecoder
mask, protection/current write, pumpON or PPS. HistoricalTest258/259 results
remain unchanged. This refinement is compiled/host-tested, NOT hardware-tested.

Source6fbafede: standardLinux7.2-rc3/clang21.1.8/JOBS8/ccache Image/DTB/modules
build and bundle/artifact audit pass.181 modules paired. Config and DTB are
byte-identical to Test259; exactTest255 deltas remain passive enable/inactive
policy declaration and charger@63status only.96 protectedfiles/85containers
remain unchanged; HVC_DCC=n. ChangeddriverW=1 and actualsparse check pass with
no changeddriverdiagnostics; one existingVDSO declaration warning retained.
No dtbs_check rerun for unchangedDTB; prior PS5169 schema caveat remains.

Full1290 host checks at6fbafede pass (report109.553s), zero failures/errors/skips;
all prior1270IDs retained,+20 (8driver/12admission). Driverfocused23 pass. Final
host-only followup5ee5ce56 extends tablet-side evidence to EVERYtransportfailure,
with affected12admission checks rerun/pass. It changes no kernel/build inputs;
reuse qualifiedbuild and unaffected fullsuite coverage, no redundantbuild/full.
Exact revisions and reports are in summary.json/validation. No CI.

ADB-first admission saves fullkernel and supplies before anyNCM check; current
Windows/WSL address/route snapshots and boundbanner/NCM authentication work on
installedTest255 bootcfb09d01. This DOES NOT establish/fix the historicalTest259
NCMtimeout cause. New helper retains Windows/WSL topology BEFOREfirstprobe and
device-side state on failure; singleattempt, no retry-to-clean. Futurefailed
boot evidence can distinguish adapter/APIPA/mirroring/boundTCP/auth stages.

No flash/reboot/modules/rootfs/deviceconfiguration change this task. Tablet
remains exact acceptedTest255, oldrollback/Test258/259tested modules intact.
Artifacts remain under out/kernel-x710-260-passive and out/boot-bundle-x710-260-
passive, not deployed/staged toWindows. See PHYSICAL_PLAN.md for separately
registered futurePCUSB150s acceptance; no automatichardwareattempt.

Passive correction candidate: OFFLINE QUALIFIED; physical acceptance pending.
ActiveStage3 candidate: NOT READY.
