# Persistent GNOME startup and terminal shortcut — completed

Native Debian boot `78ec1906-4713-4837-9acc-fe245647d7cf` remained unchanged. Test331 recovery completed first, including all five partitions, exact embedded config/kernel notes and all 181 matching module files. No kernel rebuild or new charging test.

Root cause of text-only startup: graphical.target was already configured, but gdm.service, gdm3.service and display-manager.service still had persistent /dev/null masks from installation/test guards. Removed only those reviewed masks, restored display-manager.service to the installed GDM unit and retained graphical.target. The accepted gts9-palm paired pen/touch loader is enabled as a dependency of GDM and passed its existing exact module/kernel gates before the login screen started.

GNOME Console 48.0.1 (`/usr/bin/kgx`) was already installed. User ms had no custom terminal keybinding. Added a dedicated Ctrl+Alt+T binding to launch kgx, preserving other custom shortcut paths. Existing login password and power-key/backlight-only policy retained.

Same-boot verification: GDM, paired input, SSH, adbd, NCM helper and power-key helper active; no failed systemd units. Full kernel JSON has no fault counts or unbounded suspects under the existing production parser. Battery telemetry remains Good with ordinary charging. Native before/after settings and service/input journals are archived here; original values are also saved on-device under /var/lib/gts9-desktop-default/20261008.

Owner physically confirmed **terminal and touch both normal** after logging in. Configuration persists for subsequent normal boots. A separate future reboot was not performed merely to retest this setting; current same-boot startup and persistent links/default target were verified.

Validation: Python syntax passed, focused userspace review and live checks. `host_tests_executed: false`, `kernel_build_executed: false`: reversible userspace settings, reuse accepted graphics/input/kernel qualification. No full-regression claim and no Actions. SSC/automatic rotation and the larger charging port remain incomplete; this result does not claim their acceptance.
