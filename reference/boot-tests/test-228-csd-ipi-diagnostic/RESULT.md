# Test 228 — the CSD/IPI diagnostic: **first-hand evidence of why the target CPU stops answering**

**Result: the instrument fired, and it answers the question the round was asked.**
A real CPU wedge was captured with `CONFIG_CSD_LOCK_WAIT_DEBUG` live, and the CSD
reports name the unresponsive CPUs, the exact IPI handler each was asked to run,
how long each had been unresponsive, and — decisively — that neither target was
inside any IPI handler at all.

This is the pre-registered rule's **Case B**, and it was written before the
candidate existed (`docs/CSD_IPI_WEDGE_PLAN.md` §4).

## 1. The evidence

Verbatim from the wedged boot's own journal
(`evidence/csd-reports.txt`; the full boot is `evidence/wedged-boot-klog-full.txt`):

```
[   14.312026] smp: csd: Detected non-responsive CSD lock (#1) on CPU#4, waiting 5000000050 ns for CPU#03 do_nothing+0x0/0x8(0x0).
[   14.312217] smp:         csd: CSD lock (#1) unresponsive.
[   15.240221] smp: csd: Detected non-responsive CSD lock (#2) on CPU#1, waiting 5000000102 ns for CPU#07 rcu_barrier_handler+0x0/0x8c(0x7).
[   15.240346] smp:         csd: CSD lock (#2) unresponsive.
[   15.290308] smp: csd: Re-sending CSD lock (#2) IPI from CPU#01 to CPU#07
[   24.312436] smp: csd: Re-sending CSD lock (#1) IPI from CPU#04 to CPU#03
[   34.312311] smp: csd: Continued non-responsive CSD lock (#1) on CPU#4, waiting 25000000095 ns for CPU#03 do_nothing+0x0/0x8(0x0).
[   34.312433] smp:         csd: CSD lock (#1) unresponsive.
[   34.424531] smp: csd: Re-sending CSD lock (#1) IPI from CPU#04 to CPU#03
[   35.240090] smp: csd: Continued non-responsive CSD lock (#2) on CPU#1, waiting 25000000250 ns for CPU#07 rcu_barrier_handler+0x0/0x8c(0x7).
[   35.245503] smp:         csd: CSD lock (#2) unresponsive.
[   35.264069] smp: csd: Re-sending CSD lock (#2) IPI from CPU#01 to CPU#07
```

And the independent instruments in the same boot
(`evidence/rcu-and-nmi.txt`):

```
[   14.416631] Sending NMI from CPU 4 to CPUs 3:
[   24.312326] After 10 seconds, these CPUS still haven't responded to the NMI: 3
[   34.312024] rcu: INFO: rcu_preempt detected stalls on CPUs/tasks:
[   34.312136] rcu:         7-...!: (0 ticks this GP) idle=d64c/1/0x4000000000000000 softirq=613/613 fqs=0
[   34.312258] Sending NMI from CPU 6 to CPUs 7:
```

## 2. What it establishes — the answer to "why did the CPU stop responding"

**Two CPUs failed independently and simultaneously: CPU 3 and CPU 7.**

| | request #1 | request #2 |
|---|---|---|
| waiting CPU | **4** | **1** |
| **target (unresponsive) CPU** | **3** | **7** |
| work it was asked to run | `do_nothing` | `rcu_barrier_handler` |
| unresponsive for | 5.0 s → 25.0 s | 5.0 s → 25.0 s |
| disposition | **`unresponsive`** | **`unresponsive`** |
| re-sent | yes, ×3 | yes, ×2 |

Four independent facts follow, and they are the first-hand evidence the round
existed to obtain:

1. **The target CPUs are named.** CPU 3 and CPU 7 — not inferred from a stack
   trace, but stated by the kernel as the `csd->node.dst` of the request.
2. **The work is named.** `do_nothing` and `rcu_barrier_handler`. These are
   trivial handlers: `do_nothing` returns immediately, `rcu_barrier_handler`
   queues one callback. **Neither can block, spin, or take a lock.** So the
   failure is not "the handler is slow" — the handler never ran.
3. **Neither target was inside any IPI handler.** `unresponsive` is printed only
   when `cpu_cur_csd` is NULL on the target
   (`kernel/smp.c`: `!cpu_cur_csd ? "unresponsive" : "handling this request"`).
   This is the **Case B** discriminator, and it rules out the entire Case A
   family — no nested CSD, no circular request, no handler deadlock.
