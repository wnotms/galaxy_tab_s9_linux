# SM5714 / SM5440 transaction and fallback contract

## Current hardware path — 2026-10-08

The transaction principles below remain relevant, but the dated Test256–314
implementation/deployment descriptions are historical. Current hardware work
uses the Fedora-derived `sm5440-fedora.c`, not an unqualified replacement for
the earlier native engine. See [architecture](X710_CHARGING_ARCHITECTURE.md).

[Accepted Test345 evidence](../reference/boot-tests/test-345-final-refresh-reserve/PHYSICAL_RESULTS.md)
proves one bounded short handoff/refresh/exit: fixed9 admission and source-bound
lease; switching inhibition; physicalOFF and>=3parked-zero samples spanning
>=100ms; PPS/physicalVBUSsettle/ON; five parked refreshes; one final<=2s refresh
reservation deferral without deadline extension; native complete/lease0;
OFF/unbound and verified fixed9 return; subsequent ordinary charge/discharge.
Exact331 boot/original181 were restored. This is bounded evidence, not physical
protection calibration, hard-realtime cutoff or every fault/PM branch acceptance.

[Test346](../reference/boot-tests/test-346-bounded-pps-five-minute/README.md)
reuses the same current/protection/thermal/fault/PM/lease behavior. Its separately
qualified immutable selector admits300000ms only with exclusive one-shot mode;
unknown/mixed modes fail beforeI2C. The new runner requires the exact duration
from cmdline/sysfs/native journal, follows the enrolled guardian PID and never
restarts after fault, completion or observation timeout. It remains unauthorized
and undeployed. Any later actual non-clean attempt requires OFF/fixed verification
and exact331 restoration, with primary failure and cleanup result kept separate.

Lock/epoch, PM drain and fail-closed principles below are not waived. Ordinary
SM5714 ceilings5V<=1.8A/9V<=1.5A and float4.44V remain fixed. An approved APDO
is not permission to raise input current. Source detach/reset invalidates old
capabilities and ownership; no old lease may restore a contract on a new attach.

## Historical offline Stage3C design and implementation notes

This is an offline Stage3C design. It does not enable direct charging. The
vendor audit and unresolved hardware OCP/ADC requirements are entry gates.
Fixed Stage2 remains the installed fallback and primary build profile.

Current implementation boundary (2026-10-03): this document describes the
future **active** transaction. Test302 implements native source-owned TCPM PPS
operations, and Test303 implements an explicitly invoked pump-OFF consumer
with a battery lease and PM drain. See
[owned PPS consumer](X710_OWNED_PPS_CONSUMER.md). Those compiled, host-tested
components do not supply a live pump-ON actuator or qualify physical protection.
The retained device is accepted311 ordinary recovery, restored after Test313.
Test314 compiles an inactive OFF-only hardware settings/restoration layer;
it has no live adapter or ON hook and does not yet complete this transaction.

## Admission and state

Use an explicit transaction: SWITCHING -> DIRECT_PREPARE -> PPS_NEGOTIATING
-> DIRECT_STARTING -> DIRECT_ACTIVE. Exit from every DIRECT state:
DIRECT_STOPPING -> FIXED_PD_RESTORE -> SWITCHING. A failed safety operation
ends in FAULT with both paths inhibited, not a falsely successful fallback.

Entry needs a fresh connection epoch, healthy fixed Sink/Device contract,
APDO support, present/healthy battery, valid fresh pack temperature/voltage/SOC,
valid pump ADC/die temperature, NORMAL thermal state, no fault, and not
suspended. Initial conservative limits: SOC5..<80,3500<=VBAT<4300mV,
200<=Tpack<380 deci°C, PPS<=1800mA, PPS8200..10500mV. All are
[BRINGUP_LIMIT], not new vendor production declarations. Missing charger/
connector sensor may not be forged; any optimization requiring it is disabled.
The hard initial stop at42°C is separate from the tighter admission interval.

## Operation order and proof

1. Snapshot eligibility/contract/epoch, acquire exclusive transaction ownership.
2. Inhibit SM5714 poller/TCPM switching enable before opening Q4. Confirm Q4
   off and safe ordinary current;100mA register minimum is NOT full VSYS isolation.
3. Confirm pump OFF. Start PPS via standard TCPM power_supply, not raw PD TX.
4. Recheck epoch/eligibility after each asynchronous operation. Clamp/round
   target to source APDO and board limit; reject empty range/insufficient power.
