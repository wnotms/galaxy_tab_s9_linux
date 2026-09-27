# Round 34 — the CSD/IPI plan: why the wedged CPU stops answering

**2026-09-27 correction:** [STALL_TEST_WORKFLOW.md](STALL_TEST_WORKFLOW.md) supersedes the causal exclusions and trace sizing below. NULL `cur_csd` describes recorded CSD work, not all IPI execution; `rcu_barrier_handler()` takes a raw spinlock. Test-228 remains Case B; it does not establish a GIC/DAIF/firmware cause. The next gate is retained trace coverage.

**Status: the first CSD run has happened, and it returned Case B.**
`reference/boot-tests/test-228-csd-ipi-diagnostic/RESULT.md` has the evidence: two
CPUs (3 and 7) had pending CSD requests and repeatedly reported no recorded
current CSD work. The original pre-run plan is archived with test-228;
`STALL_TEST_WORKFLOW.md` holds the corrected interpretation and next steps.

## 1. Where the investigation is, after test-227

The question is no longer "which driver is stuck". It is:

> **At about 7 seconds, why does a CPU that Linux still believes is online stop
> executing an ordinary cross-CPU IPI?**

test-227 settled the previous hypothesis by removing it. With `cpuidle.off=1`
provably in effect — the framework absent, no governor registered, and **every
cluster idle state showing usage 0 *and* rejected 0** — the tablet wedged twice
on consecutive boots at the documented onset, with the documented signature and
the documented victim chain. So no PSCI suspend was ever issued and the wedge
happened anyway.

### What is downgraded, and must not be re-opened

| direction | status | the evidence |
|---|---|---|
| GPU / GMU / ACD / AOSS | **downgraded** | `msm.skip_gpu=1` wedged with the Adreno driver never registered (test-198) |
| RPMh `rpmh_write()` timeout | **downgraded** | `gts9_rpmh_debug=1` wedged with zero RPMh output (test-199) |
| cpufreq / EPSS / OSM L3 | **no demonstrated rate effect** | 2/29 against 1/29 is inconclusive, not equivalence; retain the independently justified fix |
| **PSCI / cpuidle** | **not necessary** | test-227, above |
| **active branch** | **IPI / CSD / IRQ delivery** | this document |

**Not to be run**: `no-llcc-off`, `no-cluster-idle`, per-cluster deep-idle
disable, PSCI parameter edits, any cpuidle governor A/B. Their entire subject is
the suspend parameter, which firmware never received on the wedged boots.

### The three roles in every wedge record, kept apart

test-227's record names three CPUs and only one of them is the failure:

| CPU | core | role |
|---|---|---|
| **4** | A715 (big) | **the stalled CPU** — `rcu: 4-...!`; the `!` marks it as having failed to answer the backtrace IPI |
| 6 | A710 (big) | the **detector** — `(detected by 6, ...)` |
| 1 | A510 (little) | the **reporter** — its soft-lockup stack is the canary, *not* the cause |

The victim chain is identical in all five complete records the project holds:

```
toggle_allocation_gate
  -> static_key_enable
  -> jump_label_update
  -> arch_jump_label_transform_apply
  -> kick_all_cpus_sync
  -> smp_call_function_many_cond      <- the CPU is spinning HERE
```

This is the **canary**: a CPU waiting inside `smp_call_function_many_cond()` for
another CPU that never completes its CSD. It says what is being waited for. It
does not say why the target stopped.

The historical concentration of victims on big/prime (13 of 14 pairs) remains a
**correlation and a direction only**. It is not authorization to touch big-core
voltage, frequency or idle state.

## 2. The instrument: `CONFIG_CSD_LOCK_WAIT_DEBUG`

### 2.1 Why this one, argued from the pinned source

Our canary spins in `smp_call_function_many_cond()`. Reading
`kernel/smp.c`, that function ends with:

```c
	if (run_remote && wait) {
		for_each_cpu(cpu, cfd->cpumask) {
			call_single_data_t *csd;
			csd = per_cpu_ptr(cfd->csd, cpu);
			csd_lock_wait(csd);        /* <-- the spin */
		}
	}
```

