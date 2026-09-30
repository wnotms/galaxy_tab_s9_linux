# Future Test263 passive snapshot acceptance — not executed

Requires new explicit deployment authorization. Device currently keeps passed
Test260 plus Test255/older rollback. No PPS/APDO, pumpON, SM5714 Q4 handoff,
current increase or protection/thermal modification is in this candidate.

1. Verify rescue once (ADB/NCM/Wi-Fi), currentboot/config/notes, batteryGood and
   normal temperature/SOC. Preserve exact installed Test260 images/modules as
   rollback. At deployment verify paired writes/readbacks/modules once; do not
   repeat full hashes on every observation. Stop unknown identity/Code43/fault.
2. One normal PCUSB candidate boot. Apply the accepted Test260 first-only
   startupREVBLK gate; retain raw event and require its bounded completion.
   No broader fault whitelist. Check new candidate config/notes/181 pairing;
   fixed profile/config/DCC/SM5714 safety/USB/adbd unchanged.
3. On PC5V collect30s of read-only snapshot/gauge/TCPM (combined command, every5s).
   Expected path `/sys/kernel/debug/sm5440-0-0063/snapshot`; device name derives
   from actual bound I2C device, not a guessed hard-coded bus. If file is missing
   or debugfs unavailable, preserve first evidence and stop; no runtime repair.
   Require sample_present/valid/fresh, no fault/pending/stopped/error, age<=2500ms,
   modeOFF, IBUS0 and unchanged protections. Startup snapshot remains retained
   separately. Compare raw decoding with sm5440-hw.h and simultaneous gauge.
4. Only afterward, and within that separate registration, approved18W USB-C2
   fixed9V source,<=1.5A ordinary input: capture30s repeatability/age/raw/gauge
   comparison through Wi-Fi. Independent inline meter is still needed to claim
   physical absolute VBUS calibration; without it record telemetry comparison
   only. Test262's power/current/temperature bounds and immediate fault stops
   remain; no deliberate heating, higher PDO or pump run.
5. Remove source and restore PC rescue once. Human-action confirmation is
   separate from command/transport deadlines. Start a bounded endpoint check
   after confirmation; if continuous transition capture is desired, preserve
   actual source timestamps and explicitly register a sufficient human waiting
   budget. Never relabel a waiting timeout or late endpoint as a captured clean
   transition. Final full journal/health and one ADB/NCM/Wi-Fi check.

Any new REVBLK/VBATOVP/invalid ADC/I2C/unexpected mode, unsafe voltage/current/
temperature, CPU/kernel fault, unknown boot or rescue loss stops. Preserve
first evidence and restore exact accepted Test260 through registered recovery
if necessary; no automatic retry/protection write/diagnostic kernel switch.
New read-only snapshots do not clear latches or grant active charging.

This plan qualifies the evidence interface only. Independent ADC calibration,
complete protection/OCP and PM/live-adapter qualification remain later gates.
**ActiveStage3 NOT READY.** No future test is started by writing this plan.
