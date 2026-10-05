# Native SM5440 hardware control boundary

This is the hardware executor for the unfinished X710 charging controller.
It is linked only by the separately selected `sm5440-native-control` profile
(`X710_NATIVE_CONTROL=y`, depending on `X710_CHARGING_POLICY`). The historical
`sm5440-policy-offline`, passive and converter diagnostic profiles retain their
previous control-call meaning. No device installation is part of this change.

`sm5440_native_control()` resolves the actual bound SM5440, pins its lifetime
for each operation and uses its existing uncached I2C regmap and `io_lock`.
No foreign provider/regmap pointer escapes. A monotonic instance plus session
generation identifies an owner; a released, old-generation or replaced-device
token cannot authorize another session. A failed claim may return a cleanup
obligation token; a negative return is never an admission grant.

Claim reserves the existing single-request slot, marks ownership, invalidates
passive requests and drains the ordinary delayed poll **without holding locks**.
An old poll may complete during this drain; its cache is invalidated again before
claim returns. Existing INT/ADC ownership is therefore not shared with control
or a second converter. A successful claim verifies pump OFF and ADC disabled.
Neither probe nor a timer/notifier calls the API.

The explicit operations bind the existing real settings, watchdog, converter,
actuator and supervisor implementations to that map. OFF preparation preserves
original register witnesses. Converter begin/advance perform one bounded
acquisition; `EINPROGRESS` is not a sample. A completed request may be followed
by a new explicitly requested acquisition, never by adopting an old READY.
The 100ms refusal/READY requirement is unchanged; Test321 RAW measurements are
not used as calibration, freshness or software-OCP acceptance.

**Native START, RESUME, PAUSE and active-monitor operations remain refused.**
The driver never sets its actuator's activation flag, source lease or validated
OCP grant. A caller-supplied `software_ocp_verified=true` cannot override that
boundary. Compiling the real helpers is not permission to energize hardware.
No userspace switch, writable property, automatic PPS request or pump start is
added. The final transaction/controller worker and its standard TCPM fixed-PD
fallback are still unfinished; this executor does not negotiate PD.

Unexpected conversion/hardware errors preserve the first operation error and
latch a driver fault. Terminal cleanup attempts checked pump OFF first, then
restores ENHIZ/watchdog/settings and cancels/restores the converter. If OFF is
uncertain, settings/watchdog ownership remains; no lower-voltage grant, ordinary
poll restart or hidden second OFF retry occurs. Releasing a clean session can
restart only the old OFF poller; repeated release performs no I2C or requeue.
Cleanup errors remain separate from the original operation error.

PM invalidates the native generation before draining. A clean native teardown
releases hardware ownership; resume may restart ordinary OFF monitoring but
never arms charging. Uncertain teardown vetoes suspend/resume. Unpublish removes
the provider and waits for in-flight operation pins before devres cleanup.
The historical `sm5440_quiesce()` implementation is byte-identical; a separately
compiled native wrapper performs this additional ownership cancellation.

Lock order: lifetime registry **only to pin/unpin**, then release it; the
single-request reservation spans drain; `io_lock` serializes bounded regmap
calls. No registry/`io_lock` is held over work cancellation, PD negotiation,
VBUS wait or another supplier call. No new millisecond sleeps are introduced.

Host tests execute the actual driver session, PM and unpublish bodies together
with the six real hardware/policy C units on a mocked bus. They cover lifecycle,
old tokens, ordinary-reader exclusion, cache republication, delayed unpublish,
PM during claim/conversion, malformed requests, timeout, every I2C call failure,
uncertain writes, exact restoration and terminal retry refusal. These tests
establish software behavior only, not physical ADC timing/OCP or direct charging.

Future device validation must separately register an OFF-only native ownership/
settings/acquisition/restoration candidate with accepted311 rollback and rescue
checks. Pump/PD activation remains a later acceptance, requiring actual current,
conversion, protection and cutoff evidence; no candidate is flashed here.