and with `CONFIG_CSD_LOCK_WAIT_DEBUG` on, `csd_lock_wait()` is not the silent
`cond_load_acquire` but:

```c
static __always_inline void csd_lock_wait(call_single_data_t *csd)
{
	if (static_branch_unlikely(&csdlock_debug_enabled)) {
		__csd_lock_wait(csd);          /* -> csd_lock_wait_toolong() */
		return;
	}
	smp_cond_load_acquire(&csd->node.u_flags, !(VAL & CSD_FLAG_LOCK));
}
```

**The instrument is on the exact instruction the canary is stuck at.** That is
the argument, and it is source-level rather than a name match.

### 2.2 What it reports, field by field

From `csd_lock_wait_toolong()` (`kernel/smp.c`), the first report is:

```
csd: Detected non-responsive CSD lock (#N) on CPU#<waiter>, waiting <ns> for CPU#<target> <func>(<info>).
```

| field | source | what it answers |
|---|---|---|
| `CPU#<waiter>` | `raw_smp_processor_id()` | which CPU is stuck waiting |
| `waiting <ns>` | `ts2 - ts0` | how long the target has been unresponsive |
| `CPU#<target>` | `csd_lock_wait_getcpu()` → `csd->node.dst` | **which CPU is unresponsive** |
| `<func>` / `<info>` | `csd->func`, `csd->info` | **what work the target was asked to do** |

and immediately after it, the line that splits the diagnosis in two:

```c
	if (cpu_cur_csd && csd != cpu_cur_csd) {
		pr_alert("\tcsd: CSD lock (#%d) handling prior %pS(%ps) request.\n", ...);
	} else {
		pr_alert("\tcsd: CSD lock (#%d) %s.\n",
			 *bug_id, !cpu_cur_csd ? "unresponsive" : "handling this request");
	}
```

Then, when the target is genuinely unresponsive:

```c
	if (cpu >= 0) {
		if (atomic_cmpxchg_acquire(&per_cpu(trigger_backtrace, cpu), 1, 0))
			dump_cpu_task(cpu);        /* the target's stack */
		if (!cpu_cur_csd) {
			pr_alert("csd: Re-sending CSD lock (#%d) IPI from CPU#%02d to CPU#%02d\n", ...);
			arch_send_call_function_single_ipi(cpu);
		}
	}
	if (firsttime)
		dump_stack();                      /* the waiter's stack */
```

So the complete first report is: **who waits, whom for, for what work, whether
the target is handling this request or an earlier one or nothing at all, the
target's task stack, and the waiter's stack.** `dump_cpu_task()` is best-effort —
it needs the target to take an IPI — so a truly wedged CPU may not produce it;
that is itself informative and is recorded as such in §4 Case B.

### 2.3 It fires earlier than anything the project has used

| signal | fires at | relative to onset |
|---|---|---|
| **CSD lock report** | `csd_lock_timeout` = **5 s** default | **before RCU, while the target is still wedged** |
| RCU stall | 21.02 s (`t=5256` jiffies at HZ=250) | onset + 21 s |
| soft lockup | 26 s | onset + 26 s or later |
| panic → reboot | softlockup_panic + panic=10 | onset + ~36 s |

The CSD report is the **earliest** usable trigger the project has, and it is the
one that describes the target CPU rather than the waiter.

### 2.4 The parameters, read out of the tree rather than taken from a search

| parameter | kind | default | unit | this round |
|---|---|---|---|---|
| `csdlock_debug=` | `__setup` (`smp.c:168`) | off unless `CSD_LOCK_WAIT_DEBUG_DEFAULT` | boolean-ish | `=1` on the cmdline **and** `_DEFAULT=y` in config |
| `csd_lock_timeout` | `module_param`, `ulong`, 0644 | **5000** | **milliseconds** | left at default |
| `panic_on_ipistall` | `module_param`, `int`, 0644 | **0 = disabled** | milliseconds | **left at 0** |

Three consequences worth stating because each is a trap:

