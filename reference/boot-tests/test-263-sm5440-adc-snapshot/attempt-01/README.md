# Test263 attempt01: passive ADC snapshot physical acceptance

Owner authorizes “继续实机测试” after offline qualification aa27d8d9. This
registration permits deployment/one ordinary boot and exact Test260 rollback,
PC fixed5V cached ADC30s, approved LenovoYG65G USB-C2 18W fixed9V cached ADC30s,
then owner-confirmed unplug/PC rescue endpoints. It never permits PPS, pumpON,
Q4 handoff, current/protection/thermal/software/USB changes or a longer power test.

Read ../PHYSICAL_PLAN.md. Kernel source ea938b24, full1351/build/W1/sparse and
exact config/DTB/181 pairing already pass; reuse them, no new kernel/full run.
Bundle cc31efa0 boot, identical efddf31c vendor_boot, a50b498c module archive are
validated/staged with exact Test260 rollback under D:/android/gts9-active/gts9-
test263. PACKAGE/STAGED_FILES record all hashes. No init_boot/dtbo/vbmeta write.
New .gts9-test263-original/stage/tested slots preserve Test260/Test255/older
backups. Per-write staged/readback hashes and exact181 module gates stay.

Fresh read-only preflight confirms accepted18bce160/config f289/notes5425,
Sink/Device, ADB/NCM/Wi-Fi10.191.121.145, battery59%/28.8C, passiveOFF/Good,
no failed unit/Code43/newkernel fault. No temporary fault/USB configuration.
Host setup corrections (cursor footer, existing cmdline path, manifest key)
are recorded; no physical fault or permanent write occurred during preparation.

Commit/push registration first. BCB helper enters verified SM-X710 TWRP; read
all five partitions/current181 modules at write boundary, mount identified
root read-only, verify staging. Commit inspection before boot/modules writes;
install pair/modules transaction, verify readbacks, clear BCB/unmount, push
before ordinary boot. Attribute unique new boot via journal history and exact
config/notes. Early ADB hardware/fault gates precede NCM readiness/authentication.
Reuse accepted Test260 first-only retained0x80/two fresh conversions<=5s;
all other/live/recurrent faults still stop. One bounded host readiness gate,
no auth retry-to-clean. Observe PC30s every5s, full journal at boundaries and
incremental faults per sample. Snapshot read is cached only; compare raw decoding,
reported age and acquisition uptime intervals. Gauge cached capture time is not
independently known: this is repeatability/comparison, not absolute calibration.

PC window: pack<42C, initial20..<38C, SOC5..<80, gaugeVBAT3.5..<4.3V,
SM5440 VBAT2.5..<4.3V, die22.5..<60C, reportedVBUS4.5..5.5V, IBUS0. Require
snapshot present/valid/fresh, age0..2500ms, no fault/pending/stopped/error, OFF
mode before/after, no protection readback change. Startup remains distinct.

After PC pass and owner confirms cable/source action, use Wi-Fi-only30s
fixed9V observation: contract9V<=1.5A, input<=1.5A, SM5714 charging current>0,
pack/SOC/VBAT as above, passiveOFF/Good/IBUS0, reportedVBUS8.5..9.5V, die<60C,
no protection/role/identity/fault change. This is not measured charger inputpower
or independent physicalVBUS calibration. No PPS/fast charging, meter-free
absolute-safety claim, deliberate heating/OVP/OCP test or automatic extension.
Human action confirmation is separate from command deadlines; no waiting timeout
is rewritten as a clean transition. Final unplug/PC endpoint checks are labeled
as endpoints unless transition acquisition actually exists.

First non-clean (including missing snapshot, stale/invalid/raw mismatch, fault,
I2C, unexpected mode/boot, voltage/temperature/current, loss of rescue, Code43,
systemd/kernel fault or incomplete evidence) stops series. Preserve full first
journal/supplies and restore exact Test260 with verified recovery/readbacks;
request manual TWRP when online recovery fails. No second hardware attempt.
Passive snapshot pass does not qualify ADC/OCP/PM/handoff or activeStage3.
