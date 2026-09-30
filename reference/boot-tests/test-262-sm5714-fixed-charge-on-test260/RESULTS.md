# Test262: ordinary fixed-PD charging, endpoint checks, retained evidence gap

On unchanged installed Test260 passive candidate, ordinary SM5714 fixed-PD
charging completes **300.011s/61samples** on the owner's Lenovo YG65G USB-C2
18W PD source. TCPM negotiates fixed9V/1.5A; SM5714 input limit stays1.5A.

| Charging-window observation | Result |
| --- | --- |
| Battery net power |6.568–8.289W, mean7.827W |
| Battery current |1.659–2.068A, positive61/61 |
| Battery voltage |3.959–4.016V |
| SOC |54% →56% |
| Pack temperature |28.4–29.2C |
| SM5440 reported VBUS |9.077–9.123V, uncalibrated |
| SM5440 reported die temperature |27.5–35.0C |
| SM5440 reported current |0 throughout, pumpOFF |

No new detected CPU stall/panic/Oops, kernel/I2C/PD-reset/passive fault or failed
unit in the recorded charging window and subsequent complete journals. Fixed-PD
limits, battery2100mA/float4440mV, thermal and fail-closed policies unchanged.
Sink/Device retained. Test260's single confirmed-inactive startupREVBLK event
is preserved; no statement that historical Test2580x82 was harmless.

## Evidence gaps and separate outcomes

1. First charging observer (`charging/`) stops before charger attachment due
   the empty@@failed EOF host-parser bug. Original STOP/raw records retained.
   Narrow correction and four exact capture replays plus telemetry/admission
   pass44 affected tests; fresh charging-attempt-02 provides the charging result.
2. Pretest continuous Windows connection sounds are retained separately. Owner
   reports recovery after manual replug; fresh transports pass. Root cause is
   unknown; no USB configuration or adbd repair was performed this test.
3. Original unplug observer (`unplug-attempt-02/`) stops waiting300s while still
   attached, before the owner's removal was observed. Its STOP is not rewritten.
   Therefore the unplug transition itself is **not captured**.
4. After owner confirms removal, separate post-unplug-readonly captures15.001s
   offline/Discharging/-0.91..-1.129A/pack29.6C, same boot, healthy passiveOFF and
   unchanged complete kernel/startup. This verifies the resulting endpoint only.
5. After owner confirms PC attachment, nativeADB, configuredUDC, Wi-Fi and one
   verified-path NCM authentication pass, no observedCode43 or unready sample.
   Config/notes/DCC absence match Test260. Precise reconnect/recovery time is
   **not measured**. Device remains on this candidate, connected to PC.

**Outcome: charging phase and final endpoints pass; whole procedure has a
retained observation gap and is not a wholly CLEAN series.** No charger
reattachment/repeated charging experiment was used to hide a failure. Raw
source timestamps/command statuses and stopped attempts remain available.

Battery net power is VBAT×IBAT and excludes system consumption/conversion loss;
13.5W is configured input ceiling, not measured inputpower. No inline meter or
independent physical VBUS calibration; no actual18W-draw, ADC/OCP/protection,
PPS/direct charging, PM/high-current or long-term reliability claim. Human wait
samples outside the300s window are not a20min acceptance or an automatic test
extension.

No device software/configuration write, flash/reboot/module replacement occurred.
DTS/config/SM5714/SM5440/USB/DWC3/adbd/CPU/DCC protected sources are unchanged
from pretestbb5af694. Test253 reconnect and Test254 container settings remain
in the identical embedded config. Exact Test255 rollback images/modules remain
available; rollback was unnecessary. No GitHub Actions, kernel build or full
host rerun; Test260 qualification and corrected44 affected tests are reused,
results-only test execution=false. Completed evidence sealed with SHA256.

Next: improve future human-action orchestration so command deadlines begin
after confirmation and missing transitions stay explicit. Separate physical
ADC/protection/PM/transaction gates are still needed before any active Stage3
candidate; no automatic PPS/pump test, current increase or new hardware attempt.
**Active Stage3: NOT READY.**