* **The Kconfig symbol alone does nothing at runtime.** The switch is
  `DEFINE_STATIC_KEY_MAYBE(CONFIG_CSD_LOCK_WAIT_DEBUG_DEFAULT, csdlock_debug_enabled)`
  and that default is itself `n`. A build with `CSD_LOCK_WAIT_DEBUG=y` and the
  cmdline token dropped is a build whose instrument never runs — which looks
  exactly like a wedge with no CSD output. Both are therefore set, and both are
  asserted by the build script and re-checked on the device.
* **`csd_lock_timeout` and `panic_on_ipistall` are `module_param`, not `__setup`.**
  They are settable on the cmdline only because `smp.c` is built in, and they are
  additionally writable at runtime under `/sys/module/smp/parameters/`.
  `csdlock_debug=` is *not* writable after boot.
* **A built-in `module_param` is namespaced on the command line.** Verified in
  the compiled artifact rather than assumed: the strings inside the diagnostic
  `Image.gz` are `smp.csd_lock_timeout` and `smp.panic_on_ipistall`, **not** the
  bare names — `kernel/params.c` stores the module name before a dot. So the
  cmdline form is `smp.csd_lock_timeout=` / `smp.panic_on_ipistall=`, while the
  sysfs path keeps the bare name (`/sys/module/smp/parameters/csd_lock_timeout`).
  This round passes neither, but a future round that wants to shorten the
  timeout must use the prefixed form or the parameter is silently ignored — the
  same class of defect as `msm.no_gpu=1`. The project already relies on this
  convention: the cmdline carries `workqueue.panic_on_stall_time=45`, and that
  token is absent from the kernel's own unknown-parameter list on the device.

### 2.5 The arming gate, and why it is a *positive* test

A diagnostic that is not actually running looks exactly like a wedge with no CSD
output, and the plan's Case D exists because that would otherwise be read as
"CSD is not involved". So the gate must prove the instrument is live, and the
strongest proof available is a **capability that only the diagnostic kernel has**:

| check | production kernel | diagnostic kernel |
|---|---|---|
| `CONFIG_CSD_LOCK_WAIT_DEBUG` in `/proc/config.gz` | `n` | `y` |
| `/sys/module/smp/parameters/csd_lock_timeout` | **does not exist** | **exists** |
| `/sys/module/smp/parameters/panic_on_ipistall` | **does not exist** | **exists** |
| `csdlock_debug=1` on `/proc/cmdline` | absent | present |
| `csdlock_debug` in the unknown-parameter list | — | **absent** (proves the `__setup` handler consumed it) |

The first row is the decisive one, and it is already verified on the live tablet:
`ls /sys/module/smp/parameters/` is **empty** today, because both symbols are
`module_param` calls inside `#ifdef CONFIG_CSD_LOCK_WAIT_DEBUG`. The file
appearing after the flash is a capability no production kernel can fake, so it
cannot be produced by a stale image or a cmdline that failed to take. The
`unknown_params` check is the same gate the project already applies to
`gts9_rpmh_debug` and `msm.skip_gpu` — measured working on the device today,
where `softlockup_panic` and `workqueue.panic_on_stall_time` are both absent
from that list.
* **`panic_on_ipistall` stays 0.** The brief is explicit that round one collects
  information rather than making the instrument panic earlier, and the existing
  `softlockup_panic=1` → `panic=10` chain provides best-effort recovery
  when a detector and the reboot path still execute. Enabling it would also *shorten* the window in which the target's
  state can be observed.

### 2.6 The 64BIT dependency is load-bearing, not incidental

`csd->node.dst` exists only `#ifdef CONFIG_64BIT`
(`include/linux/smp_types.h`), and `csd_lock_wait_getcpu()` returns it as the
target CPU for `CSD_TYPE_SYNC`/`CSD_TYPE_ASYNC`:

```c
	csd_type = CSD_TYPE(csd);
	if (csd_type == CSD_TYPE_ASYNC || csd_type == CSD_TYPE_SYNC)
		return csd->node.dst;
	return -1;
```

