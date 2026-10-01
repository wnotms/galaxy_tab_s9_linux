# Next physical acquisition test — not executed here

Create a separate registration for this exact passive candidate plus one
read-only kernel consumer of `sm5440_passive_request_fresh()`. The current API
has no userspace writer or automatic caller; an unchanged Test263 device cannot
exercise it. The consumer must never expose arbitrary register writes, pumpON,
PPS, latch clear or threshold overrides. One bounded request at a time, preserve
its return code, request/delivery times and genuine acquisition stamp/sequence.

Entry: qualified artifacts/pairing and exact rollback, existing rescue/identity,
healthy passive OFF/fault0/no pending startup, thermistor/pack/source safety.
Follow essential one-time deployment checks; do not repeat partition/module
hashes or full journals per sample. A failure remains failure with raw evidence.

1. PC fixed5V OFF-mode: short30s window of bounded requests, cache/provenance,
   temperature, raw ADC and ADB/Wi-Fi/USB. Report success/refusal/deadline counts;
   no retry to replace failures or claim every request was fresh. No pumpON.
2. Ordinary fixed9V if separately registered: source capability capture via
   the existing TCPM log, physical reported VBUS/VBAT/IBUS0, fixed<=1.5A and
   normal pack temperature (entry20..<38°C, stop before42°C), then unplug/PC
   reconnect. Do not
   infer PPS APDO from18W/65W labeling or test forced voltage/current limits.
3. Independent reference/nonzero-current calibration and verified protection/
   cutoff response must precede a live active adapter. Mock elapsed-time guards
   cannot qualify scheduler/I2C worst-case latency, real OCP or ADC accuracy.
4. Only a separately built/reviewed live PM-safe adapter and actual PPS APDO
   supply can allow subsequent pumpOFF PPS negotiation. No active current stage
   is authorized by passive acquisition acceptance alone; preserve SOC<80 and
   existing voltage/thermal/current bring-up limits.

Stop on actual fault/I2C/unknown OFF/identity/rescue/kernel fault or unsafe pack/
source telemetry; no automatic pumpON/retry/raising limits. Raw host-only errors
remain separate from device behavior per owner criterion. Rollback preserves
exact Test263 boot/modules and older backups. This document does not schedule
or claim a device action; Test272 changes no installed software.
