# Test346 — bounded five-minute PPS/SM5440 stability

Purpose: determine whether the qualified conservative PPS/pump path can sustain one300s observation and restore ordinary fixed9 charging. Test345 short acceptance is frozen; no20min/current increase/calibration/45W/vendor-equivalent acceptance is inferred.

## Exact candidate and scope

Qualified kernel source5c90a4b541588974ecf1572c6d34adfe6bd191b9, Linux7.2-rc3. Reuse79actualC/23prior evidence tests/build104.643s/W1+sparse15.691s. Config51ba6a9c and DTB233a9fee exactly match331;181matching runtime module files (new metadata pairing required). Notes10dcf27f. Armed bootb6ac504e carries exactly two opt-ins:

- sm5440_fedora.direct_charge_once=1
- sm5440_fedora.direct_charge_once_ms=300000

Hardware input1700mA, PPS request/rawIBUS stop1800mA unchanged. Switching fallback5V<=1.8A/9V<=1.5A, float4.44V/thermal/suspend safety unchanged. PPS dynamic request remains within the existing8.2..10.5V/source APDO policy, rawVBUS stop10.8V and500mV target coherence; no new voltage/current capability. No CPU/DCC/DTS/SM5714/TCPM/USB/adbd/rootfs change. DCC remains absent.

## Enrollment and sequence

Registration and frozen inputs must be committed/pushed before mutation. **Execution authorized for one300s attempt** in registration.json and execution-scope.json by the owner reply “允许测试，平板为手动关机重启”, recorded in execution-scope.json. No deployment has occurred yet. Prior<=30s grants do not authorize300s. This approval is recorded in both enrollment fields, bound to the refreshed INPUTS SHA and frozen EXECUTION_INPUTS; commit/push before stage/install. No Windows staging or physical preflight/flash was executed during registration.

1. Fresh exact331 PC preflight: rescue/config/notes/boot history/full kernel journal/allfive/181/DCCabsence/noCode43, preparationSOC20..70, pack20..<38C/VBAT3.5..<4.3V. Current accepted331 result is64440dd5; a later startup needs fresh attribution, not an assumed boot ID.
2. One paired boot install and normal PC startup; verify identity/partitions/modules, then drain initial pre-entry worker and proveOFF/unbound. No pump operation at PC5V.
3. Local guardian waits fresh owner C1 confirmation<=900s whileOFF/unbound. Owner connects Lenovo YG65G C1, C2 empty, WiFi retained; host confirms activationSOC<=70/fixed9/identity and writes one exclusive marker. One rebind, no retry. Manual handoff does not consume300s.
4. Kernel owns the absolute300s deadline,100ms monitoring/500ms gap stop and OFF/PPS/physicalVBUSsettle/ON refresh. Each ON requires>=3zero observations spanning>=100ms; admitted park/resume<=2s. Final<=2s may defer a new refresh without extending the deadline. Guardian360s after activation; host400s observation limit. A live PID at host timeout remains pending, not completed/restarted. Transport-only uncertainty is retained separately from native failure.
5. `monitor` follows that enrolled PID. `collect` saves all original guardian files/full kernelJSON/source timestamps, proves native complete/fixedreturn/lease0 and OFF/unbound. Only PASS permits `charge`30s, then `discharge`15s after physical unplug. Observers import bounded346_guard and require the300000 sysfs parameter; no register configuration writes.
6. Owner PCreturn; `pc-return` checks onceADB/deviceNCM/SinkDevice/OFF/unbound/noCode43. Regardless of verdict, `restore` performs unconditional exact331/original181/allfive readback and uniquely attributed normalboot acceptance. No automatic next duration/current round.

CLI: python3 reference/boot-tests/test-346-bounded-pps-five-minute/host_flow.py <verify|preflight|stage|install|arm|activate|monitor|collect|charge|discharge|pc-return|restore>. Actual cable handoffs remain explicit; never call activate without fresh owner-C1-confirmation.json. No rebind/replay of an consumed or stopped attempt. A transport timeout resumes monitor of the same PID; never launch another guardian to replace it. If both rescue paths are unavailable, unplug and manual recovery rather than blind writes.

## Stop and evidence

Stop first at invalid sensor/source/ADC/I2C/fault/role/boot identity, source/lease generation change, pack>=42C, die>=85C, VBAT>=4.4V, rawIBUS>1.8A, gaugeIBAT>3.6A, physical voltage/coherence violation, unexpected pumpOFF/CHG_ON loss, refresh failure/deadline overrun, PM/detach, CPU/RCU/CSD stall/Oops/panic/new severe kernel fault, Code43 or unproven cleanup. Entry/post-return ordinary windows use the stricter20..<38C/VBAT<4.3V gates. No protective-limit provocation. Preserve first rejected tuple/full journal/native primary and cleanup separately; no higher current, automatic retry, new diagnosis kernel or stock-driver change to finish300s.

Full raw journal is evidence; classifications are derived. Device-side healthy completion is authoritative within registered scope; host-only collection errors must not be fabricated as CPU failure. Missing device evidence remains unaccepted. Independently calibrated ADC/current accuracy and hard-realtime OFF guarantees remain unproven.

Windows ADB: /mnt/d/android/platform-tools/adb.exe. Windows-native TCP relay uses local WSL strict SSH/trust/key; no private-key copy or trust relearning. Retention window337..346; expired336 cleanup recorded separately, accepted331 active/rollback remains protected. No fullsuite/Actions/kernel rebuild for this runner-only registration.