`CONFIG_64BIT=y` on this target, so every report names a real CPU. Had it been
32-bit, every report would say `cpu = -1` and the round would be worthless —
which is why the build script asserts it rather than assuming it.

## 3. The candidate

**`baseline production config + CONFIG_CSD_LOCK_WAIT_DEBUG`.** Nothing else.

Selected with a new opt-in fragment, `kernel/config/gts9wifi-csd-lock.fragment`,
merged *after* the mainline fragment so the diagnostic layer can only add to or
override the production one:

```sh
GTS9_DIAG_FRAGMENT=kernel/config/gts9wifi-csd-lock.fragment \
KERNEL_OUT_DIR=$PWD/out/kernel-gts9wifi-csd-lock \
BUILD_MODULES=0 ./scripts/build-kernel.sh
```

The default build does not read the fragment at all, and the build script now
asserts the split **in both directions**: a diagnostic build fails if the symbol
did not take, and a production build fails if it did.

**Explicitly not included**, and asserted absent in the diagnostic build: no
`cpuidle.off=1`, no `msm.skip_gpu=1`, no `msm.disable_acd=1`, no
`gts9_rpmh_debug=1`, no `deferred_probe_timeout=300`, no new DPU or MMC debug, no
`loglevel` change, no bulk printk. Round one is one instrument, so that a result
is attributable to it.

## 4. The pre-registered decision rule

**Written before the candidate was built.** If the outcome disagrees with the
rule, the rule stands and the disagreement is recorded.

The round's success condition is **not** "no wedge". It is:

> **a real CPU wedge produces more target-CPU / CSD / IPI state information than
> test-227 did.**

This is failure forensics, not a rate experiment. test-227 established that 2
wedges in 4 boots is achievable, so the series is expected to be short: **stop at
the first genuine wedge with usable output.**

### Case A — the target is handling a *prior* CSD request

```
csd: Detected non-responsive CSD lock (#N) on CPU#W, waiting T ns for CPU#X f(i).
	csd: CSD lock (#N) handling prior g(j) request.
```

The target is inside an IPI handler and not returning. **Next:** investigate that
handler and the possibility of a nested or circular CSD — `g` is the function to
read, and the question is whether it can block, spin, or wait on something that
needs the waiting CPU.

### Case B — the target is `unresponsive` with no current CSD

```
csd: Detected non-responsive CSD lock (#N) on CPU#W, waiting T ns for CPU#X f(i).
	csd: CSD lock (#N) unresponsive.
csd: Re-sending CSD lock (#N) IPI from CPU#W to CPU#X
```

The target has no recorded current CSD work at the sampled instant. This
prioritises tracing the path into CSD dispatch without establishing where it stopped. **Next**, in this order: IRQ masking
(`DAIF`), GIC/SGI delivery (redistributor state), CPU exception state, the arch
timer, and firmware. A `dump_cpu_task()` stack appearing here would name the
target's last-known code and takes priority over that list.

The resend uses that same NULL sample; it is not an independent measurement
of SGI delivery. Entry/exit tracing with complete retained coverage is needed
to distinguish an unentered callback from other execution paths.

### Case C — the instrument names a specific long-running function

