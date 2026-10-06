# First stop preserved

At device uptime2036.29s, just after fixed9 first appeared, the observer stopped
with `fixed9 ordinary charging missing`: battery statusCharging but current
-0.473A, input still0.5A; temperature24.3C, pumpCNTL5=01 OFF. No30s window
started. Full before/after kernel JSON and host error remain untouched.

Read-only post-stop endpoint2089.36s, without reboot/cable/config changes:
fixed9/1.5A input, Charging +1.436A, VBAT4.113V, pack24.9C, sameboot/config/notes/OFF.
This establishes normal later charging, not a uniquely proven gauge-cache cause
or continuous30s evidence. The runner incorrectly treated first negotiated9V as
the first healthy charging sample. Its original STOP will never be rewritten.

Under HOST_TEST_WORKFLOW device-completion criterion, collect only the missing
first30s window in `device-completion-charge/`, same connected source and sealed
observer. No new attach/native check/flash/kernel/PPS/current advancement.
Only after this device observation succeeds collect the originally registered
15s unplug discharge in a separate evidence namespace.
