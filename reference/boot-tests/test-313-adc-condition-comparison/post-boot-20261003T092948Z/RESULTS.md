# Restored ordinary boot: read-only owner follow-up

Owner reported the tablet powered on. The live boot ID remains
`1f1e01bf-de96-43b0-8e36-3237a92dcd80`, the exact accepted311 restore already
recorded in Test313. No additional reboot is inferred. At capture, uptime was
1672.74 seconds, SOC37%, gauge3.794V, real pack temperature31.9°C. Embedded config
and notes match the accepted ordinary kernel. ADB works; ssh/adbd/ACM services
are active; device usb0 and Wi-Fi addresses exist; role remains Sink/Device;
DCC is absent and no failed systemd unit is reported. This is device evidence,
not a newly executed host NCM TCP acceptance.

Seven existing atomic pointer/read transactions verified ordinary Q4 ON,
500mA PC input/fast current programming and4440mV float code. PC input may not
cover system consumption: negative net battery current is retained in raw
telemetry, not claimed to be positive charging. No configuration-data write,
PPS request, pump enable, flash or reboot was performed.

The complete current-boot kernel JSON contains1100 rows with a unique boot ID.
The existing classifier reports no matched CPU/kernel fault signatures; the
known passive startup confirmation refusal remains separately retained. This
bounded capture is not a new warm-reboot regression or reliability proof.
SM5440 remains OFF, activation unsupported and ADC unavailable for charging.
Neither Test313 STOP nor its live fault is reclassified as a pass.

Current thermal_zone37 resolves to `sm5714-battery`, is enabled and reads31900mC.
No `Unable to get temperature` message appears in this boot's journal. Numeric
thermal-zone IDs are not stable provider identities across kernel versions;
the earlier photograph alone does not establish which provider failed then.
Do not disable the pack thermal zone or fabricate a sensor value to hide it.

Initial host snapshot lookup used a nonexistent generic debugfs path; its raw
error is retained inhealth.txt. The registered provider-specific command then
captured the actual snapshot successfully in current-state.txt. This was a
host lookup error and caused no device change. All command timestamps, complete
journal, raw state and hashes are preserved alongside this report.

Host tests/build executed:false: evidence-only follow-up reuses unchanged
qualification. No new physical experiment, ADC calibration, PPS/direct-charge
acceptance or readiness is claimed. Next implementation remains the separate
source-bound pump-OFF preparation described in SM5440_ADC_CONDITION_TEST.md;
no repeat of the unchanged failed PC5V condition profile.
