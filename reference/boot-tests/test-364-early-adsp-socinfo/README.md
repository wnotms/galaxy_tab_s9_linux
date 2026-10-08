# Test364 — controlled early ADSP and native SoCinfo boot

One kernel/firmware boot purpose, registered before device mutation. Owner asked
to finish sensors first, then charging, and no longer requires ending in TWRP.
This stage proves early signed ADSP availability and actual native SMEM fields.
It does not claim SSC discovery/rotation or repeat PPS charging acceptance.
No charging current/USB/DTB/cmdline/kernel-driver changes.

Candidate: compiled native-QCOM_SOCINFO kernel + paired181 files; approved55-file
ADSP firmware platform ramdisk in vendor_boot. Generic init_boot/dtbo/vbmeta
remain exact accepted values. Actual ABL ramdisk delivery/PAS authentication
are new questions. Mirror the signed files in rootfs for later segment requests;
copy isolated registry/libraries/configs from exact stock archive. Stock persist
is neither exposed nor modified. No account/package/service/input change here.
GDM stays masked/inactive; never issue live remoteproc start/rebind commands.

Before deployment: fresh single baseline allfive/181, config/notes/boot/history,
real battery health/temperature and ADB/deviceNCM/authenticatedWiFi. Retain old
boot/vendor_boot/modules. Push registration before requesting recovery. Verify
staged bytes and each partition's old/new/readback hash at the write boundary.
Root copying records exact owned paths; restore only those paths on failure.

One ordinary boot, readiness<=90s, unique boot/history attribution. Require new
config/notes and181 pairing, DCC absent, no charging flags, rescue paths healthy,
ADSP running and no firmware authentication failure. Capture native soc_id519/
SMEM format/platform/subtype/version, parse real values using the source-audited
mapper; host fixtures never become device identity. Observe30s responsive text
boot with ADSP, preserve complete kernel journal and fault classification.
Stop on the first fault/unknown attribution/authentication/transport/thermal or
evidence failure. No restart of a failed candidate; restore accepted331 and
original vendor_boot/181, remove only newly owned assets. Healthy final endpoint
may be normal Debian under owner's updated direction.

PASS may retain the candidate in text mode for a separately registered same-boot
SSC runtime/rotation scope. No extra kernel flash just for package activation.
No new PPS/pump/higher-current scope; Test348 remains closed NON-CLEAN.

Reuse native kernel/DT/181 build audit, input CRCs,41affected host coverage and
SSC125 pass. Full3032 NOTPASS remains recorded; this registration does not
invent a full regression pass or recreate retired images. New runner/copy/parse
logic must pass its own host checks before physical execution. No Actions.
