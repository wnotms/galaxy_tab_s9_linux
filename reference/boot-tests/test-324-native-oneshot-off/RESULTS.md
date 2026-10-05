# Test324 — stopped; accepted Test323 restored

The original Wi-Fi evidence stop is preserved. After owner charger-to-PC
reconnection, ADB recovered the same candidate boot without another reboot:
`eb24355a-b887-423f-9c50-a2d7ac60a08d`. Kernel config/notes match the registered
one-shot candidate; journal history uniquely attributes its normal boot.
Native one-shot attempted=0, finished=0, samples=0: this is **not a 100ms timeout**.

The initial OFF ADC sample was VBUS 9.4V, VBAT 4.009V, IBUS zero, die 30°C.
Retained INT3 includes REVBLK; live STATUS3 has VBUSPOK and no decoded fault.
Current inactive-latch classifier is explicitly limited to PC 4.5–5.5V, so it
rejected this 9.4V startup before the native acquisition worker could run.
Adjacent fuel-gauge VBAT 4.087V differs by 78mV; no calibration/coherence grant.
1103 original kernel JSON rows are retained; no detected CPU-stall/panic signature.
Late ADB recovery is not a clean result for the original Wi-Fi collector.

Exact Test323 boot and saved 181 modules were unconditionally restored by the
original 0725c5fa runner. All five partition readbacks matched, BCB cleared and
root unmounted. Final normal boot `4cf32922-df0b-4f90-a48d-27416d777d13` has accepted
323 config/notes, ADB, device NCM, host NCM SSH and authenticated Wi-Fi. Battery
64%, 4.076V, 30.9°C. Existing passive startup confirmation failure is separate
from accepted ordinary charging scope. rollback_required=false.

No PPS, pump ON, current/protection/thermal/USB/rootfs change. Full port NOT_READY.
Next source correction is isolated to the OFF one-shot profile: permit fixed9V
inactive initial REVBLK context only with two new clean same-voltage-class
confirmations, unchanged controls and existing safety/timeout gates. Ordinary
PC classifier and native 100ms deadline remain unchanged. No repeat of Test324.

Build/tests executed:false for physical result recording; reuse ab30aff2
qualification (139 affected tests, ARM64/W=1/sparse) and registered nine host
tests. Post-series host address correction has a separate 15-test record and
never ran on this physical series. Original INPUTS and STAGE_SHA256 remain
historical registration/stage manifests; RESULTS_SHA256 seals the final evidence.
The rollback used frozen original runner before post-series host correction.
