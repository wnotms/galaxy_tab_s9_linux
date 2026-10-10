# Test397 — sensor-first observed; SSC absent; desktop restored

One candidate boot `65129696-de09-450b-863c-4d522465c5f3` completed the explicitly reversed
sensors-PD→root-PD startup. Persisted requested/active lists and complete unit
journal preserve actual order. The historical root-first helper is unchanged.
This differs only in ordering from396; stock early_hal/main declarations and
Fedora's absence of root-before-sensors dependency motivate the hypothesis,
not equivalence to full Android startup or a proven requirement.

Both RPC units remained active during the30s registered window (33.699s through
collection). Two standard PDR initial-state cycles returned UP, with verified
same-client unregister/closure. SSC400 remained absent, no accelerometer probe
was issued, automatic rotation remains unaccepted. Reversed launch order did
not restore SSC within this window. No physical retry/DSP restart.

35 config metadata entries and178 registry-content sessions match. One missing
oemconfig.so status69 acknowledged. Complete original unit/kernel/GLINK/raw
framing/content evidence retained; no detected CPU-stall/panic/Oops or new
severe kernel fault. Identical396 daemon/library, kernel/config/DTB/181 modules,
stock firmware/assets, native mapper and382trace geometry. No registry/firmware
or sensor hardware guessing; PPS/pump/DCC OFF.

Test370 exact vendor/assets/eight owned overlay restored, ordinary desktop boot
`9fb7e2f32d974459884b12f4c4f8b6a0` uniquely attributed. Allfive partition hashes/181
modules/config/notes/GDM/palm/ADB/device NCM gates pass, no failed unit or new
CPU/severe kernel fault in registered return window. No hostnamed gate failure
occurred in this round; original396 anomaly remains unchanged. Battery
100%,33.8°C,VBAT4.446V;
4.44V float unchanged. Device startup/return completed; sensor goal is incomplete.

39 affected tests passed before registration,0skips: new31 order/scope/actual
runtime wiring cases and8 retained root-first regressions. Existing73component,
16ARM64/QEMU,2upstream and86observer/domain qualification reused. No new kernel
build/full regression/Actions. Results tests executed:false.33 temporary Windows
files individually hash-verified/deleted; ADB folder retained. Registration seal
unchanged; results separately sealed. Retention388–397; no new kernel image.

Next compare firmware initialization/callback semantics with actual X710 stock
and same-model Fedora; do not repeat unchanged396/397, invent firmware calls or
reset factory registry. Full sensor sampling/desktop rotation needs its own
positive evidence. This result rules out only this bounded order experiment,
not every possible Android/mainline timing or dependency difference.
