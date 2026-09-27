# Test 237: automatic RCU snapshot and controlled-panic retention

Owner authorized the next round, including diagnostic build/flash/hardware tests.
This is a single instrumentation calibration, not a spontaneous CPU failure
reproduction or a wedge series. Production defaults and rootfs are unchanged.

Use patches 0022 + 0024 + opt-in 0025. Patch 0025 provides a root-only,
once-per-boot trigger, gated by test_enable=1 and the active X710 instrument.
A normal-priority kthread bound to CPU 0 holds a PREEMPT_RCU reader for a
35-second monotonic deadline, with interrupts and preemption enabled. It
requests a grace period via call_rcu; the callback only marks completion.
The existing real RCU stall tracepoint must invoke the unchanged auto dumper.
The deadline is not a guarantee on already broken hardware. No direct fake
tracepoint invocation, no disabled IRQ/preemption loop and no RT thread.

Before injection require a source boot responsive for >=150 seconds, no
positive unexplained CPU failure, READY, ECC64, watchdog 1/1/1/10, printk
admitting level 0, RCU timeout 21 seconds, stall warnings unsuppressed and
panic_on_rcu_stall=0. Save immutable source boot/capture IDs. Trigger once.
Require identified TEST_BEGIN/END, finished=1 and gp_done=1, a complete valid
58-line automatic snapshot with trigger=rcu, and continued responsiveness.
Any genuine CPU IPI non-response is an unexpected failure: stop calibration.
Do not count the deliberate reader stall as evidence of the original fault.

Fetch and verify the complete live source snapshot on the host before panic.
Preserve incomplete fetches and retry retrieval only, never re-trigger. Save
source journal and boot list, sync disk, verify panic=10, then issue one root
SysRq c. Source and immediate observer use the same ECC64 layout. Pull raw
pstore twice before slower journal queries; compare device/raw hashes, unique
source capture and exact canonical source markers, ECC bad-block count and
retained boot adjacency. Require actual panic evidence; normal reboot is not
an acceptable substitute. Synthetic RCU capture plus later panic tests those
paths, not simultaneous total CPU failure or every corruption pattern.

Build and package before flashing. Verify backups and all five partitions;
write only boot/vendor_boot with complete readbacks. Recover via established
BCB helper + plain reboot, never reboot recovery or live USB gadget changes.
If transport fails, retain timeouts and use TWRP disk journals (including
.journal~ and systemd-pstore FILE bytes) for attribution and rollback.
Restore original images, verify all five hashes, and observe final production
boot >=150 seconds with its journal; responsiveness alone is not a clean pass.