If the report (or the target's stack, when one is dumped) shows the CPU executing
one identifiable function for the whole interval, **that function and its
subsystem become the next round's object**, and the investigation does **not**
generalise to "a GIC problem". This case exists to stop a specific finding being
diluted into a generic theory.

### Case D — a real wedge with **no** CSD diagnostic information

**This does not mean "CSD is not involved."** It means the instrument has not
been proven live, and the following must be confirmed in this order *before* any
conclusion:

1. `CONFIG_CSD_LOCK_WAIT_DEBUG=y` in the **running** kernel's config;
2. the static key is actually enabled — `csdlock_debug=1` present on
   `/proc/cmdline`, and the token absent from the kernel's own unknown-parameter
   list (which proves an `__setup` handler consumed it);
3. the waiting path really goes through the instrumented code — i.e. the wedge's
   waiter is in `smp_call_function*()` with `SCF_WAIT`, as every recorded one is;
4. the timeout was actually reached, which at the 5 s default it must have been
   if the wedge lasted tens of seconds.

Only if all four hold may the round proceed to targeted ftrace. The forbidden
sentence is `CSD is not involved`.

### Case E — no wedge at all in the series

`not reproduced in N boots`, and **not** a result about CSD. The count, the
window and the profile identity are recorded and the series is extended or
abandoned; it does not become evidence.

## 5. Round two, if needed: targeted ftrace

One question only: **what did the target CPU last execute before it stopped?**

Design constraints, fixed now so round two does not drift:

* **Events, from the device's own `available_events`, not from a guess.** The
  verified-present candidates are `csd:csd_queue_cpu`, `csd:csd_function_entry`,
  `csd:csd_function_exit`, `ipi:ipi_raise`, `ipi:ipi_entry`, `ipi:ipi_exit`,
  `ipi:ipi_send_cpu`, `ipi:ipi_send_cpumask`, `irq:softirq_*`,
  `rcu:rcu_stall_warning`. `csd_function_entry`/`_exit` are the sharpest of
  these: they bracket the handler call itself
  (`csd_do_func()` → `trace_csd_function_entry(); func(info);
  trace_csd_function_exit();`), so **an entry with no matching exit on the target
  CPU names the exact handler it is stuck inside.**
* **`trace_clock=global` is mandatory.** The whole question is the absolute
  ordering of events on CPU 4 vs 6 vs 1, and the default `local` clock is
  explicitly not synchronised between CPUs. Cross-CPU ordering taken from a
  `local` clock may not be used for causal reasoning at all.
* **`rcupdate.rcu_cpu_stall_ftrace_dump` is the primary trigger.** At
  `kernel/rcu/tree_stall.h` the stall path calls `rcu_ftrace_dump(DUMP_ALL)`,
  which fires at onset+21 s — earlier than any panic.
* **`ftrace_dump()` is not globally single-shot.** Its `dump_running` atomic
  prevents simultaneous calls and is released at return. The RCU wrapper is
  once per callsite per boot; dumping stops tracing and consumes the ring.
  Concurrent triggers contend rather than add; a later backstop may find an
  empty buffer. Use one primary trigger and validate retained coverage.
* **`tp_printk` is not used.** It carries a documented live-lock risk on
  high-frequency events and adds nothing here, because `ftrace_dump()` reaches
  the console independently.
* **Buffer sizing is measured, not guessed.** Run the same event set on a healthy
  boot for 30–60 s, record events/second, bytes/second and the overwrite rate,
  and require the ring to cover **onset −20 s through the RCU stall**. A ring that
  holds only the last second makes the experiment invalid. Enabling the trace is
  itself an observer effect and is recorded as one — which also means a
  trace-enabled run's *rate* may not be compared to an untraced baseline.
* **`timer:*` is not enabled in the first pass.** It is high-rate. The minimal
  question is whether the target's local timer still delivers, and the
  lowest-rate tracepoint that answers it is chosen only after measuring the rate
  on a healthy boot.
* **`power:cpu_idle` may be kept as a timeline aid only.** test-227 removed idle
  as a necessary mechanism, so it may not be used to argue the wedge is idle-related.

## 6. Evidence that must be armed *before* the wedge

test-227 recorded the mistake explicitly: there is no `/proc/interrupts` or
`/proc/softirqs` snapshot from inside a wedged boot, because a wedged kernel
cannot be read and no trace was armed. **A wedged boot cannot be interrogated
after the fact**, so every instrument must already be running:

| instrument | how it survives |
|---|---|
| CSD reports | `pr_alert`, so they reach the ring and the ramoops console |
| panicked console | `pstore` → `/var/lib/systemd/pstore/console-ramoops-0` |
| the ring | `journalctl -b <n>`, retained across boots |
| an ftrace dump | only via `rcu_cpu_stall_ftrace_dump` / panic, round two |

The profile keeps `softlockup_panic=1` and `panic=10`, so a wedge reboots the
tablet when the detector and reboot path still execute; a total CPU failure
can still prevent recovery.

## 7. What this round does **not** do

* no touch, audio, charging or USB-host work;
* no flash, repartition, or write to `vbmeta`, `recovery`, `userdata` or the
  partition table — and **nothing is flashed by this round at all**;
* no revert of EPSS, OSM L3 or the 3.36 GHz prime OPP;
* **no hardware voltage, frequency, CPR or regulator change**, and no GIC MMIO
  or secure-firmware poking. The big/prime victim bias is a direction, not
  authorization;
* no re-run of GPU, ACD, RPMh-timeout, cpufreq or PSCI-idle ablations;
* no re-proposal of the already-present GICv3 fix `0d62a49ab55c` as a fix;
* no change to the production configuration. The diagnostic is a separate
  fragment, separate output directory and separate kernel.

## 8. The decision tree this produces

```
CPU wedge
│
├─ CSD debug names a handler the target is executing
│    └─ read that handler / nested CSD / deadlock          (Case A, C)
│
├─ CSD debug says target unresponsive, no current CSD
│    ├─ targeted IPI/CSD trace: SGI raised, no ipi_entry
│    │      └─ GIC / IRQ masking / firmware direction
│    ├─ ipi_entry present, no ipi_exit
│    │      └─ IPI handler / callback direction
│    └─ SGI fine but arch timer and other PPIs stop
│           └─ local interrupt / exception state direction
│
└─ no CSD output
     └─ prove the instrument was live FIRST (Case D), then
        targeted ftrace with RCU-stall-triggered dump
```

## Related

* `reference/boot-tests/test-227-cpuidle-off-run/` — the result that put this
  branch in play, and the three-CPU role table
* `docs/CPU_WEDGE_EVIDENCE.md` — the signature, the rate, the wedged CPUs
* `docs/SM8550_IDLE_STATE_ANALYSIS.md` — the states that were never entered
* `kernel/config/gts9wifi-csd-lock.fragment` — the diagnostic configuration


---

# 9. Outcome of the first run (test-228) — Case B

The raw evidence is in
`reference/boot-tests/test-228-csd-ipi-diagnostic/evidence/`.
The recorded target CPUs are 3 and 7, with pending `do_nothing` and
`rcu_barrier_handler` work. Both report `unresponsive` and both receive resends
(two each in the archived CSD excerpt). This matches **Case B** as an observation.
It does not establish the cause or prove the targets were outside all IPI paths.

`cur_csd` records selected CSD callback execution. A NULL sample does not exclude
execution before that recording point, other kinds of IPI, other IRQ handlers,
or prior corruption. Also, `rcu_barrier_handler()` takes
`raw_spin_lock(&rcu_state.barrier_lock)` in the pinned kernel. Earlier claims that
both handlers are lock-free and every dependency was permanently excluded were
incorrect. The unchanged RCU softirq counter establishes no RCU softirq progress,
not a direct observation of DAIF or all local interrupts.

## Round 2, made specific by this result

The next question remains whether the relevant target reaches `ipi_entry` and
then `csd_function_entry/exit`. A missing event is interpretable only after
proving the relevant interval survived both the per-CPU ring and the persistent
sink. `trace_clock=global` remains mandatory and `timer:*` stays out of the first pass.

The prior 8 MiB / 57 s sizing claim is withdrawn: the measurement was text output,
not binary per-CPU ring use. The 896 KiB ramoops console cannot hold that proposed
multi-MiB dump. Run `scripts/prepare-csd-trace.py` for the offline capacity audit;
`docs/STALL_TEST_WORKFLOW.md` defines calibration and persistence gates. No new
flash candidate is ready until they pass.

## Runner follow-up

The original count/index correction fixed the observed test-228 error, but
journal vacuuming and failed collection can still invalidate total-count
arithmetic. The current runner selects the first boot after a retained boot-ID
anchor and fetches by immutable ID. It archives the raw input for offline replay,
counts CSD non-response directly, and treats an unexpected restart without a
positive failure signature as unattributed. See the current workflow for stop
rules and transport limitations.
