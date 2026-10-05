# Native charging observation worker

This is the data-acquisition part of the future live charging adapter, compiled
under the existing `X710_CHARGING_POLICY` profile. It does not complete the
direct-charge controller. The accepted311 device baseline remains installed.

The worker calls the actual SM5714 source and pack providers and the existing
SM5440 **OFF-only fresh acquisition** provider, then repeats pack/source reads.
Source instance, source generation, budget generation, PDO set, battery instance
and battery state generation must remain unchanged across the acquisition.
Each provider's original BOOTTIME acquisition bracket is retained. The oldest
source/pack read must be within500ms; physical acquisition must meet the existing
100ms refusal gate. A RAW diagnostic observation is never substituted.

An ordinary request uses no switching lease and observes only fixed5V/9V.
An owned request supplies an exact instance/source-generation/lease tuple and
uses the real owned PPS observer. It neither obtains ownership nor requests
PPS. A partial owner tuple, invalid measurements, source change, battery change,
timeout, PM cancellation or unavailable provider clears the entire result.

One ordered workqueue handles explicit kernel requests. No timer, power_supply
notifier, userspace interface or automatic request is installed. Requests contend
on a consumer-only try-mutex; a timed-out operation remains marked in flight
until the worker completes, preventing a second ADC request. A local generation
invalidates late publication. PM sets the cancellation latch before draining
work; resume clears that latch without restarting work. Provider locks and the
short publication mutex are never held across cross-device reads or waits.

This observation contains no charging authorization. Software-OCP acceptance,
physical conversion age/calibration, live actuator/monitor integration and
transactional fallback remain separate unfinished requirements. Test321 proved
raw register transport only; it does not satisfy those requirements. No pump
enable, charger inhibition, PDO/APDO request, protection write or retry is added.

Host tests execute the same C worker, collector, request and PM functions with
threaded providers and injected failures. ARM64 compilation must demonstrate
that the worker and native provider references are actually linked. Qualification
also compares resolved config/DTB and protected source hashes; no device test is
part of this offline change.
