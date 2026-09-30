# Test258: SM5440 passive probe on ordinary PC USB

Owner authorization: "刷入测试吧" (2026-09-30). Start test HEAD976b43b8.
This supersedes the earlier offline-only authorization for this bounded test.
It does not authorize PPS, pump ON or increased charging current.

Purpose: first physical acceptance of the separate sm5440-passive profile,
without the X710 transaction core. Current accepted rollback is Test255
Stage2 fixed5V<=1800mA/fixed9V<=1500mA,4440mV float and2100mA pack current;
Test253 adbd and Test254 container configuration remain unchanged.

Candidate: build current registered source using GTS9_CHARGING_PROFILE=
sm5440-passive. Only CHARGER_SM5440_DIRECT=y and the existing isolated hub3
charger@63 status enable differ from default. Preserve GPI DMA, all ordinary
charging/thermal/USB/TCPM logic, HVC_DCC=n, USER_NS and all85 container gates.
X710_CHARGING_POLICY must remain disabled/absent. Stock TCPM still rejects PPS.
Passive driver exposes no pump-ON or writable charging property. ADC sampling
checks actual modeOFF; only OFF verification and ADC converter writes exist.

Sequence: read-only accepted-Test255 identity/rescue/rollback preflight; commit
and push this registration; immutable full build/host/config/DT/protected audit;
construct and validate paired boot/vendor_boot/modules with exact old cmdline,
bootconfig and ramdisk; commit/push artifact identity; TWRP rescue inspection;
backup/readback and install ONLY boot/vendor_boot plus181 matched modules;
ordinary Debian startup; fresh candidate identity and at least150s responsive
PC USB observation. No charger change or unplug/replug is requested in this
first test. Record all kernel journals, ADC/thermal/charging/Type-C/transport
data, raw command results and final identity. Never infer reboot from SSH loss.

Entry: ADB/NCM/Wi-Fi SSH usable, exact five partitions/config/notes/181 current
modules, all three historical rollback directories and external accepted
Test255 rollback pair verified. Battery present/Good,SOC5..<80,temp20..<38C,
VBAT3500..<4300mV. Windows must show no Code43. Record current boot dynamically;
do not assume Test255's old boot ID remains current.

Stop first: unknown identity, new unexplained kernel fault/reboot, Code43/rescue
loss, failed unit, I2C/probe/ADC timeout/error, passive fault latch, no fresh
modeOFF-backed ADC, nonzero pump mode, unexpected PPS/APDO/Source role,
battery>=42C or abnormal rise, VBAT>=4300mV, passive die>=60C or rise>=10C,
PC-USB reported VBUS outside4500..5500mV or IBUS>100mA. ADC is uncalibrated;
these reported-value refusal bounds are not independent voltage/OCP proof.
Retain first failure and restore the exact accepted Test255 boot/vendor_boot/
module pair after verified recovery if necessary; no retry/new experiment.

Do not flash init_boot,dtbo,vbmeta, alter rootfs service/USB/adbd settings,
request PPS, enable pump, test thermal/OVP/OCP limits, suspend or warm-loop.
All writes/readback/BCB recovery follow the already reviewed X710 workflow.
Preserve Test252/249 and Test254 backups. No CI/main merge.

This test may qualify passive probe/observed telemetry only. It does not accept
ADC scaling, independent physical VBUS, software OCP/protection, PM/live adapter
or active charging. Stage3 active remains NOT READY. Subsequent fixed-PD ADC
calibration needs its own registration and calibrated meter; no automatic PPS.

## Preliminary accepted-software charging-mode boot

Initial preflight stopped on differing vendor lpcharge parameters, before writes.
Five partitions/config/notes exactly match accepted Test255. Preserve this STOP
and complete read-only baseline diagnosis. Only if every other identity/health/
rescue gate passes and differences are limited to vendor *.lpcharge flags,
registration permits ONE normal systemctl reboot of the unchanged baseline to
recover its accepted normal command line, then a fresh normal-preflight. Commit
and push registration before this reboot. No image/module/parameter repair and
no candidate deployment until that fresh preflight passes. If the command line
or any other gate still differs, stop and report; no second baseline reboot.
Candidate-stage stop-on-first-failure and no automatic experiment retry remain.

## Owner workflow refinement (2026-09-30)

Reuse the completed f3a266b5 build/full1264 qualification for unchanged candidate
inputs and sealed artifacts. No rebuild/full rerun for registration, staging,
physical results or documentation commits. Adapted deployment scripts receive
syntax review and the nine existing passive-admission tests. Full baseline
identity is captured once after the registered normal reboot. Enter-recovery
checks same boot/config/notes and fresh battery; TWRP verifies partitions and
root/modules once before writes. Install confirms the same TWRP boot and staged
files, then reads back all five partitions. Observation combines boot ID,
telemetry and fault checks per sample, full journals at boundaries/first failure.
Safety, rescue, rollback and the150s window remain required. No active PPS/pump.
