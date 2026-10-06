# Test331 — corrected PPS adapter default-OFF device acceptance

Owner asked to continue testing2026-10-06. Source1f1d8568, qualification11c5967f.
Reuse187 affected tests, standard ARM64 build83.454s, W1/sparse13.115s, zero
config/DT change from tested Fedora and paired181 modules. No rebuild/full run.

One purpose: accept the changed kernel's default-OFF PC startup and30s ordinary
charging. **No PPS request, pump activation, charger/cable-removal stage, current
increase, ADC change or release-proof relaxation.** The independent physical
fixed9 return timeout remains unresolved; this cannot validate active PPS.

Combined baseline admission: exact323 config/notes, normal ordered cmdline
(tokens including duplicates/order retained, whitespace is not identity),
SOC20–<95%, VBAT3.5–<4.4V, real pack20–<38C, physical CNTL5 OFF, Sink/Device,
ADB/authenticatedWiFi or PC-only NCM rescue, no Code43, full journal/history.
Allfive partition/181 module baseline is checked once; fresh packet again at
mutation boundary, preflight age≤600s. Register/commit/push before recovery.

Verified TWRP: stage hashes, paired181 swap with **unique331** original/stage/
tested slots (never consume327tested), boot-only write, allfive readback/181,
BCB clear and unmount; one normal candidate boot, readiness≤90s and unique
journal attribution. Require exact candidate config/notes, direct_charge=N,
new sm5440-fedora provider and atomic read-only CNTL5 OFF. Four pack/OFF samples
across30s, positive PC endpoint battery current, device NCM and no kernel fault.

Retain only after actual device scope PASS. First actual device fault stops and
restores exact Test323 boot plus saved331-original181 with allfive/BCB/unmount/
one final attributed boot. Missing identity/rescue or unknown OFF is STOP; lost
transport requests manual TWRP, no blind repeat. Host-only publishing defects
are recorded separately; no repeat physical window after completed device gates.
Rollback is available and does not need execution on default-OFF scope PASS.

Unchanged Test327 mechanics are copied into a fresh namespace; only ordinal,
package/config notes, ordered-token whitespace comparison and explicit slot
refusals differ. A mocked existing-slot test exposed that the old compound
`test A && test B && test C` can suppress `set -e`;331 checks each slot in its
own simple command before any rename. Original failure log is retained. No kernel,
DTS, SM5714/USB/TCPM/adbd/rootfs or charging policy edits in this registration.
Windows staging D:\android\gts9-active\gts9-test331; native ADB remains
D:\android\platform-tools\adb.exe. Do not initiate PPS after this test.
