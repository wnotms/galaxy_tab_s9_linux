# Test386: correct minimal overlay then one ADSP DIAG handshake

Test385 passed the new three-snapshot recovery gate but stopped offline before
candidate vendor write: its desktop installer still expected8 legacy RPC files,
while the registered manifest had5 no-RPC trace/text files. It restored all
stock assets and baseline partition/module bytes. This is a host scope defect,
not a firmware/CPU/DIAG negative result. Preserve Test385 original STOP.

Correction: the new386 installer has exactly the five allowlisted manifest
paths; real temporary-root install/restore/failure/foreign-file replay tests
exercise actual ledger and readbacks. No new service, driver, config or module
change. Separate386 namespace keeps old evidence immutable. This is not an
unchanged rerun. Reuse385 recovery gate and exact370 Image/config/DTB/181,
qualified382/383 earlyvendor and matched native rpmsg_ctrl module32CRCs.

Fresh full baseline once, one attributed earlyADSP text boot,5s health and
zero-loss GLINK within300s boot; one DIAG CREATE/OPEN,15s device/19s host,
one1s passive read64KiB max, no masks/protocol writes/RPC. Native control module
is explicitlytemporary runtime/externaltaint. No force-load/reopen/live unload.
Any first new severe kernel/USB/battery/identity/evidence or endpoint/deadline
failure stops. Always restore exact370/vendor/assets/5ownedfiles and normal
GNOME; reboot removes temporary module/endpoint. Lost rescue requires recovery,
no blind boots. PPS/pump/DCCOFF; no sensor/rotation acceptance from handshake.
Only closed exact enrolled baseline evidence; no future USB error waiver.
Register/push beforemutation. Affected host/syntax only, reuse unchanged build,
no GitHubActions. Next action comes from new raw DIAG/GLINK evidence, no second
unchanged endpoint probe.
