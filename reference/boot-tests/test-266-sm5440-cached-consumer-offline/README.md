# Test266: passive SM5440 cached consumer API (offline)

Start test HEADbc2900a2; device remains accepted Test263. Fedora X710 ab123e7d
sm5440_get_adc()/wait_vbus_settled() informs the consumer, with Samsung X710
ADC control/map as hardware authority. This increment exposes the already
completed passive sample coherently, never creates an active converter or
policy/ON/PD consumer. No device access/deployment/suspend/current change.

Add acquisition-start BOOTTIME milliseconds before existing ADC enable. It is
an oldest plausible timestamp, not later cache publication time or a new sample
on read. Public read-only API rejects >100ms/future/zero time, pending startup,
invalid/fault/stopped/unbound state, modeON and absent samples. Destination is
cleared on failure. No I2C on read, pointer escape, blocking wait, reschedule,
raw-register access, PPS or activation API. Existing1s polling/2500ms passive
properties/debugfs/hardware operations stay unchanged. A100ms consumer may
return ESTALE between polls; that is refusal, not fresh acquisition support.

Lifetime: one short registry mutex -> io_lock; unpublish/drain readers before
debugfs/worker/devres teardown. Poll/PM never acquire registry mutex; no waits
or cross-device callbacks while these locks are held. Multiple providers are
rejected. Caller receives copied facts only; no provider memory reference.

Host-test actual C: ages0/100/101ms, invalid/future/unknown timestamps, pending,
fault, stop, unavailable provider, unchanged output/units, acquisition start
rather than publication, publish/unpublish lifetime, zero I2C and no lock-held
wait. Retain all existing tests. One isolated passive ARM64 Image/DTB/modules
build, full host run and driver W1/sparse. Exact config/DTB versus installed
Test263 must be unchanged;85 container/DCC and96 protectedfiles retained.
No on-demand sampling, independent ADC/OCP qualification or live handoff claim.
ActiveStage3 NOT READY. No physical Test266 authorized by this registration.
