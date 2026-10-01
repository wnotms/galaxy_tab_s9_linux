# SM5440 fresh passive request design

Test271 confirmed passive monitoring at lower battery voltage, not active-current
readiness. Test266's copy-only cache can be stale between1s polls. Test272 adds
an OFF-mode kernel acquisition request; it does not enable direct charging.

[VENDOR] Samsung X710 set_adc_mode()/convert_adc(), and [FEDORA] ab123e7d's
physical-ADC VBUS settling, supply the hardware provenance. Preserve our existing
converter register sequence and fault latch retention rather than guessing faster
averaging or channel selection. [MAINLINE] use pinned7.2-rc3 workqueue,
waitqueue, atomic lifetime references and short mutex state sections.

## Contract

`sm5440_passive_request_fresh(out)` is sleepable, kernel-only and single-request
per provider. It requests the existing worker and waits at most the remaining
100ms software budget. Only a new completion with acquisition start after the
request and age/delivery within100ms can succeed. A conversion already started
before the request cannot masquerade as new. No cache lookup changes timestamps.
IBUS stays microamps, voltage microvolts, die temperature deci°C.

A request can fail because the unchanged32-sample averaging/300ms converter
budget or scheduler/I2C operation exceeds100ms. In-flight I2C cannot be preempted;
this is a delivery validity guard, NOT a wall-time/cutoff promise. A timed-out
read does not cancel the ordinary monitor or clear a latched fault. Default poll
behavior has no new requests unless this kernel API is explicitly called.
No userspace writer/activation interface or live policy adapter is supplied.

## Locks and lifetime

Registry -> io_lock is still the copy-only cached API's short lock order.
Fresh request pins an atomic user under registry, releases registry, then uses
trylock io_lock for checks/queue/copy. It never waits on io_lock or holds it across
converter/PD waits. One request reservation under io_lock rejects another caller.

Unpublish removes the pointer under registry and marks dying; it then wakes
requesters and drains users without registry/io_lock held. The final user signals
its drain waitqueue before teardown may free state. PM sets stopped and invalidates
cache under io_lock, wakes requesters, then drains the existing worker without
io_lock and verifies OFF/ADC disable. Thus a request cannot queue work after PM's
drain. Resume never resumes a request or carries its deadline/grant forward.

Worker completes state/sequence under io_lock then wakes requests. Snapshot and
startup/fault handling remain identical; rejected/failed requests never modify
raw sample provenance or authorize ON. Existing300ms worker can continue after
a requester timeout, and normal1s scheduling continues unchanged.

## Verification boundary

Mock/host execution verifies sequence, times, units, failures and ordering; ARM64
build/static checks verify integration. Passive physical API timing, nonzero
current and independent calibration remain untested. No actual hard cutoff or
active-mode sampling is claimed. An active adapter still needs its own supplier
lifetime/PM contract and protection qualification before PPS/pumpON. Fixed5V<=1.8A,
9V<=1.5A,4440mV, thermistor fail-closed and USB/ADB are frozen.
