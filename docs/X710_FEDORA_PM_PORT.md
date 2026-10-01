# Fedora-derived PM transition port, Test265

Implementation reference: Fedora X710 ab123e7d, sm5440_direct.c,
sm5440_pm_notify(). Source identity is preserved in Test264 sources.json.
The existing PPS refresh transaction already follows that implementation's
OFF -> source refresh -> physical VBUS settle -> ON sequence. This change
ports its suspend exit semantics into the unwired mainline transaction core.
It does not register a live PM notifier or access the device.

| Fedora behavior | Port behavior |
| --- | --- |
| Set suspending and cancel_delayed_work_sync before exit | Future serialized adapter drains/cancels first; core independently latches suspended and revokes arming |
| Pump OFF, restore switching/fixed contract | Existing checked stop: OFF -> fixed restore -> fresh physical measurement -> switching release; return failures |
| PM_POST_SUSPEND schedules polling | Core resume clears only a successfully quiesced SWITCHING/uninhibited/unarmed state; it never schedules, arms or restores old PPS |
| Return NOTIFY_DONE despite restore failures | Pure API returns the actual exit error; future live adapter must propagate PM failure and maintain inhibit |

New `x710_charge_suspend()` and `x710_charge_resume()` take the existing
transaction, not a new policy framework. The transaction gains an independent
suspended latch. Old facts claiming not-suspended cannot authorize start while
the latch is set. Monitor/refresh observing it follow verified fallback without
another PPS request/ON. Resume after OFF/exit/fixed/epoch failure is denied.
Repeated successful suspend does not repeat I/O or rearm. Successful resume
leaves armed=false; future admission must collect fresh epoch/source/thermal/
ADC facts before a separately authorized entry.

## Concurrency boundary

These APIs require the existing single-owner serialization contract. They do
not make ordinary C bools safe for concurrent worker/notifier access. The future
adapter must stop new work, revoke its generation, drain outside charger/TCPM/
I2C locks and only then call suspend while suppliers remain available. Core
callbacks check the epoch and return OFF/restore proof. A failed write cannot
be represented as verified OFF; no fixed voltage change after unknown OFF.
Unbind/shutdown and suspend-abort handling remain live-adapter work.

The new resume API performs no register/PD operation. Clearing the PM latch
after a failed exit is deliberately unavailable; external fixed-path recovery
needs fresh verified state, not silent reset of this transaction. No automatic
retries, source role, direct-charge enable sysfs or thermal/current change.

## Validation scope

Compile the actual C core in host tests: clean active/inactive suspend, each
OFF/fixed/measure/switching failure, invalid adapter, epoch loss, repeated
suspend, stale pre-suspend grant, denied resume and no auto-arm. Existing entry,
PPS refresh, OCP/freshness/fault assertions remain unchanged. An isolated
sm5440-policy-offline ARM64 build compiles this default-unwired core; it is
not the installed Test263 profile and not authorized for flash.

Only expected config delta versus installed passive profile is
CONFIG_X710_CHARGING_POLICY=y. DTS/DTB, fixed5V1800/9V1500mA,4440mV/thermal,
SM5714/SM5440 transport/register operations, USB/adbd and DCC stay unchanged.
Host/build proof does not qualify active physical OCP/ADC/PM timing. ActiveStage3
remains NOT READY; no physical suspend/PPS/pump test is performed.
