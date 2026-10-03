# SM5440 OFF-only settings transaction

This implements a missing hardware layer for the direct-charge port: checked
input-limit, battery-regulation and switching-frequency programming, with a
restorable transaction. It is compiled only by the existing default-inactive
X710_CHARGING_POLICY profile. It has no probe hook, exported symbol, userspace
knob, automatic caller or CHG_ON write. Installed accepted311 remains unchanged.
This is preparation infrastructure, not a direct-charge-ready candidate.

## Source and limits

[VENDOR] X710 sm5440_charger.c: set_ibuslim(), set_vbatreg(), set_freq() and
sm5440_dc_set_charging_config() define the three register fields. Input is
50mA/code, battery regulation is3800mV+12.5mV/code, and frequency is250kHz+
50kHz/code. X710 frequency mapping is450/650/850kHz at <=1100/<=1700/>1700mA.
[FEDORA ab123e7d] uses the same fields in its hardware initialization/start.
[BRINGUP_LIMIT] accept1000..1800mA, round DOWN, battery regulation4440mV rounded
DOWN to4437.5mV. Do not import vendor +300/+600mA or +50mV offsets. This pump
regulation setting does not change SM5714's accepted4440mV float setting.

Vendor init explicitly disables hardware IBUS/IBAT OCP and states software OCP
is necessary. Do not guess an enabling bit, import the aggregate protection
recipe, or claim these current/regulation controls supply a qualified cutoff.
PPS/handoff/physical ADC/OCP/watchdog/ON remain separate outstanding work.

## Transaction and failure behavior

A future serialized hardware adapter must first establish source/lease/pack/
physical-voltage eligibility, drain competing ADC work, and hold its I/O mutex.
Use the existing uncached regmap: readback must reach silicon. These helpers
perform a finite number of register operations without delay, PD calls or locks;
I2C controller timeout is not a hard-realtime protection guarantee.
They are not a charging grant and cannot replace those outer prerequisites.
There is deliberately no live adapter until that context is implemented.

Start with a zeroed per-session transaction. Refuse reuse, invalid current,
unknown DEVICEID, any non-OFF mode, absent VBUS or a live fault before the first
settings write. Read live STATUS without consuming INT latches. Capture the
three original settings and ten unchanged protection/operating registers.

For each settings write, recheck OFF/live status, preserve unrelated bits and
verify the complete resulting byte. Mark restoration pending BEFORE a write
which might have reached silicon. Finally verify OFF/status and those ten
witnessed registers. Only then report settings prepared; it still means pump OFF.

On any post-mutation failure, attempt OFF/readback, restore all possibly changed
fields in reverse order, then recheck OFF and the unchanged register witness.
Preserve the first operation error separately from cleanup error. A missing OFF
proof prevents restoring potentially high inherited settings. Any cleanup
failure leaves restoration pending and the transaction faulted. No reset, live
fault masking, INT clearing, retry loop or fabricated successful rollback.
A successful prepare can later be explicitly restored once; reuse is refused.

## Qualification and next integration

Test314 is offline only. Execute the actual C code against a fault-injected
regmap for every failed read/write, uncertain applied write, silent write drop,
mode/fault change, protection drift and failed restoration. Preserve old passive
and ADC tests. Build the pinned ARM64 offline-policy profile in the reusable
cache; compare exact config/DT/protected source and paired module artifacts.
No new profile, DTS, TCPM, SM5714, USB/adbd/rootfs or device operation.

The next implementation connects this layer to the source-bound pump-OFF
preparation context. It must resolve the physical ADC/freshness and live
pre-status evidence; no return from this helper authorizes PPS or pump ON.
Do not flash another unchanged PC5V ENHIZ experiment to exercise this code.
