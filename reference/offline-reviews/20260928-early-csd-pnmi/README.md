# Earlier natural target capture through the existing CSD timeout path

Test245 proves a CPU1 synchronization waiter for CPU2, but RCU's request at
30.68 s was interrupted by CPU1's panic at36.54 s. Test246 combined pseudo-NMI
with matched modules and had no fault in its single120 s window. Both budgets
are closed. This review chooses an earlier request point from the actual wait
path, rather than another identical boot or a new speculative kernel fix.

Pinned kernel/smp.c final synchronous wait calls csd_lock_wait(). With
CSD_LOCK_WAIT_DEBUG compiled and the static key active, __csd_lock_wait()
checks elapsed time and first reports after the default5000 ms. The report
names the waiter, destination, function and whether cur_csd is set; the
per-target atomic gate then invokes dump_cpu_task(). kernel/sched/core.c
routes that through trigger_single_cpu_backtrace(), arm64's backtrace IPI and
lib/nmi_backtrace.c. With246's configured and runtime-enabled pseudo-NMI, this
can bypass normal PMR masking. It cannot bypass every DAIF/firmware/hardware
failure, and source reachability is not a runtime capture guarantee.

This is already upstream code. No local timeout handler or new patch is
needed. The additional fragment enables only CSD_LOCK_WAIT_DEBUG and its
DEFAULT key relative to246. Keep the compiled patches0022+0024+0026,
pseudo-NMI runtime flag, LA1/ECC64, warning-level console and1/1/1/10 arming.
No synthetic trigger, CSD panic, watchdog-threshold change, power change or
suppression of KFENCE. CSD diagnostics add time reads/per-CPU stores/barriers,
print output and possibly re-send a normal IPI; observer perturbation must
remain explicit. They may change timing or recovery, not just observation.

The standard NMI backtrace wait is bounded at10 s and touches the waiting
CPU's soft-lockup watchdog, so enabling this path can change which CPU panics
and when. A global backtrace flag serializes simultaneous requests: a request
may return without a new IPI while another backtrace is active. The per-target
CSD trigger gate and target's IPI processing also affect repeated attempts.
No promise of first-stall delivery, complete stack or guaranteed recovery.
The5000 ms threshold starts at this waiter, not the unknown fault onset.

Preflight must verify CONFIG and exact binary CSD call path, runtime parameters
/sys/module/smp/parameters/csd_lock_timeout=5000 and panic_on_ipistall=0,
cmdlinecsdlock_debug=1, plus the existing GIC/notes/six-anchor/capture gates.
Kernel built-in module_param boot arguments require the smp. prefix; do not
use bare csd_lock_timeout= to claim a setting changed. This trial relies on
the verified default and reads sysfs instead of changing it.

Build matching modules and inspect the whole installed-file manifest again;
rollback must restore original modules and both images. Keep kernel pin and
DTB unchanged. A new code/config difference must be accounted for before
hardware. Test247 may register one120 s startup target, full capture from the
first response, stop on the first positive failure/suspect/transport loss,
with at most20 s extra collection. No workload or loop of clean boots. A
clean window closes this trial without establishing repair. Any natural
snapshot/stack must be attributed to the exact target, including source times
and its own relocation. Restore the original pair and check production120 s.

Archived source excerpts and full-file hashes document the inspected code;
no compile, deployment, or natural-fault result is implied by this review.

Follow-up gate: kernel/rcu/tree_stall.h defaults csd_lock_suppress_rcu_stall to
false. When true plus csd_lock_is_stuck(), it suppresses the detailed RCU report
and its tracepoint-triggered last-activity snapshot. Keep this parameter false
and verify /sys/module/rcutree/parameters/csd_lock_suppress_rcu_stall=N on the
candidate. Original production also reads N. This is a read-only gate, not an
extra RCU-behaviour setting or a change to timeout timing.
