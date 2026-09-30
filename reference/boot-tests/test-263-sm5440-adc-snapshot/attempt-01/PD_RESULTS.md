# Test263 attempt01 fixed9V snapshot phase — PASS

Owner confirmed18W PD attachment before observation. On same33435db7 boot,
30.420s/7samples pass fixed9V<=1.5A contract and conservative switching-input,
cachedraw/freshness/conversion/OFF/protection gates. Reported VBUS9.076..9.109V,
SM5440VBAT4.0415..4.0560V, IBUS0, die32..33C, age68..976ms. GaugeVBAT4.046..4.057V,
netbattery current1.788..2.072A, pack29.0..29.1C, SOC60%. Telemetry-derived net
battery power7.246764..8.383312W, mean7.813216W; this is not measured USB inputpower.
The9V/1.5A13.5W contract/input ceiling is not measured draw. No PPS or pumpON.

Paired cachedADC-minus-gauge VBAT difference-6.5..+3.0mV is retained with raw
bytes and host/device acquisition timestamps. Gauge cache age is unknown;
comparison is not independent ADC calibration or an assumed correction factor.
Protection bytes f2/e7/37/fe remain identical to the PC phase. No new/repeated
startup event, kernel/CPU fault, systemd failure or boot/identity/role change.
USB ADB/NCM absence while on independent charger is expected, with Wi-Fi alive.

The original PC_RESULTS pointwise difference range is corrected to-87.5..-70.5mV
from matched pairs (its raw samples/CURRENT_STATUS already had those values);
the earlier text had subtracted unrelated range extremes. No physical evidence
or verdict is changed. No new build/full regression: kernel source/artifacts
unchanged; endpoint host helper uses accepted fixed-charge parser/safety,15
focused checks including actual saved offline packet+snapshot parsing pass.

Owner-confirmed unplug/discharge endpoint and PC rescue remain pending. Whole
series is NOT complete. No flash/reboot/config/current/protection/thermal/USB
change during this phase. Absolute ADC/OCP/PM/handoff remain unresolved.
