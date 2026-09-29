#25-minute direct18W PD battery telemetry

Owner-confirmed Lenovo YG65G USB-C2, C1 idle, computer cable absent, Wi-Fi
retained. Boot d745248e6a164243b9ccc5e6ede21fb2 stayed unchanged.
The first300.011s checkpoint and the registered additional20-minute window
completed in1500.060s host-monotonic time. Device-source span:
1499.930s; target5s sampling maximum gap:
6.130s. All301 charging samples show positive
current, Charging/Good, Sink/Device and fixed9V/1500mA policy state.

SOC59->69%; pack temperature28.7..31.5°C. Battery-net-power range
6.357504..8.563590W, mean7.827682W. Raw VBAT range
3.988..4.146V;
IBAT1536..2084mA.
The programmed1500mA input limit yields a13.5W configured ceiling,
not measured charger draw. The adapter's18W label is not an observed draw.
Actual input power and independent VBUS measurement remain unavailable.

Complete periodic kernel journals and failed-unit captures contain no new
CPU-stall/panic/I2C/TCPC fault or new failed unit. Initial5V CC/PD budget
transitions followed by9V are preserved in source-timestamped journal rows;
they are not a separate5V-only-source physical acceptance.
No kernel/DTB/driver/charging policy/rootfs/USB/adbd configuration, reboot,
flash or Stage3 action was performed. First-failure gates were never relaxed.

Verdict: **bounded battery/contract telemetry passed**. This does not claim
independent measured-VBUS acceptance or universal safety. Registered unplug
and charger-to-PC checks are pending and cannot be inferred from this pass.
