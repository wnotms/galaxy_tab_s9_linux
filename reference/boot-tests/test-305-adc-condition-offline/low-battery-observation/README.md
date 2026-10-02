# Retained-baseline low-battery observation

This is not Test305 candidate execution. Device remained on accepted Test299 /
Test300 boot57535bed-a626-48d0-aaaa-3071ac8332e5 throughout11 read-only Wi-Fi
SSH observations. No reboot, flash, sysfs/register write, current adjustment,
PPS request, fault clearing or pump enable occurred.

After the unexpected0%/3.287V reading, the owner was asked to switch from PC
USB to the previously accepted USB-C2 ordinary18W source. Independent read-only
observation used the authenticated Wi-Fi path,15s between command completions,
maximum11 samples. `elapsed_s` is each SSH command duration, not absolute
observation time; raw /proc/uptime provides the device clock. Original raw output
and stderr for every sample are retained.

No PD/net-positive charging transition was observed. Every sample still reports
SDP500mA, SOC0%, temperature31.3°C and negative battery current. Voltage readings
span3.135–3.203V, final3.145V. These are gauge-reported values; no independent
instrument/calibration claim follows. The monitor has completed and was not
restarted. Physical entry remains refused pending ordinary recharge; do not
flash/reboot or invoke a diagnostic while in this condition. Do not infer a CPU
wedge or a new charging-policy root cause from battery telemetry alone.

This evidence-only follow-up runs no host regression or kernel build:
`executed: false`; existing Test305 offline qualification remains separate.
