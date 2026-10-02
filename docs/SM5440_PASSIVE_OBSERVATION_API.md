# SM5440 passive observation: separate acquisition from a charging gate

Design precedes the Test290 implementation. Test289 established a traced new
OFF-mode conversion with four completion polls, required final reads after the
request returned, and a refused100ms API. It does not establish an ADC worst-case
latency, independent calibration, a healthy active pump, or exact timeout branch.
Another identical trace or a larger `SM5440_FRESH_REQUEST_MS` would not resolve
those distinctions. Installed exactTest263 and the fixed-PD fallback stay frozen.

## Two independent contracts

The original `sm5440_passive_request_fresh()` / cached API remain byte-for-byte
unchanged, including100ms oldest-acquisition age and delivery refusal. The
unwired active transaction core retains its100ms ADC/monitor checks. No consumer
may substitute a diagnostic observation for that accepted fresh measurement.

New kernel-only `sm5440_passive_observe()` is **OFF-mode diagnostic telemetry**.
It requests the same worker, shares its single-request reservation, and returns
only a new conversion begun after entry and after the captured conversion
sequence. It reports original acquisition start, software completion, request
entry and final delivery timestamps, acquisition sequence, request epoch and
actual oldest acquisition age. It does not relabel completion as acquisition,
call a139ms-old measurement100ms fresh, or authorize PPS/pumpON.

Its500ms software collection budget is [BRINGUP_LIMIT], allowing one registered
passive observation to report a slow conversion rather than manufacture a fresh
pass. It is neither an ADC specification nor physical cutoff guarantee. The
unchanged worker requests at most12 sleeps of25ms (300ms nominal); this does not
prove it always completes by500ms. I2C/scheduling/user release can exceed the
budget: late delivery is rejected, output cleared, no retry or monitor cancellation.
The budget cannot be passed as an argument to the legacy/active APIs.

## Provenance and locks

A `completed_ms` timestamp is captured under io_lock immediately before copying
the fully checked worker sample into its cache; it follows ADC/status/OFF/protection
reads. It is a software completion bound, not physical ADC-ready time or exact
publication/wakeup instant. Original `acquired_ms` remains before enable, and
existing acquisition_seq prevents adopting an older same-millisecond conversion.
Zero, future, reversed or incomplete timestamps fail closed.

Registry -> lifetime user pin -> release registry; shared atomic request_busy;
trylock io_lock for admission/queue/copy; release before wait. Same workqueue and
worker, no second converter or new I2C access. PM advances epoch/sets stopped
under io_lock before drain. Unpublish removes provider/sets dying, wakes waiters,
drains users and retains its final registry barrier. No provider pointer escapes
or access occurs after final user release. Caller must be external sleepable
context, not the converter worker, teardown callback or locked charging/TCPM path.

I2C/ADC/fault/startup/PM/dying/busy/old-sequence/late delivery failures clear the
complete destination. Faults stay latched. A timeout leaves ordinary monitoring
intact. Existing startup classification, converter writes/averaging/channel,
12polls,1s cadence, pumpOFF and protection values remain unchanged. No userspace
activation/writer, rootfs/TCPM adapter or diagnostic auto-request is added.

## Validation and next physical scope

Execute actual C functions against mocked worker/clock/lifetime/PM, covering
Test289-like140ms completion with explicitly old age,500ms boundary/late release,
old conversion, timestamp corruption, timeout, shared reservation, removal,
suspend/resume epoch and I2C error. Retain old100ms tests. Then one ARM64 build,
exact config/DT/protected-input diff, affected and final full host regression.
No repeated build/suite for prose-only results. Test290 is offline; no device
commands/flash/reboot/modules/PPS/current writes are permitted.

A future separately registered single passive call can validate these timestamps
on hardware with pumpOFF and exact rollback; it is not100ms/active acceptance.
Independent calibration, nonzero-current/protection, real-time active sampling
and transactional PM remain gates before any pumpON/PPS integration.
