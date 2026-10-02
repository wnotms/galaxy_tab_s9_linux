# Test296 — vendor ADC rearm comparison

**DEVICE_REARM_DIAGNOSTIC_COMPLETED; exact263 restored.**
Source18e495bc, registration92f844a9 pushed before mutation. ONE passive PCUSB
candidate boot 6f688b219f454af49f35b27736955e2b; three voltage pairs,
15-second sameboot device endpoint. ADB/services/deviceNCM/SinkDevice/config/notes/
full kernel evidence/WindowsCode0 pass; no detected CPU/panic/RCU/CSD signature.

| Seq | ADC oldest→read complete(ms) | SM5440 VBAT | Gauge start→end(ms) | SM5714 VBAT | Difference |
|---|---|---|---|---|---|
|1|169→302|3.5970V|302→302|3.880V|283mV|
|2|1333→1477|3.5975V|1477→1478|3.822V|224.5mV|
|3|2520→2661|3.4970V|2661→2661|3.816V|319mV|

Adding Samsung's20ms disabled rearm interval did **not** resolve the voltage
difference or startup confirmation failure in this boot. Third sample remains
below3.5V; refusal at2.666175s is retained. This does not exclude every possible
rearm effect or establish a sensor calibration/root cause. No guessed offset or
threshold relaxation. Millisecond timestamps locate software reads; gauge internal
hardware acquisition time is unknown, and conversions are not simultaneous.

The preamble checks OFF, disables only ADC enable, unlocks for20ms and checks
cancellation. Original sample_once/ADC math/AVG32/channel/read-to-clear handling,
100ms/500ms guards/startup thresholds/5sdeadline/fault latch stay unchanged.
Retained raw mode01/01 means OFF inbits[3:2], IBUS0, protectionsf2/e7/37/fe.
No PPS/pumpON/reset/active init/continuous mode/current or fixed-PD policy change.
This source-backed correction is compiled/host-tested/device-exercised, **not**
a successful repair of the observed VBAT discrepancy or active charging grant.

## Transport and recovery

Baseline NCM SSH had recovered and authenticated sameboot. Candidate and final
host NCM probes again timed out, while device ADB/ssh/adbd/usb0 and WindowsCode0
remained present. The registered device-centred OFF-only scope records this
host limitation once per boundary without extending or restarting the test;
it does not claim host NCM accepted or classify the timeout as a CPU fault.
No driver/network/service workaround was applied.

Unconditional allfive partition/181module restoration passed; original263boot,
unique296tested slot/olderbackups retained, BCBclear and root unmounted. Final
attributed263boot ffca1c7b35fe4423b717499e7985e357; ADB responsive, exactconfig/notes/cmdline, no failed
units or new kernel signature. PackGood,44%,
3.826V,30.2C,
IBAT-719mA. Passivehealth remainsREFUSED;
ordinary PC charging status is not proof of positive net battery current.

## Scoped qualification

228affected SM5440 tests pass,8new real-C/PM/mode/I2C/rearm cases,7.638s.
5runner cases pass. ARM64 ccache build91.64s; W1/sparse and byte-identical
object pass. Exact295config/DTB, protected source/8compiled overlays/181paired
module archive pass. Full regression executed:false; unchanged294 qualification
reused. No CI/Actions, no unrelated DTS/SM5714/TCPC/adbd/USB/CPU/DCC change.

## Next

Vendor sm5440_convert_adc refuses ordinary CHG-OFF readings belowCHECK_VBAT;
Fedora active initialization uses continuous ADC and gauge eligibility. These
are operating-condition differences, not permission to skip current safety.
Prioritize the real mainline PPS/coordinator prerequisites and authoritative
measurement validity over further delay-only trials. No direct/PPS activation
while physical ADC/OCP/PM requirements are unproven. Fullwiredport remains
incomplete; ActiveStage3 NOT READY.
