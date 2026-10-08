# Test361 — GNOME normal-use activity and reduced motion

On current accepted33125ff0ad0/GNOME/touch, record60s normal use with animations
on, then save exact ms dconf key and disable only interface enable-animations;
record another60s. Seven snapshots per phase,10s apart. Preserve raw process
comm/start/cpu counters (no argv/env/input), CPU capacity counters, pack safety,
available CPU/GPU TSENS/devfreq/runtimePM and unchanged backlight. Read TSENS,
not the known unrelated disabled sm5714 thermal-zone37; pack uses validated
power_supply telemetry. Unknown sensors are omitted, not replaced with zero.

This is observational, not a controlled workload/causal or long-term thermal
experiment. No stress, brightness change, governor/OPP/thermal/current/charging/
USB/config/DT/kernel/181-dir/flash/reboot change. Current ms animation preference
false is a reversible visible reduced-motion setting; greeter/global settings
and accepted power-button=nothing remain untouched. Save original explicit key
(absent vs true distinguished). On first failure, restore only that key if
changed, save partial/terminal, no automatic retry. End leaves GUI/touch active.

One owned device log directory/collector lifetime, no restart of old watchers.
Monotonic windows, per-sample boot/pack/new-kernel fault guards and boundary
GDM/failed-unit checks.8 affected counter/PID-reuse/unit tests pass; unchanged
kernel/touch qualification reused, no fullsuite/routing/CI/kernel rebuild.

Window352–361:351desktop transfer created no image; none to retire. Active331
rollback/348 pendingcandidate/provider preserved;348grantunused/fresh inactive
admission/finalTWRP unchanged. Do not call sample comparison proven cooling.

Use the active ms /run/user/<UID>/bus for the live setting write/read, with the
correct user-owned runtime socket. An isolated dbus-run-session is suitable
for a pre-launch schema read but must not be relied on to notify running GNOME.
No other session bus or greeter preferences are changed.
