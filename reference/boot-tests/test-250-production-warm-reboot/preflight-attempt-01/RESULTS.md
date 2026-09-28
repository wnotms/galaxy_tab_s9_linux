# Read-only Test250 preflight attempt 01 — runner false negative

This preflight stopped before any reboot. The tablet remained on boot
`b08bbc9b-3bbf-417e-9935-619fcc5d7222`. The device-returned embedded
config and kernel-notes SHA-256 matched Test249; all five production partition
hashes and all 181 module file hashes matched. The production watchdog/ECC
values were zero, no systemd unit was failed, and the raw DCC check reported
`dev=absent`, `sysfs=absent`, `getty=inactive`, `symbol=`.

The first runner incorrectly expected three DCC output lines. Its intentional
empty `symbol=` marker is a fourth line, so it reported `dcc_absent: false` in
`production-state.json`. That is a host-side parsing false negative, not a
device-state change. This attempt never reached full journal or transport
acceptance and must not be counted as an accepted preflight or a reboot round.
The raw command outputs and statuses are retained here; the corrected runner
will start a new preflight directory without overwriting them.
