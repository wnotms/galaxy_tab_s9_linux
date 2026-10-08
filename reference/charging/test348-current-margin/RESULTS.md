# Test348 current margin: source comparison, no policy change

Owner requested finishing sensor support first, then higher-power charging,
using the same-model Fedora implementation and Samsung X710 sources. This
read-only source comparison prepares that next work; it does not authorize or
execute another charging attempt. Source hashes and line references are in
`SOURCE_COMPARISON.json`. Fedora remote HEAD remains
`ab123e7d1dbc0cbcd35661f9761197e977b15aa9` on 2026-10-08.

## What 1.8 A means

The current 1.8 A is a **PPS input/request and raw-IBUS bring-up stop ceiling**,
not a battery-current limit or a proven hardware maximum. The hardware input
setpoint is 1.7 A. At nominal 9 V, 1.8 A corresponds to 16.2 W of input;
this arithmetic is not a calibrated battery-power measurement. A 2:1 pump
also does not make IBAT exactly twice IBUS: system load/losses and separate
gauge acquisition matter. Fixed 9 V switching charging stays capped at 1.5 A.

Compared with the higher-power port goal, 1.8 A is conservative. It was chosen
for staged validation, not extracted as the X710 production maximum.

## Same-model evidence

- [FEDORA] `sm5440_direct.c`: initial/minimum PPS 1800 mA; default maximum
  3000 mA, configurable cap 5000 mA; hardware limit adds 300 mA above requested
  PPS current. The source advertising/cable/temperature and eligibility limits
  still apply. These values are reference capability, not our hardware pass.
- [VENDOR] `sm5440_dc_set_charging_config()`: hardware IBUS limit is `ci_gl +
  SM5440_CI_OFFSET`, offset 300 mA; twice the offset at minimum current.
  X710 configuration sets `need_to_sw_ocp=1` with the explicit comment that
  hardware OCP cannot be used. This makes software-current protection essential;
  it is not permission to remove or raise the software stop gate blindly.
- [VENDOR] X710 r04 board data separates ordinary PD power 15000 mW,
  max input 3000 mA, max charging current 3150 mA, and SM5440 board tuning.
  Aggregate board limits are not automatic direct-charge settings.
- [VENDOR/FEDORA] ADC IBUS scale is 0.625 mA/LSB. Neither source inspected here
  provides a measured calibration or guaranteed transient/control error bound
  for this tablet. Encoding agreement does not supply that missing guarantee.

## First failure and next decision

Test348 raw IBUS was 1811.875 mA, 11.875 mA above the registered 1800 mA stop
and 111.875 mA above the 1700 mA setpoint. The native guardian correctly stopped
and proved pump OFF/fixed return. Do not reclassify its failed 20-minute result
or infer that a future 3 A setting is safe because this exceedance was small.

After sensors, keep the Fedora-derived hardware transport, TCPM policy owner,
OFF-before-refresh/physical-settle checks and exact fixed-PD fallback. Prepare
a separate candidate that explicitly distinguishes:

1. source-advertised/PPS requested current;
2. hardware regulation setting and its documented margin;
3. raw measured software stop threshold, pack current and temperature gates.

Then register bounded staged 2.0/2.25/2.5/3.0 A work only after the protection,
source/cable, current-margin and fallback prerequisites for each step are met.
Do not inherit Fedora's 5000 mA configurable cap, permissive retries, or a
higher-power setting into the currently accepted fixed-PD path.

No driver/config/DTS/device/charging-current changes were made by this review.
Tests/build: executed=false for this documentation-only source comparison.
No new PPS request, pump activation, flash, reboot or Actions.
