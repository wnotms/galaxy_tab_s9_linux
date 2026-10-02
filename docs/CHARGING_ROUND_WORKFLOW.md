# Charging round execution with less repeated work

Latest owner instruction2026-10-02: prioritize short physical rounds and check
only modified parts/dependencies; avoid lengthy repeated review/full regression.
Reuse qualified candidates and ask a new concrete hardware question per round.
The detailed historical trace profile below is not a mandatory template for
every charging test; register the minimum evidence appropriate to the new scope.

Owner instruction2026-10-02: accelerate each round. Follow
`HOST_TEST_WORKFLOW.md`: reuse qualification for unchanged source/artifacts;
normal device behavior completes the registered device scope. A host-only
display/parser issue is recorded separately; it does not authorize replay or
relax a real identity/safety/transport failure.

## What the last round actually spent

Test282 recorded116 commands: their durations sum to52.35s. Record endpoints
span888.91s, including boots, readiness waits and orchestration gaps; this is
not an estimate that all remaining time was removable. The Windows USB checks
each took about4s. Recovery state misclassification alone caused45.948s of
unnecessary polling after native TWRP `recovery` first appeared.

Therefore target repeated orchestration and waits, not safety limits. Test283
provides a mock-qualified `wait_recovery` that returns immediately on native
`recovery`/`device`; a TWRP identity check is still required. It is not yet
hardware-qualified. There is no promised fixed duration for an entire round.

## Next independently registered physical round

1. Prepare/review artifacts, portable tools and rollback files together. Run
   affected host tests once after edits settle; reuse the exact kernel build,
   config/DT/module audit and full-suite qualification. Save registration and
   push before any physical mutation.
2. One combined live admission packet: boot/config/notes/cmdline, battery,
   healthy passive OFF/protection cache, services/roles/USB/NCM. Authenticate
   Wi-Fi boot ID and obtain Windows Code43 evidence concurrently where they
   are independent reads. Save full journal/history at the boot boundary.
   Require all gates, never interpret missing evidence as pass.
3. BCB helper uses command-local TMPDIR=/tmp. Ordinary `systemctl reboot` only.
   Use native recovery readiness, stop polling as soon as it appears. Verify
   TWRP identity/partition sizes and original baseline **once** before writes.
   Verify staged hashes and paired boot/modules at deployment/readback.
4. Group deployment/readback/candidate admission as a planned stage. Preserve
   every raw command; do not insert a manual review/commit between individual
   commands. Commit/push each completed meaningful stage, not each check/file.
   A script must fail closed at each gate. Recovery/cleanup on a failure takes
   precedence over waiting for a network push.
5. Obtain candidate current packet once, then collect independent full journal,
   history, authenticated Wi-Fi and Windows evidence concurrently. Confirm a
   unique new boot and all identity/safety/rescue conditions before acquisition.
   Use Test283's bounded ADC_UPDATED classification only in a newly registered
   profile, preserving Test282's original STOP and unresolved REVBLK cause.
6. The existing single-process279/280 coordinator owns one observer load,
   cached capture, trace cleanup and unload. It avoids repeated ADB shell
   polling. First refusal stops immediately; the fixed500ms trace tail remains.
   Keep max30s/8calls/100ms refusal budget and raw trace/loss/miss/boot checks.
7. One endpoint packet and full kernel journal. Do not fetch full journal or
   rehash unchanged rollback modules for every sample. Keep ADB/authenticated
   Wi-Fi/device NCM and Code43 checks at actual attach/boot boundaries; device
   NCM acceptance does not require another Windows TCP retry series.
8. Perform the registered unconditional exact263 rollback once. Verify allfive
   partition hashes and181originalmodules at readback, then one final boot/
   identity/health/rescue endpoint. Do not repeat hashes after an unchanged
   boot. Reuse qualification, seal new raw evidence and commit/push results.

No artificial pause after a passed gate, no duplicate wrapper/changed/full
test run, no repeated kernel build for host-only changes, no re-acquisition
because of a host-only output error. If preserved raw evidence resolves that
error, analyze those bytes instead of replaying a physical operation.

## Checks that remain mandatory

Exact paired identity and safe backup/write/readback; current battery/thermal,
pumpOFF/fault0/protection and USB rescue; unique boot attribution; kernel fault
gate; trace completeness/cleanup and unload; failure evidence; registered
rollback. Unknown device state remains STOP. Actual observation windows,
deadlines/current ceilings and first-failure behavior cannot be shortened or
relaxed as a workflow optimization. No PPS/pumpON/current escalation is implied.
