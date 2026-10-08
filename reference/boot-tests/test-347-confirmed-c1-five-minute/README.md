# Test347 — confirmed-C1 five-minute PPS acceptance

Purpose: execute one300s conservative PPS/pump observation with fresh owner-confirmed C1 admission, preserving the qualified kernel and native/cleanup gates. Test346 closed at its900s human-handoff timeout without activation; never restart or rewrite it. This is an independent registration, not a retry of its consumed guardian.

## Candidate and safety

Reuse exactly source5c90a4b5, armed bootb6ac504e, modules4399bcc1, config51ba6a9c, notes10dcf27f and DTB233a9fee from qualified bounded-duration build. No new kernel/config/DT/SM5714/TCPM/USB/adbd/rootfs logic. Current device last accepted331a96de8c0; fresh live preflight is mandatory, not an assumed boot. Unconditional exact331/allfive/original181 restoration follows this attempt.

Exactly once=1 and once_ms=300000 opt-ins. Hardware1700mA, PPS request/rawIBUS stop1800mA, source/APDO voltage validation and all park/refresh/fault/thermal/PM/epoch/lease/OFF rules unchanged. Preparation/activationSOC20..70, entrypack20..<38C/VBAT3.5..<4.3V; runtimeSOC<80/pack<42C/die<85C/VBAT<4.4V. Fixed fallback5V<=1.8A/9V<=1.5A/float4.44V preserved. No20min/current increase/45W/calibration/hard-realtime or complete-port acceptance.

## Execution enrollment and sequence

**Execution enrolled under the owner’s still-unperformed one300s charging approval** (“允许测试，平板为手动关机重启”). Test346 terminated its guardian wait before any entry/PPS/pump activation and exact331 was restored. Test347 is independently registered with identical qualified artifacts/caps and host-only timing corrections; the existing grant is carried for that one actual test, without replaying Test346 or permitting extra activations. Both flags, scope and frozen inputs are refreshed and pushed before stage/install. A fresh347 candidate boot-bound C1 reply is still required; goal resumption alone is not permission for different current/duration/kernel policy.

1. Exact331 fresh PCpreflight and rescue, staged/provider hashes, one paired install and normalPCboot admission with unique boot history/allfive/181/notes/config/300000parameter. Drain the initial pre-entry worker; proveOFF/unbound before owner cable handoff. No guardian exists yet, and the unbound driver cannot activate while the owner pauses.
2. Ask for Lenovo YG65G C1 connection, C2 empty, WiFi retained/no reboot. Record a fresh reply in owner-C1-confirmation.json with test=Test347, current candidate boot_id, nonempty owner_reply and received_epoch. No test timer runs during manual cable waiting.
3. `start` requires that exact reply age0..120s, authorized scope, untouched prepared-OFF-unbound state and no prior guardian-start directory/STOP. Read-only sameboot fixed9/roles/source/pack/OFF proof precedes launch; recheck confirmation before launch. Device repeats admission before the sole bind, with token bound to the plan/current boot. It does not wait900s for a marker after starting.
4. Persist launch-request state before the only nohup. Remote shell saves originalPID before returning. A lost SSH response leaves start-requested-unknown-status: `adopt` only reads that savedPID and sameboot/path/terminal proof; it cannot launch or bind. A second start is denied, including failed prelaunch admission. Unknown/lost rescue requires cleanup/recovery, never blind replay.
5. `monitor` follows that PID, `collect` preserves original guardian/full kernelJSON/source timestamps and native300s/lease0/fixedreturn/OFF proof. SamePID may be reobserved after transport uncertainty; no restart/deadline extension. Only clean evidence permits ordinary fixed9 charge30s, then unplug/discharge15s, onePCreturn deviceNCM/ADB/noCode43 check. Restore exact331 regardless of verdict.

Commands: host_flow.py verify/preflight/stage/install/admit/start/adopt/monitor/collect/charge/discharge/pc-return/restore. There is no pre-owner `arm` or separate delayed `activate`. Adoption is observation of an ambiguous original launch, not another attempt. First native/safety/identity/kernel/evidence non-clean stops. Preserve primary and cleanup separately.

WindowsADB stays /mnt/d/android/platform-tools/adb.exe. SSH uses local WSL key and registered accepted public key via Windows-native TCP. Public known_hosts is now /home/ms/.ssh/gts9-test292-known-hosts, recreated only from the previously accepted exact public key if absent; wrong contents/symlink reject, no keyscan/trust relearning/private-key copying.

## Offline validation and limitations

60affected host tests pass:28new runner tests (19retained gate behaviors +9confirmed-start/trust/handle cases),19historical346 gate tests,8pure duration evidence,5Windows transport. Python/shell syntax and frozen artifact/provider checks pass. Reuse79actualC/build104.643s/W1+sparse15.691s; no rebuild/fullsuite/Actions/CI for host-only workflow changes. Matched module metadata remains mandatory even with unchanged runtime181.

No Test347 live preflight/Windowsstage/flash/PPS/pump operation yet. Test346 raw STOP/restoration remains unchanged. Retention338..347, expired337 images/Windowsstage retired with logs/config/DTB/notes/modules/source/hash retained. Full charging port NOT_READY. Only successful independently registered300s acceptance supports proposing20min later; this registration does not implement it.

Historical346 unauthorized fixtures now explicitly set execution_authorized=False, independently of the recorded owner grant. Their denial behavior is retained; no historical manifest/result is rewritten to bless the edited test. Test346 remains terminal and its original input gate rejects fixture drift.
