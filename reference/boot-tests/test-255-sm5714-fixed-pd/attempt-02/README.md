# Test255 attempt02: owner-rebooted candidate PC USB checks

On 2026-09-29 the owner reported one manual reboot and instructed continuation
from the following items. Current observed Debian boot is
`d745248e6a164243b9ccc5e6ede21fb2`; ADB responds, embedded config/notes match
the installed Stage2 candidate and Type-C reports Sink/Device. These initial
observations are not final acceptance.

This continuation has no deployment, reboot, configuration change or charger
connection. Preserve attempt01's battery-only pass and incomplete same-boot
PC reconnect separately. A manual reboot cannot satisfy same-boot reconnect
or establish charger-to-PC recovery. Fetch both boots' full journals and the
boot history, attribute the transition to the owner's report, and stop on any
new failure or unexplained intervening boot.

Scope: full candidate config/notes/five partition/181 module identity, all
three old 181-file rollback directories, protected USB/SSH/Test253 files,
DCC absence, Stage1 battery readings, Sink/Device live topology, Windows
PnP, ADB shell/file roundtrip, NCM and Wi-Fi authenticated SSH. Observe the
current PC-connected boot for at least 150 seconds with repeated transport,
battery and kernel checks. Preserve initial transport failures; stop on any
non-clean observation, unexpected reboot, Code43, loss of rescue, kernel
panic/Oops/stall, TCPC/I2C/reset/attach loop or charging anomaly.

No known 5V-only source and no independent VBUS meter are available. The
Lenovo 18W PD supply is not connected by this test. The already registered
independent actual-VBUS gate remains required before 9V charging. This attempt
can conclude only bounded PC-USB checks after an owner reboot; it cannot pass
full Test255 fixed-PD or charger-to-PC acceptance. No Stage3/SM5440/PPS.
