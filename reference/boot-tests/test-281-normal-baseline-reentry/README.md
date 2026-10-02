# Test281 — one normal Test263 baseline reentry

Owner continues after Test280. Preserve280STOP and manual-boot explanation.
This independent test answers only whether **one ordinary warm reboot**, without
changing installed software, returns the bootloader-supplied command line to the
already accepted normal Test263 form. It is not a fresh ADC attempt, trace
experiment, charging test or reliability proof.

## Admission and frozen software

Incoming cmdline must exactly match the owner-explained Test280 lpcharge profile;
this is an incoming reboot condition, **not** an exemption for the future trace
test. Test263 embedded config/notes, five partitions and181module hashes are
verified once before reboot. Battery/OFF/PCSDP500/health, same-boot authenticated
Wi-Fi, native ADB, device NCM and no Windows Code43 are prerequisites.

No flash, module replacement, tracefs write, observer load, kernel/config/DT/
rootfs/USB/ADC/current/thermal change. DCC remains absent; PPS/pump ON forbidden.

## Single action and endpoint

Commit/push registration BEFORE `systemctl reboot`. Save old boot ID/history,
then issue that command once. Wait up to180s for a read-only shell; shell
disconnect does not prove success. Require one changed boot ID and uniquely
attributed journal history. Collect one full kernel journal and endpoint health.
Use the existing strict gate with the exact accepted normal cmdline. Record a
second health endpoint15s later on the same boot; this is a bounded reentry check,
not a stability acceptance window. Wi-Fi/ADB/deviceNCM and Code43 gates apply.

Any cmdline/identity/health/rescue/kernel mismatch, extra boot or missing evidence
stops Test281. **No second reboot, auto repair, flash or trace attempt.** Missing
initial readiness is recorded; only bounded boot readiness polling is allowed.
Rollback is not needed because installed software is unchanged.

Documentation/results-only registration uses frozen275/277gates and28024-test
qualification: new tests/build/full/CI executed:false, not a new regression pass.
If normal baseline is recovered, future passive tracing still needs its own
accepted registration/paired deployment/rollback; nothing is loaded by281.
