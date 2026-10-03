# Test310 — registration and collector qualification

**REGISTERED_PROVIDER_COLLECTOR_READY_PHYSICAL_NOT_EXECUTED**.

Exact qualified Test308 kernel and paired package reused; no kernel/build
input changed, no new build/full regression or Actions. Only the independent
host observer changes: select the real battery provider and verify its bus
alias/binding/compatible instead of assuming global address uniqueness.

Host tests execute the actual new reader against real filesystem symlinks with
both2-0049 and7-0049, verify all seven atomic pointer/read messages and FD
cleanup, and refuse wrong/missing address/alias/provider/driver/compatible
before bus access. Inherited actual310 gate/preflight/admission/lifecycle tests
retain low-battery, identity, CPU/Code43, boot attribution, AICL, control/history,
first-failure rollback, no retry and retain-on-PASS rules. Exact results are in
validation/host.json and host.txt. Existing Test309 qualification is unchanged,
not presented as a newly executed full regression.

Seven staged hashes match the reused package and new helper; six files reuse
NTFS hard links. Source/provenance and registration inputs are sealed before
commit/push. Test309 result is STOP, accepted299 restored; no hardware acceptance
is claimed for Test310 at registration. Full wired charging goal remains open.
