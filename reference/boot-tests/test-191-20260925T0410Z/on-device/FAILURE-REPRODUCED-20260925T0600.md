# The failure sequence, reproduced on a second boot, with the same victim

`on-device-pstore-20260925T0600/console-ramoops-0` is the pstore console record of
the boot that ran after the recovery request at ~06:00Z - the boot the operator saw
hang on the boot log. It was archived by `systemd-pstore` on the next boot and pulled
before it aged out. It is the **second complete record** of this failure, and it
reproduces the first one's shape.

## The two records, side by side

| | 04:57Z (round 22) | 06:00Z (this one) |
|---|---|---|
| frame-done flood begins | 6.755 s | ~52.5 s |
| `mmc1: Timeout waiting for hardware interrupt` | 21.987 s | 67.043 s |
| `rcu: detected stalls on CPUs/tasks` | 27.727 s | 72.179 s |
| soft lockup | 32.275 s, **CPU#4**, 27 s | 77.124 s, **CPU#3**, 26 s |
| workqueue | `events_unbound toggle_allocation_gate` | `events_unbound toggle_allocation_gate` |
| stack | `smp_call_function_many_cond <- kick_all_cpus_sync <- arch_jump_label_transform_apply <- __jump_label_update <- jump_label_update <- static_key_enable <- toggle_allocation_gate` | **identical** |
| `SMP: failed to stop secondary CPUs` | 0,3,6-7 | 0,4,7 |
| panic reason | `softlockup: hung tasks` | same class, then `Rebooting in 10 seconds..` |

Four things follow.

1. **The order is reproducible**: display frame-done, then microSD, then RCU, then
   soft-lockup panic. Two independent boots, same sequence, ~45 s apart in absolute
   onset. That ordering was inferred from one record in round 22; it now has a
   second sample.
2. **The victim is the same worker both times**, and it is still a victim.
   `toggle_allocation_gate` calls `jump_label_update()`, which calls
   `kick_all_cpus_sync()` - a synchronous cross-CPU call that cannot return while
   any CPU is not answering. So this worker is a **canary**, not a cause: it is
   simply the work item most likely to be caught waiting for a frozen CPU. Its
   appearance in all three records is expected and carries no causal information.
3. **The onset time is not fixed.** 6.8 s in one boot, 52.5 s in this one. The
   brief's "13.3-14.3 s window" is a third, different instance again. Whatever the
   trigger is, it is not tied to a fixed kernel-init milestone.
4. **A different set of CPUs was unreachable each time** - `0,3,6,7` and `0,4,7` -
   so the affected set varies while the big/prime bias
   (`docs/CPU_WEDGE_EVIDENCE.md`: 13 of 14 targets) is preserved.

## And one thing this record shows that the panicking variant does not

The record ends `[78.699704] Rebooting in 10 seconds..`. The operator reports that
the tablet did **not** restart, and a live kernel was measured afterwards: ARP
resolved, and ICMP answered 3/3 at 2 ms fifteen minutes later, while the console
refused writes and sshd was absent. So at least one boot in this chain reached
userspace, failed, and kept answering the network while every other instrument said
"dead" - `scripts/gts9-kernel-alive.sh` exists for exactly that state, and
`reference/boot-tests/test-191-20260925T0410Z/FLASH-ATTEMPT-1.md` §8 has the
measurements.

## What this does not say

It does not say the display failure *causes* the CPU failure. The two records
establish that the display symptom comes first and consistently, which is why
section 9 of `FAILED-BOOT-20260925T0457.md` reads the DPU's first line from the
source and finds it a handled early-return from the commit path rather than a fault.
The candidate trigger there - a boot-time display commit racing the encoder's state
- is a hypothesis with a cheap userspace A/B attached, and nothing more.
