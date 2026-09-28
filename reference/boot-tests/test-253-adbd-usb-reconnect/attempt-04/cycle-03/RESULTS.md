# Cycle03: accepted under the adopted bounded recovery policy

One owner-operated computer unplug/replug, same boot/PID834/hash, no charger,
reboot or software change. The observed offline lower bound54.755s was detected
from supply offline+host ADB absence, despite UDC configured. Native USB shell
passed first attempt. NCM first probe timed out8s, second passed with source-
bound banner; the first timeout is retained. Combined native/NCM recovery
conservative upper bound15.060s is within60s. No new adbd warning occurred.

Continuous real native ADB and both SSH paths completed151.345s after recovery
with full stream/final journals, no new kernel fault/suspect or extra boot/cable
transition. The full final-acceptance/ check is also this cycle's post-cycle
gate, referenced by post-cycle/summary.json, with original command times retained.
Five partitions/config/notes/181 candidate+181 original hashes/DCC/protected
settings/daemon/units/kernel/ADB/NCM/Wi-Fi pass, without Code43. No host-server
restart, device restart/reset/software change or reboot. This completes3/3
adopted bounded cycles, with documented NCM recovery transients. Prior stopped
attempts/Test252 remain stopped; this is not a transient-free USB reliability
claim or an acceptance of raw connected `adb reconnect`.