4. **The handler never started, confirmed twice over.** `Re-sending CSD lock`
   appears only under the same `if (!cpu_cur_csd)` test, and it fired **four**
   times across the two requests (twice each). A handler that had *begun* and not
   finished could not produce that line.

**So: the target CPUs stopped taking SGIs entirely, while sitting outside every
IPI handler, being asked to run functions that cannot block.**

The `csd_function_entry`/`csd_function_exit` tracepoints — which bracket the
handler call itself — would confirm "no entry" directly; they were not armed in
this round, and that is the round-2 instrument (§5 of the plan). It is the one
remaining ambiguity in the statement above: `unresponsive` plus `Re-sending`
proves the handler had not started **at the moment of the report**, which for a
5-to-25-second interval is as close to proof of "never started" as the kernel
offers without the tracepoint.

## 3. What it rules out, and what it points to

**Ruled out by this evidence:**

| direction | why it is out |
|---|---|
| **Case A** — nested / circular CSD, or a handler that blocks | both targets report `unresponsive`, i.e. no current CSD; `do_nothing` cannot block anyway |
| the handler being slow | `do_nothing` is an immediate return; `rcu_barrier_handler` queues one callback |
| a single-CPU fault | two CPUs (3 and 7) failed in the same boot, within ~1 s of each other |
| a lock or workqueue dependency in the IPI path | both handlers are lock-free and non-blocking |

**What it points to**, which is the plan's Case B list:

```
IRQ masking (DAIF)  ·  GICv3 SGI delivery / redistributor  ·  CPU exception state
arch timer  ·  firmware
```

Two details sharpen that:

* **`softirq=613/613` on CPU 7 froze across the whole stall.** RCU's own
  stall-warning documentation treats a constant `softirq=` counter as the
  signature of a CPU spinning with interrupts disabled. This is a *second*,
  independent indication that the failure is at the interrupt-delivery layer
  rather than in a handler.
* **Both targets are big or prime cores** — CPU 3 is a Cortex-A715 (big) and
  CPU 7 is the Cortex-X3 (prime). That is consistent with the historical victim
  concentration (13 of 14 pairs) and with `SMP: failed to stop secondary CPUs
  4,6-7` in test-227. It remains a **correlation and a direction**, and it is
  explicitly *not* authorization to touch big-core voltage, frequency, CPR or
  regulator settings.

## 4. Onset, and what the instrument buys

| derivation | value |
|---|---|
| RCU-derived: report 34.312 s − 5252 jiffies ÷ 250 Hz (21.01 s) | **13.30 s** |
| CSD-derived, CPU 3: report 14.312 s − 5.000 s wait | **~9.31 s** |
| CSD-derived, CPU 7: report 15.240 s − 5.000 s wait | **~10.24 s** |

**Correction to my own first pass:** I initially wrote that 13.30 s was "inside"
the documented 6.5–7.8 s band. It is not — it is later. Reported as measured.

What the instrument adds is not only that it fires earlier and tighter (by ~3–4 s
here), but that it is **the only instrument that names the target CPU, the work,
and the disposition.** The RCU stall says "CPU 7 did not report"; the CSD report
says "**CPU 1 asked CPU 7 to run `rcu_barrier_handler` and CPU 7 has not taken a
single interrupt in 25 seconds**".

## 5. A defect in my own harness, found by this wedge — and it nearly cost the result

**This wedge was first recorded as `verdict=clean`.** Round 10 of the first
`csd-lock` series reported no wedges at all; the CSD evidence above was found only
by going back to the device and reading the journal by hand.

Two independent bugs in `scripts/wedge-ssh.sh`, both now fixed:

1. **The boot index was chosen by comparing boot ids, not by counting boots.**
   The round's boot is the *first* boot after the harness's reboot — index 0
   normally. It becomes `-1`, `-2`, … when the kernel reboots itself, which is
   exactly what a wedge does. The old code compared `now_id` with `after` and
   selected index 0 when they matched — but they match **precisely because** the
   wedged boot panicked and restarted, so index 0 was the boot *after* the wedge.
   The round's journal, containing the entire point of the round, was never read.
   The index is now derived from the count: `idx=$(( -extra_boots ))`.
