# Real pack current in the native direct-charge path

## Design before implementation

The existing `sm5714_battery_read_pack()` reads the SM5714 gauge CURRENT SRAM,
with error propagation, signed microamps and the original acquisition bracket.
The native controller currently drops that measured current. SM5440 has no
independent verified IBAT ADC (vendor `SM_DC_ADC_IBAT` returns zero); negotiated
PPS current and twice measured IBUS are not substitutes for measured pack current.

Carry signed `pack_current_ua` and an explicit validity bit into the same native
facts used for entry, refresh/retarget, ON/resume and monitor. Validate **both**
pack acquisitions bracketing the hardware sample; never let a later normal value
hide an earlier overcurrent. A failed provider read leaves current invalid.
Retain the last attempted measured current/bracket in controller result telemetry,
including the excessive value on refusal; it is not a health or freshness grant.

Use a conservative direct-charge signed envelope **−3.6A..+3.6A**
[BRINGUP_LIMIT], with exact microamp comparison. Positive 3.6A is derived from the
existing approved 1.8A input cap and the X710 2:1 topology / vendor
`setup_direct_charging_work_config()` setting `cc_gl = ci_gl * 2`, not a vendor OCP trip threshold or measured protection.
The negative boundary is an explicit bringup refusal of excessive pack discharge,
not a decoded reverse-current hardware fault. Normal negative current while
switching, paused or under system load remains allowed. Zero is a real possible
measurement and is allowed only when current_valid is true. No input-current or
ordinary Stage1/Stage2 charging setting changes; this envelope applies solely to
the native direct/off-coordination eligibility.

The mandatory facts validity/limit check in `x710_charge_eligible()` is also used
by the actual actuator and supervisor guards, without duplicating their code.
The real native controller refuses first/second excessive pack samples before
PPS/ON or the next monitor feed. Existing once-only OFF → fixed physical proof →
lease release cleanup remains authoritative. Unknown OFF still prohibits voltage
change or lease release. No new locks or blocking waits are introduced.

## Source provenance

- [MAINLINE] Current `sm5714-battery.c`: `sm5714_get_current()` sign-magnitude
  CURRENT SRAM decoding; `sm5714_battery_read_pack()` propagates the read result,
  timestamps the oldest real acquisition and rechecks provider/session identity.
- [VENDOR] X710 `drivers/battery/charger/sm5440_charger/sm5440_charger.c`,
  `sm5440_get_adc_value()`: IBAT/default returns zero, not a pump measurement.
- [VENDOR] `sm5440_direct_charger.c`, `setup_direct_charging_work_config()`:
  `ci_gl = min(ta.c_max, target_ibus)` and `cc_gl = ci_gl * 2`. The vendor battery-current capability is not
  an accepted mainline current grant.
- [BRINGUP_LIMIT] Existing PPS input ceiling 1800mA and 2:1 conversion motivate
  the conservative pack envelope; physical accuracy and cutoff remain unproved.

## Validation and remaining gates

Execute real production C in host tests for exact endpoints, one microamp beyond,
invalid/zero/sign-extreme current, first/second pack spikes, provider I2C failure,
loss of current during monitor and paused refresh, and actual supervisor shutdown.
Keep old assertions/tests. Build the existing native profile with exact previous
config and accepted311 DTB; preserve original 181 module pairing and protected
sources. No device operation, kernel activation grant or suite-routing change.

A host pass does **not** prove gauge update latency, calibration, total reaction
latency, physical OCP, ADC coherence or safe pump activation. The private native
activation and software-OCP qualification flags stay false. Current facts keep
their original oldest timestamp; no new timestamp makes cached measurements
fresh. Device access, charge recovery, normal boot, ADC/current/cutoff validation,
independent PPS-OFF and conservative pump tests remain required for the full port.
