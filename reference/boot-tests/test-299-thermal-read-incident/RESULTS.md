# Test299 — thermal incident and offline fix

Owner photo attributed to restored263/acdd2dfc at224.224098s kernel source timestamp
(photo shows224.226049s); thermal_zone37 is SM5440passive. Initial startup confirmation
failed at4.037024s; sample3498mV/current0/OFF/fault1/pending1 then stops. Invalid
or stale TEMP correctly returnsENODATA. Automatic tripless zone later disabled;
not a battery/CPU sensor failure. Packzone38 enabled/31.8C, IIO/Goodbattery and
services responsive. Do not clearfault or manufacture/stale-return temperature.

Fix9173df11 only sets passive power_supply_desc.no_thermal=true and explanatory
comment. Diagnostic TEMP, freshness/error/startup/fault/ADC semantics unchanged;
SM5714 battery automatic thermal zone and pack/IIO/thermal safety unchanged.
No global thermal/config/DT/core/rootfs/USB/PPS/pump/current change. Future active
pump needs qualified continuous die-temperature input; absence of a passive zone
is not healthy die-temperature evidence or a charge grant.

5actual descriptor/pinned-mainline registration tests +24actual passive tests
PASS. Initial fixture errors preserved and corrected (missing upstream ops object,
incorrect existing temperature-function name), no existing test weakened.
ARM64 ccache96.64s/W1sparse/objectidentical/exact297configDT/protected96/compiled
overlays/181paired modules PASS. No full repeat/CI under owner changed-scope workflow.
This record is read-only incident +offline qualification, not a physical fix result.

Next separately push Test300 registration: one299candidateboot, assert passive
thermal type absent/real packzone enabled+valid,15sdeviceendpoint. Retain candidate
on registered pass to actually fix owner symptom; exact263rollback on firstfailure.
No224s wait: nonregistration is a direct structural proof. Fullport goalactive,
ADC/OCP/PM/livePPS/directcharging still incomplete/Stage3NOTREADY.