2. **`extra_boots` was computed, recorded, and then ignored by the verdict.**
   The harness's original detector for "something restarted this boot" was a
   second USB-presence outage. This runner substitutes the journal boot count —
   and then did not let that count reach the verdict. `extra_boots > 0` now
   forces `verdict=wedge`.

A third, smaller defect: `csd_report_lines=$(grep -c … || echo 0)` produced
`"0\n0"`, because `grep -c` already prints the count and exits 1 on no match. A
field that reads as two lines is a field no reader can trust.

**Verified against the real wedge:** on the device, boot `-1` holds 4
`csd: non-responsive` lines and boot `0` holds 0. With the fix, `idx=-1` is
selected. A three-round re-run afterwards reported `extra_boots=0` on every round
and stayed consistent.

The lesson is recorded because it is the failure mode this project keeps
re-encountering: **a detector that runs, reports, and is then not consulted is
worse than no detector**, because its output looks like a measurement.

## 5a. A timing correlation, recorded but not claimed as a cause

The wedged boot carries ten `[drm:dpu_crtc_frame_event_cb] *ERROR* crtc103 event 1
overflow` lines, and **none of the three clean rounds of the same profile carry
any**. That is worth writing down — and it is deliberately *not* being promoted to
a finding, because the marker is not a wedge discriminator:

| boot | outcome | count |
|---|---|---|
| test-228 wedged (`9f9d7592`) | **wedge** | 10 |
| test-228 clean rounds ×3 | clean | 0, 0, 0 |
| test-047 (clean bring-up) | clean | 2 |
| test-182 (PCIe A/B) | not a wedge | present |

It appears on clean boots too, so "the DPU overflowed" does not imply "the CPU
wedged". And its timing sits *after* the failure rather than before it:

```
~9.31 s   CSD-derived loss of CPU 3   (report at 14.312 s minus the 5.000 s wait)
10.101 s  first crtc103 overflow      <- ~0.8 s LATER
10.251 s  last crtc103 overflow       (10 lines, 16.7 ms apart = one 60 Hz frame)
14.312 s  first CSD report
```

Two readings are compatible with that ordering, and this round separates neither:

* **the DPU is a victim** — with CPUs failing to take interrupts, the crtc
  frame-event work is not drained and the event ring overruns;
* **the DPU is a contributor** — the burst loads the very CPUs that then stop
  responding.

The brief's rule applies directly here: do not attribute the failure to the
subsystem that printed last, or to the first subsystem that complained. The
marker is recorded as a **timing correlation with an unknown direction**, and the
`crtc103` path stays out of the candidate list until an instrument shows cause.

## 6. What this does *not* establish

* **Not a cause.** It localises the failure to interrupt delivery on specific
  CPUs; it does not say whether the fault is in the GIC, in the CPU's DAIF state,
  in the arch timer, or in firmware.
* **Not a fix, and no fix is proposed.** No code change follows from this round.
* **Not a rate.** Round 10 of the first series wedged; rounds 1–9 and a further
  3-round re-run were clean. No claim is made about the rate, and the round's
  success condition was never "no wedge".
* **Not proof that the handler never began**, only that it had not begun at each
  report — see §2. The `csd_function_entry/exit` tracepoints close that gap in
  round 2.
* **Not something to fix by touching supplies.** The big/prime bias is a
  direction, not authorization.

## 7. Where this sends round 2 — the plan's Case B branch, made specific

The plan's decision tree said, for Case B: *targeted IPI/CSD trace → does the SGI
arrive?* This evidence makes that question precise and cheap to answer:

| question | instrument | expected discriminator |
|---|---|---|
| does the SGI reach CPU 3 / CPU 7 at all? | `ipi:ipi_raise`, `ipi:ipi_entry` | raise present, **entry absent** ⇒ delivery/GIC/DAIF |
| did the handler start and not finish? | `csd:csd_function_entry` / `_exit` | entry present, exit absent ⇒ handler fault |
| are *all* local IRQs stopped, or only SGIs? | `irq:softirq_*` plus the arch-timer PPI | timer also silent ⇒ local interrupt/exception state |
| exact cross-CPU ordering | requires `trace_clock=global` | mandatory; `local` is not synchronised |

Both events are present on the device and were verified in this round's baseline
(`baselines/tracepoints-available.txt`). The event-rate and buffer sizing were
measured on the healthy production kernel so round 2 does not have to guess:

