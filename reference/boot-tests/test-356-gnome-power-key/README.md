# Test356 — GNOME power key policy

Test355's full prior kernel/system-power evidence attributes the shutdown to a power-key event, GNOME48.1 VM handling and orderly PowerOff. systemd-detect-virt=vm-other; existing logind HandlePowerKey=ignore and gts9-power-key.service are already correct. This stage sets only GNOME power-button-action=nothing for ms/greeter and a reusable schema default. Never falsify virtualization or change the hardware/backlight helper.

Record exact previous per-user dconf value (empty means no explicit override), install the new owned schema override and compile, verify both effective values, then start GDM once and retain persistent masks without --now. Ten-second initial journal/health check; desktop remains active. Ask the owner for two short power presses: screen off then back on, same boot, SSH remains reachable. This is manual acceptance; applying a value alone is not a physical key pass. No long hold, suspend, touch load, reboot, flash or charging mutation.

Failure rollback restores only this new schema and per-user key. Kernel/DT/config/181 modules, logind/service, charger/GPU/USB/ADB remain unchanged. Test348 scope remains unused and eventual exact331/TWRP endpoint unchanged. New touch acceptance follows a fresh registration.

One test compiles the actual cached Debian48.1 schema and checks the resulting nothing value plus unchanged other power keys. Existing accelerated GNOME evidence reused. Build/fullsuite:false; no routing change, no CI. Prior owner manual desktop success remains recorded alongside the subsequent power-key regression.
