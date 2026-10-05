# USB reconnection — read-only endpoint verification

The owner reported reconnecting the PC USB cable. One native ADB read, Windows
PnP capture, interface-bound NCM SSH-banner probe and authenticated Wi-Fi SSH
identity check pass. Composite/ADB/NCM have ProblemCode0; NCM is Up.

Boot remains `e71954cf-fb78-4ee3-aa76-cbaafe5841fc`, the accepted311/Test318
rollback boot. Embedded config, kernel notes and normal command line match the
registered accepted baseline. SSH/adbd/gadget are active, Sink/Device remains,
DCC is absent and no systemd failed unit is reported. No flash, reboot, service
restart, USB reset, device configuration change, PPS or pump-ON command issued.

Pack:22%,3.746V,31.5C,Good. PC SDP input500mA and net battery current-280mA:
this PC connection does not supply enough to make net battery current positive.
SM5440 remains OFF,IBUS0,passive fault0. Do not mistake driver Charging status
for positive net battery charging.

Full1100-row same-boot kernel journal retained losslessly with source timestamps.
The earlier1060-row Test318 rollback journal is an exact cursor prefix; the40
additional rows contain no detected CPU-stall/panic/Oops signature. Existing
startup MDSS/SMMU faults remain UNKNOWN; no overall stability-clean claim.

Result: **USB_RECONNECT_ENDPOINT_PASS**. This proves the current endpoint works;
no disconnect timeline or recovery duration was captured, and this does not
prove a permanent charger-to-PC USB fix. Historical Test319 STOP and Test318 ADC
READY timeout remain unchanged. No additional physical cycle or long window.

Host tests/build: `executed: false` (results only, no executable inputs changed);
existing qualification reused. No GitHub Actions. Summary, original command
outputs/metadata and compressed raw journal are sealed in SHA256.json.
