# Test311 — offline registration

Verdict: OFFLINE_SERIAL_COLLECTOR_REGISTRATION_READY. Physical test **not executed**.
The previous Test310 STOP and exact299 restore are preserved. Timeout cause is
unknown; no CPU-wedge cause or ordinary device acceptance is inferred.

The actual host runner now collects identity, real-pack thermal, provider-bound
charger controls and full kernel evidence before boot-history/Windows/NCM metadata.
ADB operations are serial; one boot-history query is limited to20s. Missing
history remains a failure. Existing safety limits, readiness, one ordinary
recovery<=5s, unique attribution, 15s endpoint and exact299 restore gates remain.
The previous provider reader and gate are byte-identical. No kernel/config/DTS,
USB/adbd/rootfs, charging current, PPS or pump change.

Final affected host validation: **35 PASS**, 0.145125s;
zero failures/errors/skips. Tests execute the new runner with mocked transports,
including actual provider fixtures, unsafe controls, missing history, serial
ordering, lifecycle/restore and acceptance gates. Syntax checks passed.
The initial incomplete staging fixture error is retained in
validation/development.json and is not reported as a pass.
No new build or full host run: exact Test308 kernel/artifact qualification reused.
No routing/old tests changed; no Actions started.

136 registered source inputs sealed; all125 inherited Test310 inputs
unchanged. Seven Windows stage files match hashes; six share existing Test310
hardlinks and only the unique311 module helper is new. No large artifact copy.
See validation/stage-reuse.json and validation/runner-diff.patch.

Last historical restored boot788fef75 runs accepted299, not this candidate.
Fresh normal/safe production preflight is mandatory before a future authorized
run. No Test311 device acceptance or ADC/PPS/direct-charge qualification claimed.
Physical ADC validity, active protections/actuator, handoff/fallback and PM
acceptance remain outstanding; full Stage3 is NOT READY.

Expired images were deleted separately; exact manifest:
reference/host-storage-cleanup/2026-10-03-test311-image-retirement/.
