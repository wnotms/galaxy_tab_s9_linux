# PC USB reconnection — read-only endpoint

Owner reported completing the requested cable reconnection. One endpoint capture
passes native ADB shell, Windows composite/ADB/NCM ProblemCode 0, NCM Up,
interface-bound Windows NCM SSH banner and authenticated Wi-Fi SSH.

Boot `ecaa3c64-5c69-4bbe-b755-1a2aff6a88ca` is unchanged. Embedded config,
kernel notes and cmdline match the preceding accepted endpoint. Sink/Device,
three active transport services, no failed units and DCC absence remain.
No reboot, flash, service restart, USB reset, charging configuration, PPS request
or pump enablement was performed. SM5440 remains OFF, IBUS 0 and passive fault 0.

Pack 16%, 3.699 V, 31.3°C, Good; PC SDP input limit 500 mA, net battery current
−349 mA. The pack is discharging despite the Charging label. SOC is below the
registered 20% deployment admission threshold; no deployment is attempted.

Full 1108-row kernel journal is retained losslessly with source timestamps.
The preceding 1104 cursors are an exact prefix; four new rows concern stack
usage and screen/backlight off, with no detected new CPU-stall/panic/Oops
signature. Earlier display/SMMU faults remain unresolved; this is not an overall
stability acceptance or proof of a permanent charger-to-PC USB fix. Physical
unplug/recovery timing was not continuously captured.

Verdict: **USB_RECONNECT_ENDPOINT_PASS**.
Device/Windows raw CRLF outputs are retained losslessly as .txt.gz; Windows
PnP bytes use GB18030 and have not been rewritten as UTF-8.
Host tests/build `executed:false` because only evidence/status changed; no
Actions. Commands, full output, summary and this report are sealed by SHA256.json.
