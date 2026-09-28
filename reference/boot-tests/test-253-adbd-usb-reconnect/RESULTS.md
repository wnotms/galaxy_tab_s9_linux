# Test253 initial preflight: stopped before deployment

The locally built ARM64 userspace daemon and 13 focused real-thread/owned-FD
checks pass. Final full host regression passed1080 tests, zero failures/errors/
skips. No daemon, service, gadget or kernel file has been written to the device;
no Test253 reboot was issued. Native ADB remains offline, NCM/Wi-Fi SSH work.

Read-only preflight on boot `fcb9a367-fa8e-43df-afb1-08db722ff2f1` stopped on
`upower.service` failed, before the full acceptance gate. The failure occurred
at source time2262.005s, before this preflight: systemd rejected user namespace
setup with EINVAL, and upowerd never executed (`217/USER`, five restart attempts).
`PrivateUsers=yes` in the shipped unit conflicts with embedded
`# CONFIG_USER_NS is not set`. See raw `preflight/upower-failure.txt` and
`upower-unit-config.txt`. This establishes the launch prerequisite failure,
not an ADB or CPU-stall cause. No UPower/kernel workaround was applied.

The existing Test252 candidate config/notes and DCC/runtime profile still
match. Supplemental post-stop five-partition/181-candidate/181-original module
identity and full journals are retained separately. The original Test252 USB
acceptance remains stopped. A fresh, separately registered ADB-only attempt
must identify this exact existing failed unit explicitly rather than silently
clearing its status or declaring the initial preflight clean.
