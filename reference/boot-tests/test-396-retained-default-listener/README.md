# Test396 — retained default listener reference

Test395 X710 stock disassembly and Qualcomm primary listener code retain the
registration reference while servicing callbacks. f3220073 repairs only rpcd.c
in the otherwise qualified status69 daemon. This is a new lifetime experiment,
not an unchanged Test393 replay and not a proven SSC root-cause correction.

One early-ADSP boot, unchanged root→sensor launch order, two bounded PDR listener
cycles (2s registration +2s cleanup;8s host bound), 30s SSC observation. Report
SSC_ABSENT, SSC_PRESENT_NO_SAMPLE or SSC_PRESENT_WITH_SAMPLE; UP is not SSC proof.
Only if service400 appears, execute one accelerometer probe. No rotation acceptance.

Reuse Test382 early trace vendor, exact Test370 kernel/config/DT/181 modules,
stock assets and existing library. Eight namespace-owned overlay files; only
payload difference from393 is daemon49140bbd, library1be44d2f unchanged. Preserve
Test253 ADB, GNOME input, battery policy. No new kernel/image/build/fullrun/Actions.
PPS/pump/DCC OFF. No registry, firmware or hardware parameter guessing.

Essential preflight: ADB root, same enrolled boot, exact five partitions/181
modules/config/notes, battery20–100%,10–<42°C, VBAT3.4–4.45V, noCode43 or new
failed unit/kernel fault. First unknown/fault stops, no replay. Complete raw
kernel/unit/GLINK/return journals retained. Mandatory owned-overlay/assets and
exact Test370 vendor restoration, ordinary GNOME return regardless of SSC result.
Registration must be committed and pushed before any device mutation.

Reuse73 host/16 ARM64-QEMU/2 upstream component and86 PDR observer/domain cases;
16 new namespace/mock flow tests passed,0skips. Retention387–396; Test382 vendor has
an explicit current consumer, no new image copies beyond temporary Windows stage.