5. Require a fresh physical SM5440 VBUS measurement settled within bounded
   tolerance of target. Negotiated TCPM voltage is not that proof.
6. Program only audited protections/current/frequency/WDT with readback. Unknown
   protection/OCP support blocks pumpON. Initial input ceiling1800mA is independent
   of source advertised current and vendor battery-current targets.
7. Enable pump last; immediately sample mode/VBUS/VBAT/IBUS/temp/faults.
8. DIRECT_ACTIVE exists only after every gate passes. Maintain bounded worker,
   current/temperature/OCP/epoch monitoring and watchdog service.

Long negotiation/settle work happens without the charger/core/transport mutexes.
The adapter is single-owner and cancellation increments the connection epoch;
after unlocked work the snapshot must still match. A cancellation cannot rearm
old work or restore an old9V contract onto a fresh attach. Epoch counters are
64-bit for the coordinator and never reset by a retry.

## Refresh and exit

Fedora measured a REVBLK cutoff and later TCPC I2C loss when refreshing PPS
with pump running. Every planned refresh must therefore do:
OFF+readback -> PPSrefresh -> bounded physical VBUS settle -> eligibility/
epoch recheck -> ON+readback. No shortcut based on PS_RDY alone. Vendor initial
PPS delay250ms and recurring1100/2500ms requests are evidence; they do not
prove mainline refresh safe. Initial proposed refresh4s is [FEDORA/BRINGUP_LIMIT]
and must be accepted with source timeout and worst-case TCPM setter latency.

Exit: pumpOFF+readback first, then TCPM ONLINE=FIXED, then prove fresh fixed
contract and physical VBUS safe for switching, then release SM5714 inhibit.
If pump OFF, PPS exit, epoch, ADC or fixed restore cannot be established:
leave inhibited, FAULT, no automatic retry/voltage change. Detach means cancel,
OFF, invalidate source cache and do not negotiate with a vanished/new source.

## Faults, retries and PM

Any I2C error, invalid thermistor/ADC/VBAT, APDO disappearance, PPS failure,
CHG_ON lost, REVBLK, UVLO/OVP/OCP, thermal shutdown, startup/capacitor fault,
unexpected reboot or rescue loss exits direct. Best-effort OFF is not proof if
I2C fails. Save failure evidence before a separately authorized retry.

Vendor UVLO2s retry differs from Fedora2/4/8/16/30s and5failures->300s. First
bringup policy latches on first critical fault; a pure bounded backoff helper
may be tested for future noncritical retry, but no automatic retry is enabled.
No I2C/Request storm. Software OCP response time remains a pump-enable blocker.

Suspend/freeze/unbind: invalidate epoch, stop new work, synchronously drain it
without holding core locks, verify OFF, exit PPS safely before controller PM.
On failure return an error/leave inhibited rather than suspend with unknown
pump state. Resume starts from OFF/fixed and must reacquire fresh eligibility;
no restoration of an old PPS state. Stage1 suspend already stops switching and
must remain unchanged. Vendor wake locks are not a mainline PM design.

## Implementation boundary

Test257 extends the unwired core with latest-source-offer admission, monotonic
facts/ADC age checks, microamp IBUS comparison and a monitor operation. See
SM5440_SOFTWARE_OCP_AUDIT.md. Facts use the oldest required acquisition timestamp;
cached data cannot be stamped fresh. Logical500ms facts/100ms ADC and monitor
budgets are refusal limits, not hardware OCP qualification. Healthy monitoring
does not request PPS or change pump mode; late/stale/faulted monitoring invokes
verified OFF/fixed fallback. Stop revokes authorization even if callbacks are
invalid; such an invalid adapter cannot prove hardware OFF. No live worker or
periodic scheduling has been added, so no bounded physical cutoff is claimed.

Pure validation/state/action ordering is shared with compiled host fault tests.
Passive hardware driver exposes ID/ADC/status and OFF only. The pump-OFF
consumer already integrates standard TCPM power_supply references, real battery
ownership and a serialized PM cancellation/drain boundary. An active adapter
still needs checked pump preparation/ON/OFF hardware operations, genuinely
qualified ADC data, active protection, bounded monitoring and supplier-safe PM
exit. It may not be advertised as implemented merely because the pure engine
or pump-OFF consumer passes mocks. Test256's original live-adapter gap is partly
addressed by Test302/Test303; its active protection and sensor gates remain open.
