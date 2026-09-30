# Unplug observer: retained waiting timeout

The observer waited300.016s and captured61 samples, all still attached to the
fixed9V charger. It stopped with `unplug-not-confirmed-within-300s` before the
owner's removal was observed. No detach sample or completed transition window
exists in this original observer. Preserve the generated STOP and raw samples;
do not relabel this result PASS or claim continuous unplug attribution.

All captured samples retain Good battery/passive health, pumpOFF/IBUS0, same
boot and no failed units. Final attached pack29.8C, SOC58%, current1.646A;
these are waiting-state samples, not an extension of the registered charging
acceptance window or a20min charge test. No parameter/device change occurred.

The owner subsequently replied that the charger was removed. A separate
`post-unplug-readonly/` capture checks the resulting endpoint without reattaching
the charger or repeating charging. It cannot fill the original transition gap.
PC attachment afterward restores/checks the rescue transport; no new charging
experiment is authorized or started.
