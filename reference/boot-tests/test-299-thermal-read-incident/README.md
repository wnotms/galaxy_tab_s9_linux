# Test299 — post-test thermal warning attribution

Owner photo: thermal_zone37 Unable to get temperature, disabling at224.226049s.
Read-only same Test263 bootacdd2dfc/configf2891de2/notesfea0613f; source Test263
is ea938b245bff3ae9e3c1828751ea149a90337992. Not the new297/298 kernel.
Zone37 type=sm5440-passive; TEMPreportsENODATA/mode disabled. Existing startup
confirmation refusal at4.037024s stopped passive sampler; finalsample3498mV,
OFF/IBUS0/fault1/startup_pending1. Cached die temperature is intentionally unusable.
Mainline automatically registers a tripless zone for power_supply TEMP; repeated
missing temperature disables it later. This is not battery/CPU thermal failure.
SM5714 battery zone38 enabled,31800mC; packTEMP318decic/Good, system servicesactive.

No sensor/threshold/fault/calibration change, no device write/reset/PPS/pump.
Fullkernel/rawcache/type/mode/battery/photo retained. It does not invalidate the
bounded Test298 newkernel endpoint, but exposes a later warning on the restored
baseline. Do not amend historical evidence to call it clean.

Fix: passive descriptor no_thermal=true, the stock power_supply metadata flag.
Preserve diagnostic TEMP+ENODATA/fault gates and independent SM5714 IIO pack
thermal policy/auto zone. No fabricated or stale temperature, no global thermal
suppression. Active Stage3 must qualify a genuinely continuous die sensor before
using it; this fix does not resolve ADC/refusal/OCP. Register separate Test300
single candidate boot/noSM5440thermalzone/packzone/15sdeviceendpoint/263rollback.
