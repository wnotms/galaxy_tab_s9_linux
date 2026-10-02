# SM5714 standard TCPM fixed-contract restoration

This is a kernel-only protocol fallback prerequisite. It does not install a live
coordinator, activate PPS, tune a programmable supply, enable SM5440, or release
SM5714 switching inhibition. The device remains the Test300 retained thermal fix.

## Capability versus active contract

Pinned Linux 7.2-rc3 `tcpm_pd_select_pdo()` publishes USB_TYPE according to the
source's advertised PPS/SPR-AVS capabilities even when it chooses a fixed PDO.
`tcpm_psy_get_online()` distinguishes fixed=1, PPS=2 and SPR-AVS=3. Accept a fixed
snapshot with a PD, PD_PPS, PD_SPR_AVS or combined capability type only if ONLINE
is 1 and the existing 5V/1.8A or 9V/1.5A limits, successful callback mirrors and
stable generations/properties all agree. ONLINE=2/3 is never a fixed snapshot.
This corrects the Test297 observer; it changes no charge programming or Request.

## Kernel API and ownership

`sm5714_pd_restore_fixed(instance, source_generation, lease, &snapshot)` requires
an exact current source/port identity and a nonzero acquired switching lease.
The caller must prove the pump OFF and serialize against releasing that lease.
A read-only battery companion check verifies the lease, inhibition, Type-C owner,
charge gate, PM and fault state; it performs no I2C and does not grant pump ON.

Pin the provider's lifetime, try a per-provider operation mutex (busy refuses),
check the token/lease, read standard properties twice and recheck token/lease.
If already fixed, perform no write. If ONLINE=2 with PPS capability, write only
standard POWER_SUPPLY_PROP_ONLINE=1. Reject offline, unknown types and active AVS.
Afterward use the same double-read/generation/mirror/board-limit fixed snapshot
and require the original instance/source generation. Zero output on any error;
preserve the first setter error and do not retry. Success is only a logical
contract observation, not physical VBUS or permission to charge.

The current actual Request guard remains fixed-only (`pps_authorized=false`).
Consequently this commit cannot reach a live PPS contract through this driver.
The PPS-exit branch is executed with a lock-aware protocol mock, not claimed as
hardware-tested. No writable debugfs/sysfs activation interface is added.

## Lock and lifetime rules

Registry -> try TCPC only while pinning; no registry, TCPC or battery lock across
standard power_supply getters/setter. The operation mutex serializes this API;
TCPM callbacks never take it. Companion -> charger is the separate, short lease
check order; no TCPC/registry lock held. Unbind removes publication, drains pinned
operations, then puts the power_supply reference before unregistering TCPM.

Pinned `tcpm_pps_activate(false)` uses TCPM's own policy engine and waits for its
completion with PD_AUG_PSY_CTRL_TIMEOUT=10 seconds. That is a completion timeout,
not an end-to-end deadline: acquiring upstream swap_lock can also wait. Do not
wrap an abandoned asynchronous worker around this API or release its resources
before it returns. No hand-written Samsung PD policy is introduced.

Detach/reset/source changes during a blocking setter cannot be made globally
atomic with upstream lockless properties. They invalidate completion evidence;
the API cannot claim that no detach occurred in an unobservable interval. A new
source is never accepted as success for an old token. Ordinary callback budget
changes still revoke the lease and retain inhibition. A successful fixed result
therefore does not imply the original lease remains releasable. The future live
adapter must integrate owned budget transitions rather than weaken revocation.

## Remaining gates and next physical purpose

Actual owned PPS callbacks/RDO authorization, live coordinator, physical fresh
SM5440 ADC, protection/OCP and PM qualification remain incomplete. This is not an
active charging candidate. Next register a short, pump-OFF test on a known
PPS-capable source: verify ONLINE=1 fixed classification, then exercise an acquired
lease and idempotent fixed restoration. Physical fixed VBUS must be established
before any switching release; failure leaves inhibition set and follows the
registered rollback. No repeated delay-only ADC experiment or pump activation.
