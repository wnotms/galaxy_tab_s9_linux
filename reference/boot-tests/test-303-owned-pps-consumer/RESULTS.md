# Test303 — actual owned PPS consumer, offline qualification

**OFFLINE_OWNED_PPS_CONSUMER_QUALIFIED**, source `53f223cf`. Device stays
retained Test299/Test300. No device command, flash, reboot, PPS request, pump
activation, rootfs/adbd/USB or ordinary-current change in this qualification.

The explicit kernel consumer integrates real standard pack properties,
strict100ms fresh SM5440 OFF-mode acquisition, checked switching lease and
the actual TCPM PPS/fixed APIs. It preflights the fixed9V source/APDO/pack
before ownership, rechecks after acquisition, requests PPS once, acquires
physical VBUS evidence and returns immediately to fixed. This is executable
provider integration, not a second mock-only policy engine. It has no timer,
auto-start, userspace switch or pump ON path. Source capability and negotiated
limits remain distinct from actual physical measurement and protection.

PM prepare sets cancellation before draining the single consumer mutex.
Cleanup may leave PPS for the same source despite cancellation, but never
starts a new PPS call. Native failed restoration is not automatically retried: a
read-only fixed snapshot must prove native cleanup succeeded before continuation.
First errors and cleanup errors are reported separately. Unresolved ownership
blocks another attempt and suspend; PM post does not clear the fault or rearm.

Fresh physical proof and exact provider/source/budget are checked under the
TCPC gate before try-only battery authorization release. No IIO/I2C or producer
wait is added under that gate: the unchanged poller performs ordinary thermal
checks/Q4 programming afterwards. This avoids the actual pinned thermistor's
possible501ms conversion timeout in a transport lock. `switching_released`
means authorization released, not evidence of completed Q4 programming; the
future device endpoint must observe ordinary charging separately. Original
synchronous release and fixed-path functions are unchanged.

568 unique affected host tests pass: initial559 in16.289s, then57 final
consumer/release/ownership tests, reusing511 unaffected results. No skipped,
failed or errored final tests. Actual C uses real threaded mutexes/PM drain
with faulted framework/hardware providers; production physical ADC/TCPM
behavior is not established by these mocks. Existing assertions retained.
Unknown-file routing preview selected1719 conservatively; latest owner scoped
workflow instead ran the affected charging/build/container/discovery tests,
without weakening router rules or claiming a full regression. Raw initial
fixture failures and corrected tests are preserved.

ARM64 Image/DT/modules build passes91.651s. W=1/C=2 sparse passes8.435s
on battery/TCPC/consumer, with objects and linked vmlinux byte-identical.
No changed driver warning; unchanged upstream vDSO declaration warning retained.
Checkpatch has0 errors, one new-file MAINTAINERS advisory and two brace-style
checks; these are recorded, not represented as a clean style check.

The existing explicit `sm5440-policy-offline` profile compiles the real OFF
consumer. Test302 -> Test303 has exactly CONFIG_X710_CHARGING_POLICY n->y,
no unexpected resolved delta, and byte-identical DTB. Default/passive profiles
do not compile/arm this consumer. HVC_DCC remains n, Docker/UPower retained,
96 protected files/frozen Stage2 artifacts unchanged, ten compiled overlays
and four shared-header copies match source,181 paired regular module files
and archive verified. Large artifacts remain in `out/kernel-x710-303-policy`.

To avoid another4.7GiB D: cache clone, reused the retired301 cache only after
archiving and verifying2731 generated/debug inputs, including exact vmlinux,
config and Module.symvers. Old301 cache path is no longer a provider; restore
its recorded inputs/rebuild if needed. Old301/302 formal artifacts and rescue
remain hash-identical. New303 archive/provider must be used for future consumers.

Physical PPS/direct charging is **NOT READY**: current passive startup
refusal/ADC validity and>100ms acquisition remain unwaived blockers. This
consumer refuses such evidence before acquiring switching ownership. Next
inspect source-backed ADC operating conditions (vendor initialization versus
the minimal passive converter), then fix a demonstrated prerequisite and
register one purposeful pump-OFF physical scope. Do not replay an unchanged
failed delay profile or use logical VBUS/restamped cache as physical proof.
Active actuator/protection/OCP/full coordination and physical acceptance remain
required for the complete wired-charging port. No Actions/CI or auto-deployment.
