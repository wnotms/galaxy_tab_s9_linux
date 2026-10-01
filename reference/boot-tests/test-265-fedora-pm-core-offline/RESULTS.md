# Test265 — offline Fedora-derived PM core qualified

Source0da8e89a25b57d85cbdc088add0b1483310a2199. Port Fedora X710 ab123e7d
sm5440_pm_notify() exit order into the existing unwired transaction core:
suspend independently latches PM cancellation and revokes grant before checked
OFF/fixed/physical-measure/switching restoration. Start cannot reuse old facts
while suspended. Resume requires a quiesced SWITCHING/uninhibited/unarmed state;
it never re-arms, schedules a worker or requests the old PPS contract.
See docs/X710_FEDORA_PM_PORT.md for caller serialization/lifetime boundaries.

Unlike reference unchecked restoration, every failed exit propagates and blocks
resume. Invalid adapter cannot claim pumpOFF. Epoch loss never restores a
contract on a new connection. This is a pure transaction API; no live PM notifier,
worker, hardware ON API, APDO advertisement or PPS request path was connected.

Actual C38 development tests pass, including10 new PM tests. One full1369 host
run passed, zero failures/errors/skips (128.781s); all prior1351 IDs retained.
Isolated ARM64 Image.gz/DTB/modules build passed, Linux7.2-rc3/clang21/ccache/JOBS8.
181 matched regular module files exactly match archive; embedded config/source
and kernel notes audited.85 Docker/UPower requirements/DCC/96 protectedfiles
retained. W=1/compatible sparse pass; only previously known upstream VDSO
missing-declaration warning retained; changed object hash remains identical.

Exact config diff versus installed Test263: only X710_CHARGING_POLICY n->y,
with byte-identical DTB (empty diff). The audit's older Test255 comparison also
shows the already accepted passiveSM5440 node/profile; it is not a new Test265
DTS/hardware enable change. No config fragment or DTS changed. No unrelated CPU,
GPU, USB, charging current/protection/thermal or adbd change. Same frozen images
remain intact; new outputs under out/kernel-x710-265-policy.

Initial precommit artifact audit named the registration revision before code
commit and rejected two compiled-source identities. Its report is retained;
the new build source hashes already matched working code. Final audit against
committed0da8e89a passes. This was host attribution setup, not an unsuccessful
kernel build/device failure; no repeated build or host suite was needed.

No device command, flash, reboot, module replacement, physical suspend, PPS,
pump activation or current escalation. Installed Test263 device acceptance stays
complete, exact Test260 rollback remains. No physical Test265 acceptance claim.
ActiveStage3 NOT READY: actual ADC/current/protection and live PM adapter remain
separate gates. Offline qualified means this PM code is compiled/host-tested;
it does not qualify physical direct charging. No automatic next physical test.
