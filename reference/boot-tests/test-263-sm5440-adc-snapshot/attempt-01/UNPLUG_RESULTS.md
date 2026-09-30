# Test263 attempt01 unplug endpoint — PASS

Owner confirmed charger removal before capture. Four samples over15.370s on
33435db741e94574aeb2c209730acf67 confirm Discharging, battery current
-1.720..-1.063A, gaugeVBAT4.011..4.018V, SOC65%, pack29.4C. USB/TCPM/SM5440
online=0 throughout; no PD contract remains. Wi-Fi remains responsive.
SM5440 IBUS0, modeOFF, die29..30C, valid/fresh cached snapshots with age28..896ms,
no live fault/I2C error, unchanged protection bytes f2/e7/37/fe. Full kernel
journal scan has no new kernel/CPU/systemd failure; original bounded startup
event remains separately retained.

Detached reported VBUS4.096V is the ADC decoding floor (raw VBUS bytes00 00),
not evidence of an attached4V source. This endpoint verifies offline/discharge,
not independent voltage calibration. No captured unplug transition or measured
physical recovery time is claimed. Computer USB rescue endpoint remains pending.

No device configuration/write/reboot/PPS/pumpON/current/protection/thermal/USB
change. Results-only validation executed:false; reuse15 endpoint host checks
and exact ea938b24 kernel qualification. ActiveStage3 NOT READY.
