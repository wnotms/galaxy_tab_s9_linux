# Retained native session: irreversible cancel and queue-failure drain

Design precedes implementation. The native grants remain closed; tests use only
private mock grants. This is not a physical OCP or pump acceptance.

## Concrete defects to reproduce

`x710_charge_controller_cancel()` marks cancellation and schedules the retained
session's immediate periodic callback. Before that callback runs, another request
could cancel it before this fix and clear `x710_controller_cancelled`, reviving the same
active epoch. Status must not imply cancellation is irrevocable when admission
can revoke it. Reject new controls while an active cancelled session awaits drain;
STOP itself must not erase that existing terminal obligation.

Admission cancels periodic work before attempting to queue the requested worker.
If `queue_work()` refuses during an active session, the API returns EBUSY but does
not restore monitoring or schedule exit. The old retained pump/ownership can be
left with no scheduled observer. Keep the EBUSY return visible, mark cancellation,
and immediately schedule the existing terminal callback on the ordered queue.
This callback uses the existing OFF → fixed physical proof → lease-release path,
not a retry of the refused command. Failed OFF still prohibits voltage/release.

No change to normal timing, source/pack/current/thermal limits, TCPM, native
hardware executor, private activation/OCP flags, DTS or rootfs. No new lock or I2C
operation in admission. Queueing under the publication mutex is existing practice;
the callback does I/O after unlocking. PM already drains/vetoes unresolved active
ownership, including an emergency callback cancelled during suspend preparation.

## Test method

Use the real controller/core and the existing threaded ordered-workqueue shim.
Pause execution after an admitted mock active session, cancel it, attempt every
new command before the cancellation callback, and prove refusal preserves the
pending callback/epoch with no supplier calls. Inject refusal of **only** the
regular request worker (retain existing global queue-failure tests), prove an
immediate cleanup callback remains queued, reject a second request before drain,
and verify exactly one OFF/fixed/release with no second ON/Request/monitor restart.
Include failed hardware OFF and suspend draining queued emergency cleanup.

Mocks prove software ordering and the missing path; they do not establish a
naturally occurring queue failure, physical response timing or current safety.
Build once with the existing native cache, identical resolved config/DTB and
paired modules. Run only affected controller/mock tests; reuse unchanged provider
and pure-policy test qualification by exact protected hashes. No physical action.

## Qualified implementation

Admission now refuses an active cancelled session before it can cancel periodic
work or clear cancellation. Active request queue refusal keeps EBUSY visible,
marks cancellation and schedules the existing immediate terminal callback. No
new retry, recovery state, lock or supplier call is added. The private activation
and OCP grants remain false. Actual-C mock evidence and build qualification:
[results](../reference/charging/x710-cancel-drain/RESULTS.md).
