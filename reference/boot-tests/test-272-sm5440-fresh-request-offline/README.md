# Test272 — offline passive SM5440 fresh-request API

Purpose: provide one serialized, kernel-only request for a new OFF-mode physical
conversion using the existing worker, rather than restamping an old cache.
Starting HEAD20494199; installed device remains unchanged Test263.
No hardware command or deployment is included in this test.

The API retains an in-flight provider user while waiting, requests the existing
worker with zero delay, and accepts only a new sequence acquired after this
request with genuine acquisition age and total delivery time <=100ms. The
original converter (25ms polls/up to300ms), default1s cadence, register sequence,
startup classifier, protection, fixed charging and thermal behavior remain.
An older already-running conversion is refused; no automatic retry to clean.
Busy/startup/fault/PM/unpublish/deadline states clear the destination and fail.
A100ms refusal is NOT a hard-real-time execution or hardware OCP guarantee.

Use companion registry only to pin/unpin lifetime, never over a wait/I2C.
Use io_lock only for state/copy/scheduling. PM marks stopped under io_lock before
wake/drain, preventing a request queue after drain. Unpublish removes the provider,
wakes requesters and waits for their bounded functions to drop users before
freeing memory; no mutable provider pointer escapes. No new worker or ON/PPS API.

Host tests exercise actual C functions with deterministic worker/lifetime mocks,
including stale old conversion, sequence change, timeout, late delivery, stopped,
fault, pending, active mode, I2C failure, detach facts and publication/unbind.
Retain all historical tests. One final passive-profile Image/DTB/modules build,
W=1/sparse, config/DT/protected audit and full regression after implementation.
Results-only commits reuse that qualification. No CI. No automatic flash/reboot.
ActiveStage3 remains NOT READY pending acquisition on real hardware, calibration,
protection/cutoff, live adapter/PM and actual source APDO.
