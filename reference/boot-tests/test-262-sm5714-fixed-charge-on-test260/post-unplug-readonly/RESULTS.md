# Post-owner-unplug read-only endpoint check

The owner confirmed charger removal after the original300s observer had
stopped. Four fresh samples spanning15.001s confirm sameboot18bce160,
USB/TCPM/passive online0, battery Discharging and negative gauge current
(-0.910,-1.045,-0.996,-1.129A). Pack29.6C, battery/passive healthGood,
SM5440 not charging/IBUS0, no failed units. Complete current kernel journal
has no new detected fault and the single accepted startup event is unchanged.

This is an endpoint-state check after an acknowledged evidence gap, not a
recaptured unplug transition or a clean result for the original stopped
observer. No charger reattachment, configuration write, reboot/flash, PPS or
pumpON occurred. Qualified telemetry/safety helpers were reused for a read-only
sampling procedure; no new build/full regression was executed.

Next: one PC attachment and current ADB/NCM/Wi-Fi/identity/health check after
owner confirmation. Do not launch another waiting loop while awaiting the
owner; command deadlines start at the actual check, not the human prompt.
No precise physical reconnect/recovery time will be inferred from late replies.
