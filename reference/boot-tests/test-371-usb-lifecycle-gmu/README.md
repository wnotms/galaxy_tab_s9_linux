# Test371 — accepted GMU kernel USB lifecycle qualification

Independent registration; frozen STOP results Test367/368/369 remain unchanged.
The installed and accepted Test370 kernel, native input pair, GNOME and Test253
adbd are reused. No flash, reboot, build, PD/PPS, pump or charging-policy change.
Exact config and notes come from Test370 final acceptance. Before any formal preflight/start, owner confirmed manual reboot and new DHCP
address10.49.219.156. Complete new boot journal passed unchanged Test370 startup
classifier (zero fault/suspect); freeze this actual boot’s exact priority<=3
multiset and snapshot hashes. Earlier enrollment preserved separately; no HFI/ep0
failure is adopted into this baseline. Any new unclassified fault stops the first attempt.

Three initially absent files only: event helper, exact kernel profile, disabled
unit template. One transient service (1200s backstop), never enable at boot here.
Reuse unchanged tested lifecycle/teardown parsers and isolated Test371 transaction.
One initial detached edge (3s), PC attachment (30s), unplug (15s), PC reattachment
(30s). Require same boot, Sink/Device, good battery, full raw kernel/unit journals,
unique owned unbind/bind events, actual ADB shell, device usb0 NCM address and
healthy GNOME/SSH/adbd. Windows Code43 stops; host NCM TCP alone is not a device
CPU failure. At most one exact priority3 empty ep0out dequeue message per owned
unbind, within250ms source-monotonic, per existing pinned source audit; all other
faults stop. No blanket USB error suppression.

Push registration before any device write. A read-only transport preparation
failed SSH banner: preserved separately; no identity/health or battery inferred.
Formal preflight must succeed freshly before starting. Owner cable coordination
is required. After one cycle stop service, verify original binding and remove
only the three ledger-owned files. Persistent installation is a later concrete
change after physical qualification, not part of this acceptance.

Existing current Test370 artifacts and its namespace-backed original Test331
rollback remain referenced, no new images or Windows staging. Retention window
362–371; expired361 created no image (see its registration). No new kernel tests
or full host regression: run only affected transaction, lifecycle and parser tests.

Commands: `python3 reference/boot-tests/test-371-usb-lifecycle-gmu/host_flow.py`
with `verify`, `preflight`, `install`, `attached`, `detached-again`, `reattached`,
then `restore`. First failure is durable; no retry or baseline enlargement.
