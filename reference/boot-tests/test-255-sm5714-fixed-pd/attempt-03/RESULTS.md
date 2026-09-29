# Test255 attempt03: direct18W PD power/battery telemetry

**Passed within the owner-revised bounded scope.** Lenovo YG65G USB-C2
18W was connected directly with C1 idle; no separate5V-only source or
external VBUS meter was required for this observation. Earlier sealed
attempts and their unexecuted gates remain unchanged. Registration b63fad60
and23 fresh read-only identity gates were pushed before charger attachment.
All stages stayed on boot d745248e6a164243b9ccc5e6ede21fb2 and adbd PID827.

| Observation | Result |
| --- | --- |
| Fixed PD contract state |9V/1500mA throughout301 charging samples |
| Hardware-programmed input-current limit |1500mA;13.5W configured ceiling |
| Battery net charging power |mean7.827682W; range6.357504..8.563590W |
| Battery voltage/current during registered charging |3.988..4.146V;1536..2084mA |
| Charging SOC |59->69% |
| Charging pack temperature |28.7..31.5°C; Good/Charging throughout |
| First checkpoint |300.011s passed; immutable evidence e0a9f963 |
| Full charging window |1500.060s host-monotonic;1499.930s sampled source span |
| Sampling |target5s; maximum observed source gap6.130s, preserved |
| Unplug battery-only window |150.005s USB/TCPM offline, Discharging, negative current |
| Charger-to-PC recovery |upper bound14.056s from last offline command START |
| Initial recovery command failures/new adbd warnings |none observed |
| Independent PC-connected stable window |156.412s; nativeADB/NCM/Wi-Fi/PnP pass |
| Final installed state |exact config/notes/five partitions/181 modules unchanged |
| Rollback |all three181-file Test254/Test252/Test249 module directories unchanged |
| New CPU-stall/panic/kernel fault, failed unit or Code43 |none detected |

Power is calculated from measured fuel-gauge VBAT and signed IBAT. It is net
power entering the battery, excluding system consumption and conversion loss.
TCPM voltage_now/current_now are negotiated protocol values; switching
input_current_limit is a hardware-programmed limit. Their13.5W product is
**not measured input power**. No claim of actually drawing18W, independently
checking physical VBUS<=9.5V or universal hardware safety is made.
The independently measured VBUS gate remains unobserved. Stable fixed9V
protocol state is supported by full source-timestamped TCPM journal and psy
records. Initial5V budgets are ordinary attach negotiation, not independent
5V-only-source acceptance. No additional5V supply test was performed.

After unplug, SOC reached70% before returning to PC. PC input is limited to
500mA even though its TCPM state reports fixed5V/1800mA; battery net current
can therefore remain negative while charger-enabled status says Charging.
This is recorded separately from the successful9V charging window. The final
PC battery sample was69%,35.2°C, Good. The PC window observed34.1..35.1°C.
No protective temperature/current/voltage limit was deliberately tested.

Fresh nativeUSB config-byte transfer, NCM authenticated SSH/interface-bound
banner and Wi-Fi checks pass. Complete kernel JSON and text, raw supply/typec
samples, Windows PnP, daemon journals, command exit/timestamps, CSV and hashes
are retained. The duplicate identity capture during the PC window is labelled
`during-pc-window-identity`; a separate fresh `final` capture after completion
passed22 gates. All Test253 settings and daemon/hash/PID are preserved; its
existing narrow warning parser found no new warning on this transition.

There was **no** kernel/config/DTS/driver/policy/rootfs/USB/adbd change,
reboot, flash, host-server restart, diagnostic activation or Stage3/SM5440/PPS
operation. Linux7.2-rc3, DCC disabled, Test254 container prerequisites,
4440mV float,2100mA pack-current policy and original thermistor/thermal/
suspend/fail-safe rules remain unchanged. No rollback was needed or executed.
The device is left connected to the computer, charger disconnected, Wi-Fi up.

This completes the revised battery/power observation and bounded USB return
path. It is not a long-term reliability result, fault-rate estimate or blanket
acceptance of every original Test255 gate. No Stage3 is authorized or started.
Host validation is recorded in validation/transition-validation/
pc-recovery-validation/final-validation; all old tests are retained and CI
was not started. See summary.json for machine-readable results and per-stage
SHA256.json for preserved raw evidence.

Final local review executed all1200 retained host tests with zero failures,
errors or skips (96.129s unittest;96.240s runner). Registration wrapper also
executed1200;17 new parser/power tests and33 retained cable checks passed.
Every stage manifest and the complete final attempt seal were verified.
