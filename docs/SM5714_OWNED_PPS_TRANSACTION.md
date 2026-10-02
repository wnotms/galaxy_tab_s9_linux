# Owned SM5714 TCPM PPS transaction

Planning baseline df9888a3/Test301. Device remains accepted Test299/Test300.
Implement the missing real standard TCPM operation and callback ownership, not
another offline policy engine. No live consumer/pump ON/physical test here.

Acquire the existing checked switching-OFF lease externally. A kernel-only PPS
operation requires exact provider/source identities, that live lease and caller-
proven pump OFF. Start only from stable fixed9V; use standard ONLINE=2,
CURRENT_NOW and VOLTAGE_NOW, with each intermediate pair validated against the
source APDO, existing 8.2–10.5V/1.8A initial PPS bounds and the connector's actual
operating power. Select current-first or voltage-first safely; refuse if neither
intermediate is valid. No core/DTS/capability changes, Source/AVS/EPR/PDO>board
limits, userspace activation helper or charge-pump operation.

A per-provider operation mutex serializes setters but is never taken by TCPM
callbacks. Exact current/previous target pairs authorize PPS RDOs only while the
source identity and switching lease agree. Check the companion lease outside the
TCPC lock, then revalidate under it before TX. Permission exists only during this caller-owned operation and closes before
return. Unchanged refresh must use this API again with pump OFF; unsolicited
requests are refused even if their pair equals the last accepted target. Invalidate the window on source/reset/detach/fault/charge-off.

Owned budget callbacks keep Q4 OFF and minimum switching input verified, retain
only the exact acquired lease and mark the contract kind. This is not a pump ON
grant. Ordinary callbacks retain their revocation behavior. Fixed return standby
uses Linux PD_P_SNK_STDBY_MW=2500mW (e.g.284mA at8.8V), and
is a distinct OFF-only state, never a releasable fixed grant; a PPS9V budget must
not masquerade as fixed9V. PM/fault/detach always revoke and retain inhibition.

On a mutating error attempt a single standard fixed return only for the same
current source and live lease; preserve the first error, log cleanup outcome,
clear authorization and keep inhibition. No automatic retry/release. Completion
requires double property reads, callback-kind/budget mirrors and unchanged
identities; these are logical observations, not physical VBUS or atomic upstream
TCPM state. Upstream completion timeout10s excludes swap mutex acquisition.

Actual physical fresh ADC/OCP/PM and full live coordinator remain required before
active charging. Future separately registered pump-OFF protocol test uses the
accepted rollback and physical voltage evidence; no spontaneous deployment.

The pinned TCPM SNK_READY state does not install a periodic PPS refresh timer.
A future consumer must schedule refresh within PPS requirements and stop the
pump before each API call. Do not claim TCPM alone supplies keepalive, or leave
an unrestricted window open while a future pump runs. Source/reset changes
invalidate even same-looking capabilities; stale restorers cannot revoke a
newer instance/source/lease. Accepted RDO V/I are recorded only after TX submit
and are compared with owned callbacks. STD standby is the sole explicit exception.

A new PPS9V/1.5A contract is marked programmable; equality of its numbers with
fixed9V/1.5A is insufficient for release. The ordinary budget API revokes when
kind changes as well as when numbers change. Existing baseline cases remain fixed.
No protocol snapshot or kernel-only lease proves actual ADC freshness/OCP/thermal
eligibility. Active charging is NOT READY and device software is unchanged.
