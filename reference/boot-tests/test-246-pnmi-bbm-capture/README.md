# Test246 preparation: capture the failed target through pseudo-NMI

Motivated by the actual test245 startup fault, not another successful boot.
This explicitly registered combined diagnostic keeps245's 0022+0024+0026,
adds CONFIG_ARM64_PSEUDO_NMI and its runtime flag, and uses loglevel5 so the
standard warning-level backtrace can reach the retained console. No calibration
helper0027, synthetic workload, deliberate fault, power/frequency change or
KFENCE suppression. The intended evidence is the failed target's PC/stack;
CPU1's prior synchronization-waiter stack is insufficient.

Build kernel and modules with the same config and save exact symbols/hashes.
Compare the config with245 and account for every difference. Verify DTB/release
unchanged; validate package before any flash. Module compatibility and reversible
deployment/rollback must be made concrete before hardware, including actual
installed-file backup/hashes. See the module compatibility offline review.
Do not reuse an unrelated known release string as proof of compatible inlines.

Prospective budget: ONE TWRP-entry candidate target, **120 s total uptime**,
full JSON from the first connection and independent notes/six anchors/READY/
capture ID/ECC64/1-1-1-10/GIC positive runtime checks. Stop on first failure,
suspect timeout, missing attribution or unexpected reboot; allow at most20 s
extra capture after positive failure. No workload or idle/fault injection.
If the panic recovers, identify the immediate retained successor and pull two
raw copies with device hashes before further reboot. Capture IDs/relocation
must belong to the failed target. No missing-event inference or clean=repair.

Restore original boot/vendor_boot and any temporarily replaced module files;
verify all five partition hashes and the module backup manifest. Restore the
original production profile and observe its startup to120 s with ADB/NCM SSH
checks. The already documented UPower217/USER failure is tracked separately;
any such health result remains incomplete and is not reset/hidden as a pass.
No new unrelated failed service is acceptable without review. Preserve USB
configuration. Use the BCB helper plus an ordinary reboot transaction, never
reboot recovery. Manual TWRP is needed only if software recovery actually fails.

This file registers preparation/scope; it is not a build, deployment or capture
result. No further boot beyond this one is authorized by the trial budget.
