# Test247 execution record

run_target.py completed its sole candidate deployment, then intentionally exited1
when observe.run classified failure_observed. It did not restart the target.
The kernel itself panicked and rebooted into the immediate observer.

Read-only observer collection preserved the target's immutable-ID full journal
and two raw pulls of each console/panic pstore file, checked against device
SHA-256 before and after. failure-live/identity-process was already an observer
and is never used as failed-task process evidence.

Restoration required failure_observed, both verified pstore copies, and a fresh
identity check of observer ca2235ae-e5c9-4129-858c-9cea934a2c52. It then called
control.recover('to-recovery'), poll(recovery=True), recovery_capture,
modules.swap('module-restore', restore=True), verified all181 hashes of the
owned .gts9-test247-tested directory before removing that directory, restored
images through control.flash('restore', restore=True), and used modules.reboot
with both restoration records before observe.run(production=True). This host
session exited0. The later check_transport.py verified the same production boot.
All actual remote commands/statuses/timestamps are preserved in phase JSON files.
