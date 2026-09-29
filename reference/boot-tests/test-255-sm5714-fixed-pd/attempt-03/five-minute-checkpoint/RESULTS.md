# First5-minute direct18W PD battery checkpoint

The owner confirmed Lenovo YG65G USB-C2 attachment. The unchanged Test255
candidate negotiated fixed9V/1500mA and programmed1500mA switching input.
Observed300.011s on boot d745248e6a164243b9ccc5e6ede21fb2; all61 charging
samples show positive battery current. SOC59->61%, temperature28.7..29.7°C.
Measured battery-net-power range6.514893..8.428736W, mean7.771210W.
13.5W is the configured input ceiling, not measured charger consumption.
No new kernel fault, failed unit, role/boot change or stop threshold was detected.
Exact policy/config/modules and thermal/float boundaries were not changed.

This directory freezes the raw prefix through the5-minute checkpoint, including
pre-attachment offline samples; summary statistics count only61 charging samples.
The registered additional20-minute same-boot window is still in progress.
Actual input power and independent actual-VBUS measurement remain unavailable.
No claim of complete original Test255 acceptance or universal device safety.
