# Future Test260 physical acceptance (not registered/executed yet)

Publish a fresh attempt registration after owner authorizes deployment. Reuse
qualified source6fbafede Image/DTB/config/notes/181 modules and final admission
helper5ee5ce56. No repeated kernel/full run for unchanged inputs. This plan
alone does not authorize another physical attempt after Test259 STOP.

1. Fresh acceptedTest255 boot/config/notes/normalcmdline, Good battery/SOC,
   20..<38C/VBAT3.5..<4.3V, DCCabsence, ADB/NCM/WiFi, Windows noCode43 and
   healthy journal. Confirm exact rollback pair/181 files. TWRP alone checks
   five partition hashes/current181 modules at the write boundary; no redundant
   Debian/backup hash loops. PreserveTest258/259tested modules.
2. Review staged paths against the seal BEFORE recovery. Use freshTest260
   slots and release-root helper; test actual archive install/restore once.
   Register/push, then established BCB request plus ordinarysystemctlreboot.
3. TWRP identity/rootUUID/machineid/battery, candidate/rollback hashes. Install
   only pairedboot/vendor_boot/181modules, verify readback, cleartemporaryBCB,
   unmount, record/push. Keepinit_boot/dtbo/vbmeta and every device setting.
4. OrdinaryPCUSB boot only. Require changed/unique attributed boot, newconfig/
   notes and actualsource module pairing. Save earlyADB identity/fulljournal/
   battery/passive/roles BEFORE anyNCM authentication. Do not leave a hardware
   fault unexamined while waiting forSSH.
5. Admission helper performs one captured transport attempt, with Windows
   addresses/routes/Code43, mirroredWSL route/addresses, Windowsinterface-bound
   SSHbanner then actualNCMSSH and boot match. On ANYfailure capture additional
   deviceinterfaces/services/fullkernel evidence, STOP. No retry-to-clean.
6. Startup exception only under the documented first-only0x80/PCVBUS/0IBUS
   constraints: two new clean conversions within5s and complete paired
   pending/rawfault/confirmed kernel records. HealthUNKNOWN or missing/malformed/
   repeated/out-of-order confirmation fails admission. Retain startup warning
   classification explicitly; do not call this a warning-freeboot. Test2580x82
   remains a failure; anyVBATOVP/live/recurrentREVBLK always fails.
7. After admission,150s sameboot PCUSB monitoring: sourcehealth, VBUS4.5..5.5V,
   IBUS<=100mA, die<60C, pack<42C/VBAT<4.3V, Sink/Device; no newkernel/CPU/
   failedunit/transport error. Fulljournal at boundaries/firstfailure, samples
   combined per5s; no per-sample partition/modules/rollback hashing.
8. Firstnonclean stops. Save raw evidence and restore exact acceptedTest255
   boot/vendor/181modules via verifiedTWRP; five readbacks once, finalidentity/
   health/rescue gate once. No automaticnewattempt or reclassification offailed
   results. No PPS, pumpON, protections/current/thermal/USB changes, unplug/
   charger/suspend/activeStage3 tests. ADCcalibration/OCP remain separate.

Successful bounded passive acceptance is not direct-charge readiness. Stage3
activation still requires independently verified protection/softwareOCP/physical
ADC and PM/transaction adapter. Do not use inherited11V/4487.5mV pump settings
as approved board limits or alter them simply to clear a warning.
