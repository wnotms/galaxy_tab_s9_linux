# Test 241: calibrate pseudo-NMI capture through ordinary IRQ masking

The CPU-stall repair goal remains open. Test 240 only validated a separate
BBM fix's functional behavior. This trial returns to unchanged baseline code
plus recorder 0022/ECC64 0024, adding ARM64_PSEUDO_NMI and calibration 0027.
Do not combine BBM patch 0026 or RCU injection 0025. Defaults, power settings,
rootfs and USB coexistence remain unchanged. Config changes are opt-in.

Question: can an actual higher-priority backtrace interrupt CPU0 while normal
local IRQs are masked and record the interrupted PC/stack? Existing builds
used ordinary backtrace IPIs. CPU_BACKTRACE is excluded from normal IPI trace
points; a tiny calibration-only observation hook records the actual callback
context and interrupted registers without printing/waiting/allocating.

The root-only once-per-boot trigger requires enable=1, X710/8 CPUs, running
system and actual priority masking. Normal-priority kthreads are bound to
CPU0 (receiver) and CPU1 (sender). Setup waits are bounded at 5 seconds. The
receiver uses preempt_disable + local_irq_save/restore, never raw DAIF changes,
and a 200 ms monotonic-fast deadline. The sender makes the standard single-CPU
backtrace request (pinned helper has a 10 s timeout). The holding flag clears
before restoring IRQs, rejecting delayed ordinary backtraces. NMI printing
may extend elapsed masked time beyond the loop deadline; this is not a hard
hardware recovery guarantee. No CPU hotplug or forced panic.

Runtime gate: successful GIC Pseudo-NMIs enabled message, no NMI registration
warning, helper READY prio_masking=1, watchdog 1/1/1/10, ECC64 and >=150-second
healthy candidate boot. Save immutable boot/lastactivity/calibration IDs,
notes, per-boot relocation and exact symbols. Use console loglevel=5 so pr_warn
and default-level backtrace registers/stacks reach the console sink; loglevel4
would filter them. This logging change is explicit and must be checked live.

Trigger once, require both workers complete, error=0, holding=0 and observed=1,
in_nmi=1, interrupted PMR showing ordinary IRQs disabled, PC nonzero and seen
within start/end. Require actual target backtrace with gts9_pnmi_masked_region
in its interrupted stack; symbols identify this kernel, not a previous boot.
Keep delayed/missing response or metadata mismatch inconclusive, not a pass.
Record actual masked duration. Preserve console/journal output, then observe
>=60 seconds without unexplained CPU/RCU/workqueue failure. No natural-failure
series under this calibration plan; broader CPU repair is not established.

Before flashing, extend this plan with one direct normal Debian reboot after
the successful calibration/post-observation. Keep the identical ECC64 kernel
for the immediate observer and do not trigger calibration again. Save the
source kernel journal at priorities 0..4 (the messages admitted by console
threshold 5), then compare the unique BEGIN-to-END region against two raw
pstore pulls and their device hash. Strip only timestamp/task prefixes from
pstore and transport CRLF from journal; require exact payload bytes, the same
calibration ID, zero unrecoverable ECC blocks and retained adjacent boot IDs.
This validates the newly admitted backtrace's warm-reboot retention, not
delivery during a natural CPU failure or retention through every crash path.

Build and validate before flashing. Verify backups/device/five partition
hashes; flash only boot/vendor_boot with full readbacks. Restore originals
through BCB helper + plain reboot/TWRP, never reboot recovery or shared-gadget
changes. Verify all-five hashes and a separate >=150-second production boot.
Stop on unexpected failure and collect evidence; hardware/firmware can still
prevent even pseudo-NMI delivery or automatic reset.
