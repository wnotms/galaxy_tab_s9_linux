# Test394 — actual Samsung recovery SoC identity

Test393 observed sensor_pd UP before/after RPC, with no SSC400. The native
SoC mapping and returned bytes have host qualification, but the five actual
Samsung recovery sysfs values have not been independently compared. This single
new observation checks that boundary; it does not repeat SSC startup.

The unchanged accepted Test370 desktop is the starting and finishing endpoint.
One ordinary recovery round trip, ADB only. Read `/sys/devices/soc0/{soc_id,
hw_platform,platform_subtype,platform_subtype_id,platform_version}` under the
known X710 TWRP kernel, hex-encode the actual bytes, compare with a fresh
boot-bound mainline native snapshot. Record both boot IDs and complete raw
recovery dmesg/available persistent logs. Recovery is not a full Android boot.

No kernel build, flash, module swap, rootfs/registry/firmware/configuration edit,
ADSP/RPC startup, PD/PPS request or pump activation. Only the existing2048-byte
misc BCB boot-mode request and clear are permitted. Never issue mainline
`reboot recovery` (the known SDAM trap). Verify recovery identity before reading
or returning. No Debian filesystem mount from recovery is needed.

Readiness is bounded90s per transition, one attempt only; recovery transport
admission reuses the existing8s/three-snapshot gate. Once a known recovery is
established, return once even if a field is missing, malformed or different.
No blind return after loss of identity/ADB. All new CPU/kernel/Code43/safety
faults stop. The passive observation bounds remain20–100%,10–<42°C,
3.4–4.45V;4.44V float setpoint is unchanged. Keep PC USB connected; no charger
swap or Wi-Fi requirement. Normal graphical startup must be restored.

Read-only preflight: boot/config/notes/DCC/181modules/five partitions/desktop/
ordinary battery/ADB/device NCM/full kernel journal/noCode43. Source/hash
registration and preflight must be committed/pushed before the BCB request.
Return: unique new Debian boot in bounded history, exact unchanged five
partitions/config/notes, normal desktop/ADB/device NCM/battery and full kernel
health. Modules/config are never written. No long repeated sensor window.

Pure comparison/cleanup host tests and existing mapping/recovery dependencies
are selected directly. No routing change, full regression, kernel build or
GitHub Actions. Full/omitted builds executed:false. `SOURCE_AUDIT.json` names
actual Samsung/Fedora inputs and hashes; Fedora remote HEAD still equals the
audited ab123e7d snapshot.

Matching fields eliminate a demonstrated input mismatch at this boundary,
**not** other SNS initialization issues. Differences are retained for source
analysis, never automatically repaired. Either result remains insufficient for
sensor/automatic-rotation acceptance. Test393 and its seals remain unchanged.
