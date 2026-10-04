# Native SM5714 pack observations

`sm5714_battery_read_pack(lease, out)` supplies an actual gauge/thermistor bundle
for the mainline charging consumer. It replaces the OFF-only PPS session's
separate power_supply lookups and duplicate thermistor reads. It does not arm a
pump, request PPS, release switching ownership or alter ordinary charging.

## Acquisition and provenance

The provider reads live charger STATUS1/STATUS2, the existing serialized gauge
SRAM words for SOC/VBAT/current, and the mandatory `battery-temp` IIO channel.
It then rereads the live status and checks the provider/state/lease token.
VBUS attach, battery absence, overvoltage or watchdog status changing during
acquisition refuses the bundle. No read-to-clear interrupt register is used.
SRAM RADDR writes select existing read words; no charger-control write occurs.
Negative battery current and negative temperature remain signed measurements.

The battery-present flag now follows Samsung X710 `psy_chg_get_present()`:
STATUS2 (0x0e) bit 2 set means absent. The public battery `PRESENT` property uses
the same hardware predicate and propagates I2C errors. It no longer returns a
constant 1. The vendor source identity/function is recorded in
`reference/charging/sm5714-pack-snapshot/source-audit.json`. This is a hardware
fact; no Samsung private power_supply/notifier framework is imported.

`started_ms` is native BOOTTIME immediately before the first live read;
`completed_ms` follows the acquisition and final token check. This is the
acquisition bracket for gauge SRAM/IIO data, not the gauge's inaccessible
internal conversion timestamp. No polling cache, last-known temperature or
successful default substitutes for a failed read. Errors zero the output.
A zero/start rollback or acquisition bracket exceeding 500 ms refuses output.
The caller must check oldest-data age after return: lock/provider scheduling can
make delivery later than the native acquisition. This is not a hard real-time
500 ms execution promise, and is not the 100 ms physical ADC/OCP qualification.

Health is derived from the same live status and the single real pack-temperature
read. Stable missing battery/OVP/watchdog/cold/hot observations cannot appear as
healthy. The existing OFF-only session additionally requires attachment, Type-C
ownership/charge grant, nonzero identity/generation and exact switching lease,
then retains its existing SOC 5–<80%, VBAT 3.5–<4.3 V and pack 20–<38°C limits.
These conservative bring-up limits are not claimed to be vendor maxima.

## Lifecycle and locks

`sm5714_companion_lock -> chg_lock` is used only briefly to pin and capture a
provider token. Admission and the final charger-token check use trylock, refusing
busy state. Neither core lock is held across IIO or gauge reads. The existing
`sram_lock` protects only the gauge's two-step window protocol.

A per-provider pin prevents managed gauge/IIO/driver storage from disappearing.
Unpublication clears the provider and marks removal before draining pins. It
waits with both core locks released, then acquires the registry barrier to prove
the last decrement/wakeup has finished touching the wait queue. The last put
holds the registry mutex around decrement and wakeup, matching the existing TCPC
lifetime pattern. No raw driver/supplier pointer escapes the API.

Every binding has a monotonic instance. The state generation invalidates on
budget/lease/revocation/PM events, including suspend followed by resume and
same-value ABA changes. Counters saturate/refuse rather than wrap. The exact
owned lease is mandatory during inhibition; lease zero is pre-entry observation.
The caller must also bracket the pack bundle with native TCPC instance/source/
budget receipts: battery state metadata is not a replacement for PD provenance.
Future worker PM/unbind draining remains required; this API alone does not
implement the complete direct-charge lifecycle.

## Verification and remaining work

The actual acquisition, SRAM conversions, public property, pins, PM and token
functions are executed with a register/IIO mock and real pthread locks. Tests
cover every transfer error, thermistor failure, signed current, native time,
state/lease ABA, real suspend/resume and concurrent unbind. The session's mocked
producer still injects per-getter/source/PM failures; its real producer is tested
separately. Mock success is not physical ADC/current/cutoff protection proof.

The offline build uses the existing `sm5440-policy-offline` profile, so both the
real battery producer and real OFF-only session are compiled/linked. The prior
ADC diagnostic is disabled in that profile; no config/DTS change was made to
obtain it. Device accepted311 is untouched. Full active worker integration,
physical sampling/current/cutoff/OCP, native refresh/fallback and PM acceptance
remain. Test317's 128–130 ms diagnostic brackets do not satisfy 100 ms active
protection. No averaging or deadline relaxation is introduced here.

Full SM5714/SM5440/PPS charging port: **NOT READY**.
