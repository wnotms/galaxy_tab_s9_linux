# Test361 — user reduced motion applied; normal-use heat evidence

Same33125ff0ad0/accepted GNOME+touch. Two60.000s windows completed with seven
snapshots each. ms enable-animations originally inherited true (no explicit
dconf key); one live-user-bus write now false, exact original saved for reset.
Global/greeter/power-key settings unchanged. GUI remains active, zero new
failed unit/severe kernel signature. CollectorPID4348 is terminal; final live
check found no process,14samples and terminal.json. No old watcher restart.

| Window | CPU capacity activity | Pack temperature | GPU runtime suspended fraction |
| --- | --- | --- | --- |
| animations on |13.51%|26.0–26.4°C|67.64%|
| animations off |4.46%|26.4–26.8°C|89.92%|

These are **uncontrolled normal-use windows**, not evidence that the setting
caused a measured cooling improvement. QQ processes appeared and owner activity
changed. Newly started/exited PIDs are not apportioned in endpoint process rates;
raw counters retain them. Aggregate CPU includes all accounted work and process
percentages use oneCPU=100%, distinct denominators. Observer is also recorded.
Pack warmed0.8°C overall; no claimed temperature decrease.

GPU reports normal runtime suspend/resume counters and mostly220MHz samples.
CPU7 accumulated deeper-idle/WFI time in both windows, contradicting an inference
of continuously active maximum CPU based only on cached frequency. Available
TSENS snapshots reach47.2°C in first window; these are SoC sensors, not the
pack42°C stop threshold or a calibrated tablet-surface measurement.

Screen raw brightness was2047/2047 throughout both windows (earlier preflight
was628). This is a useful next optimization preference, not a causal attribution
of all heat to the display. Owner clarifies “本次没有发热，上次运行时发热”. Current heat is not reproduced;
historical cause remains unproven. Retain owner-controlled brightness, no
automatic50/70% change or additional heat-reproduction trial. Keep animations
false as a reversible preference; do not kill owner QQ/apps or change their data.

Raw14snapshots/commands/full finalkernel and SHA-bound gzip are retained;
owned device log directory contains partial checkpoints/terminal/original key.
8affected counter/PID-reuse/unit tests passed; no fullsuite/CI/kernel rebuild.
No OPP/governor/thermal threshold/charging/USB/kernel/config/DT/module-dir/
firmware/flash/reboot change. Active3481200s grant remains unused and its
fresh desktop-inactive admission/final331TWRP endpoint unchanged.
