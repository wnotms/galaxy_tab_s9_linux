# Future acceptance sequence — not executed by Test269

1. Audit/resolve full-pack passive startup fault from new and retained raw INT,
   STATUS, OFF-mode, protection and ADC provenance. Do not widen/whitelist the
   <4.3V classifier just to pass. Record the failed Test267 result unchanged.
2. Separately qualify bounded genuine ADC acquisition and nonzero current with
   independent reference; cache lookup cannot manufacture a new timestamp.
   Establish current protection, watchdog/failure response and cutoff latency.
3. Review/implement the serialized live TCPM/charger adapter and supplier PM/
   unbind ordering. No core mutex held over negotiation or work drain; generation
   invalidation aborts old work. Keep fixed5V1800/9V1500mA fallback and4440mV.
4. Only after those gates pass: register pumpOFF PPS negotiation on a confirmed
   PPS/APDO-capable supply, confirm actual VBUS/source bounds. The existing
   Lenovo18W PD label alone is not evidence of APDO capability.
5. Separately authorize initial<=1.8A short pump run, then5min and20min with
   fresh VBUS/IBUS/VBAT/die/pack temperature and identity/rescue evidence. Exercise
   retarget only with measured normal VBAT change; never raise current to induce
   OCP or heat/voltage to a protection limit. Initial pack entry20..<38C; stop
   before42C and on any I2C/fault/REVBLK/OVP/deadline/epoch/rescue/kernel anomaly.
   Stop uses verified OFF, PPS exit, fresh fixed voltage and switching restore.
   If OFF/restore cannot be proven, preserve inhibit and perform registered rescue.
6. Consider2.0/2.25/2.5/3.0A only in later independent candidates after lower-stage
   acceptance, source/board evidence, current protection qualification and explicit
   authorization. No automatic current ramp is provided by Test269.

Rollback for a future deployed candidate must preserve and verify exact Test263/
Stage2 boot/vendor/modules and older backups. Test269 itself changes no device
software, so there is no deployed candidate to roll back. Normal fixed charging
and ADB/NCM/Wi-Fi regression belongs to the future registered device acceptance.
