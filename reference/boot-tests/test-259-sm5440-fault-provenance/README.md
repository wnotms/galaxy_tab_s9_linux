# Test259: passive first-fault provenance

Owner request: repair and continue testing. Start revision b8b95275. Test258
attempt02 remains STOP and immutable. Installed baseline is accepted Test255.

The proven defect is loss of fault provenance: old INT latches, conversion-time
INT4 and live STATUS were merged. Preserve each separately, raw ADC and mode,
and read-only CNTL2/VBUSCNTL/VBATCNTL/PRTNCNTL (Samsung register audit). Log the
first fault with its physical ADC sample before its cache expires. Keep the
same conservative decoded fault latch/stop, including VBAT_OVP and REVBLK.
No guessed protection setup, ignored fault or active charging workaround.

Qualify a new isolated passive candidate once: targeted executable C/mock tests,
one full host regression, standard Image/DTB/modules build and exact config/DT/
protected-file audit. No repeated build/full run for registration/results.

Physical scope: fresh Test255 identity/battery/rescue preflight; pushed sealed
registration before recovery; TWRP five-partition/current181-module check;
paired boot/vendor_boot/181-module install with readback. Preserve Test258
failed modules and use separate Test259 rollback slots. Observe ordinary PC
USB for150s only if all samples are clean. First fault: save full journal/raw
snapshot and stop; restore exact accepted Test255 pair/181 modules. No automatic
second physical attempt. A new correction must have its own qualification and
registration after the first new evidence is analyzed.

No PPS, pump ON, Q4 change, protection write, charger/unplug, suspend, current
increase or active transaction core. Stage2 limits, float4440mV, thermal,
Test253 adbd/Test254 containers, HVC_DCC=n and primary DTS/config unchanged.
All Test258 PC-USB health/transport/identity/temperature/ADC stop gates remain.
A captured fault is diagnostic success but NOT passive hardware acceptance.
Actual overvoltage and ADC calibration cannot be inferred from bitmap0x82.
Active Stage3 remains NOT READY.
