# USB reconnection — read-only endpoint verification

Owner confirmed a PC USB reconnection. Native ADB shell, Windows composite/ADB/
NCM ProblemCode0, NCM Up, interface-bound NCM SSH banner and authenticated Wi-Fi
SSH all pass. This is a single endpoint capture; cable disconnect/recovery timing
was not recorded. It does not prove a permanent charger-to-PC USB fix.

Same boot `ecaa3c64-5c69-4bbe-b755-1a2aff6a88ca` as Test321 final rollback.
Embedded config, kernel notes and normal cmdline match accepted311. No failed
systemd units; SSH/adbd/gadget active; Sink/Device and DCC absence retained.
No reboot, flash, USB reset, service restart, PPS or pump enablement issued.

Pack20%,3.730V,31.6C,Good. PC SDP input limit500mA; net battery current-381mA,
so the driver's Charging label does not mean positive net battery charging.
SM5440 remains OFF with IBUS0, passive fault0 and last_sample_error0.

Full1104-row kernel journal retained with original source timestamps, losslessly
compressed. Earlier1067-row Test321 final journal is an exact cursor prefix.
37 additional rows contain ordinary Wi-Fi startup, known aux_bridge deferred
probe/interconnect sync messages, regulator retention and stack-depth notices;
no detected new CPU-stall/panic/Oops signature. Prior MDSS/SMMU faults remain
UNKNOWN; no overall stability-clean claim.

**USB_RECONNECT_ENDPOINT_PASS**. No further physical cycle or long observation.
Host tests/build `executed:false`: results only, executable inputs unchanged.
No Actions. Raw outputs, command metadata, summary and report sealed in SHA256.json.
