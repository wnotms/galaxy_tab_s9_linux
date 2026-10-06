# OFF-only fixed-return control qualification

2026-10-06, source48cc5d16; no new device deployment during offline qualification.
253affected actual-C/API/observer tests PASS5.910s, zero failures/errors/skips.
Standard ARM64 build PASS80.690s,J8/ccache/shared native-profile cache.
Changed Fedora object W1/sparse PASS12.810s, no warnings; standard object restored.
Resolved/embedded config51ba6a9c andDTB233a9fee byte-identical Test331 and fixed
window candidate. Kernel7.2-rc3 pin unchanged; all85 required symbols/DCCn intact.
181module file set/runtime/layout/symbol qualification; new notesff706409 and
matched archive in PACKAGE/SHA256. 841protected/history and30formal artifacts
preserved, including prior fixed-window/defaultOFF/rollback outputs.

Only Fedora driver changes: defaultfalse/read-only one-shot fixed_return_check,
mutual exclusion with direct charging, 300s deadline, source/pack admission,
checkedOFF/existingADCchannels0xdf/lease/pack recheck and existing fixed return.
Worker does not request PPS, initialize/reset charger, enable pump or raise
current; completion/refusal is terminal. Existing PM/remove drain owns teardown.
Proof log is emitted only after actual source-bound release succeeds.
Current baseline read-only CNTL5=01/ADCCNTL1=08/ADCCNTL2=df; no channel/ADC
algorithm fix. Unknown ADC channel setup refuses rather than reconfigures.

No config/DTS/TCPC/battery/TCPM/USB/adbd/rootfs/thermal/current/CPU changes.
No full suite/Actions or repeated build for documentation/runner. Full charging
port NOT_READY. New Test332 separately qualifies actual pump-OFF fixed9V return;
it does not validate a PPS voltage transition or sensor calibration.
