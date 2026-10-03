# Test310 — registration and collector qualification

**STOP_BOOT_HISTORY_CAPTURE_TIMEOUT_ACCEPTED299_RESTORED**.

One physical candidate attempt followed the pushed registration. Baseline
provider-anchored controls were verified before any mutation: Q4ON,input500mA,
fast500mA,float4440mV. Allfive/181 identities matched; candidate boot/modules
were installed/readback-verified and normal boot
`c9663df0-eafc-4487-b426-9051ed85c477` passed current-state identity/pack/rescue.

The parallel `journalctl --list-boots` ADB operation timed out at10.014s.
Current-state capture succeeded in0.292s and full1064-row kernel JSON in1.279s.
Offline classification found no matched CPU fault; existing passive startup
confirmation refusal remains explicit. This does not prove the timeout's
cause, complete attribution or candidate control/endpoint acceptance. Candidate
stable-control collection was not reached; the scope remains STOP.

The subsequent failure kernel capture and target history query succeeded in
0.154s and0.153s. Automatic cleanup restored exact299 boot/181 modules once,
checked allfive hashes and cleared BCB. Final attributed normal boot
`788fef75-722a-4243-8ad1-9e0b3a16269c` has42%,3.815V,30.2°C and device ADB/NCM;
final history took7.627s and completed. `rollback_required=false`.
Host NCM SSH255 is recorded separately. No PPS/pump/current change.

Do not replay Test310. The next host collector should run essential device
checks before expensive metadata/host probes, serialize commands sharing ADB,
and give the single boot-history operation an explicit bounded deadline.
This must retain actual boot attribution, CPU/journal/control/thermal gates;
it is not permission to call missing history CLEAN. No kernel rebuild is needed.

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
