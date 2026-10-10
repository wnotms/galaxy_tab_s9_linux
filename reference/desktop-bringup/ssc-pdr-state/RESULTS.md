# Sensor PD state observation: host qualified, not deployed

Test390 proved a native mapper advertisement for `msm/adsp/sensor_pd` instance74,
not its execution state. Its complete same-boot QRTR inventory advertised the
corresponding notifier: service66, version1/instance74, node5/port3. Those old
addresses are offline fixtures only; deployment must select a unique endpoint
from fresh complete inventory and domain evidence bound to the actual boot.

The new independent `servreg-state-snapshot.py` follows the actual Linux7.2-rc3
PDR schema. `PRIMARY.json` pins the inspected source files and tree revision.
Method0x20 REGISTER_LISTENER takes enable and a raw top-level path string; its
response has a mandatory QMI result and an optional four-byte current-state
enum. UP, DOWN, EARLY_DOWN, UNINIT and LOCATOR_ERROR are distinct results.
Service64 is the locator; service66 is the notifier; service69 is unrelated.

This is **not a GET_STATE operation**. It sends enable=0 once on a freshly bound
private QRTR client: unregister only that client, read optional current state,
and close. No subscribe/ACK/restart or DSP activation is implemented. The kernel
accepts a boolean but currently calls the helper with true. Whether the firmware
supplies state for false is **not verified**. Missing state, rejection, unknown
enum, malformed/foreign reply, timeout or boot change cannot prove domain UP;
there is no automatic retry or escalation to enable=1. UP itself proves neither
SSC publication nor an accelerometer reading.

30 new tests and20 existing domain snapshot tests PASS, zero skips. Literal wire
fixtures, actual Test390 inventory selection, optional-state absence, invalid
results, deadline/peer/boot checks, socket errors and closure are exercised.
`HOST_TESTS.json` records exact IDs. No kernel build/full regression/Actions;
no device query, rootfs change, reboot, charge policy or USB change in this
qualification. Existing tests and historical Test390 evidence remain unchanged.

Next physical scope must register/push before mutation: one early-ADSP boot,
at most one pre-start and one post-start private-client query, one ordered RPC
startup only when the initial response is valid, bounded health observation,
then exact Test370/GNOME restoration. Unknown initial state stops before RPC.
Do not repeat unchanged Test390 or claim sensor/automatic rotation completion.