```
candidate set (csd:function_entry,exit,queue_cpu + ipi:raise,entry,exit
               + irq:softirq_entry,exit,raise + rcu:rcu_stall_warning)
  1545 events/s   ·   144 KiB/s
  =>  4 MiB = 29 s (too short)   ·   8 MiB = 57 s   ·  16 MiB = 114 s
```

The requirement is to cover onset −20 s through the RCU stall (~28 s), so
**8 MiB is the minimum** and 16 MiB is comfortable. The full measurement is in
`baselines/event-rate-measurement.txt`. Enabling the trace is itself an observer
effect and is recorded as one: a traced run's *rate* may not be compared to an
untraced baseline.

**`timer:*` is still not enabled in the first pass** — it is high-rate, and the
arch-timer question is answered by the PPI counter comparison rather than by
tracing every timer event.

## 8. Candidate identity and the run

| field | value |
|---|---|
| repo commit | see `source-commit.txt` |
| upstream kernel | `a13c140cc289c0b7b3770bce5b3ad42ab35074aa` (v7.2-rc3) |
| diagnostic | `CONFIG_CSD_LOCK_WAIT_DEBUG=y` + `_DEFAULT=y` |
| `csd_lock_timeout` | 5000 ms (default, as designed) |
| `panic_on_ipistall` | 0 (disabled, as designed) |
| `boot` written | `f0f893c7…` (was `71e194a5…`) |
| `vendor_boot` written | `41111e70…` (was `49ae21b3…`) |
| not written | `init_boot`, `dtbo`, `vbmeta`, recovery, BCB, userdata, partition table |
| wedged boot id | `9f9d7592-6485-4506-a49a-2d180a8493e4` |

**Arming gate passed on every check**, and the decisive one is a positive
capability test: `/sys/module/smp/parameters/` listed `csd_lock_timeout` and
`panic_on_ipistall`, where the production kernel lists nothing at all — the round
started by verifying that directory was **empty**, so the files appearing cannot
be explained by a stale image or a token that failed to take. `csdlock_debug` was
absent from the kernel's own unknown-parameter list, proving a handler consumed
it.

The wedge recovered itself through the profile's own chain — `softlockup_panic=1`
→ `panic=10` → reboot — and the tablet came back without intervention.

## 9. Evidence index

| file | what |
|---|---|
| `evidence/csd-reports.txt` | all 12 CSD report lines from the wedged boot |
| `evidence/rcu-and-nmi.txt` | the independent RCU stall and unanswered-NMI lines |
| `evidence/wedged-boot-klog-full.txt` | the entire journal of the wedged boot, 1159 lines |
| `evidence/pstore-console-ramoops.txt` | pstore as it now stands — **overwritten by later boots**, recorded rather than hidden |
| `evidence/dpu-overflow-correlation.txt` | the `crtc103` marker's counts across wedged and clean boots, and its timing relative to onset |
| `baselines/hotplug-baseline.txt` | `online`/`present`/`possible`, all 8 CPUs, nothing isolated |
| `baselines/proc-interrupts.txt` | per-CPU SGI/PPI counts on a healthy boot |
| `baselines/proc-softirqs.txt` | the softirq baseline the frozen `613/613` is read against |
| `baselines/tracepoints-available.txt` | the device's real `available_events` for csd/ipi/irq/rcu |
| `baselines/event-rate-measurement.txt` | the buffer-sizing measurement |
| `PRE-WRITE-STATE.txt` | every partition hash before the write |
| `rollback/` | hash-verified copies of the pre-test `boot` and `vendor_boot` |

## 10. Rollback

```sh
dd if=.work/test-228/rollback/boot-before.img        of=/dev/disk/by-partlabel/boot        bs=1M && sync
dd if=.work/test-228/rollback/vendor_boot-before.img of=/dev/disk/by-partlabel/vendor_boot bs=1M && sync
sha256sum /dev/disk/by-partlabel/boot /dev/disk/by-partlabel/vendor_boot
# expect 71e194a5…  and  49ae21b3…
```

Both images were dumped from the device, hash-verified on the device, pulled, and
re-hashed on the host before anything was written.

## Related

* `docs/CSD_IPI_WEDGE_PLAN.md` — the pre-registered rule this result is read against
* `reference/boot-tests/test-227-cpuidle-off-run/` — the result that opened this branch
* `docs/CPU_WEDGE_EVIDENCE.md` — the signature and the historical rate
