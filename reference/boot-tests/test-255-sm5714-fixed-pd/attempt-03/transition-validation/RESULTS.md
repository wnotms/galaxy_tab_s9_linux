# Registered post-charge capture preparation

Changed host invocation executed1200 retained tests in96.499s, with zero
failures/errors/skips. Both read-only phase captures compile. The battery
parser/policy is the same17-test-validated collector used for charging;
PC observation reuses attempt02 transport/kernel/PnP gates, with explicit
preflight/charging/unplug prerequisites and a new evidence folder/scope.
Unplug capture waits for150s of actual USB-offline/Discharging/negative current;
settling is excluded from the window, never presented as a passed window.
These helpers issue no reboot, restart, flash, sysfs or configuration write.
Their preparation does not pass the future physical transitions. No CI.
