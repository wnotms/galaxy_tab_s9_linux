# The CPU-wedge plan: is PSCI cpuidle necessary for the wedge?

Round 33. The hypothesis under test, stated before any data:

> Some CPU or CPU cluster enters a PSCI deep-idle state and, at a low rate, does
> not return correctly. The CPU is then online but not executing or taking
> interrupts, which is what the RCU stall, the workqueue lockup and the
> unanswered IPI are all downstream of.

**This is a hypothesis, not a conclusion, and nothing in this document claims a
fix.** The terms used are the brief's: `candidate`, `hypothesis`,
`not reproduced`, `downgraded`, `correlated`, `necessary`, `not necessary`,
`physically verified`.

## 1. What this round inherits, and what it does not re-open

Taken as given from `docs/CPU_WEDGE_EVIDENCE.md`,
`docs/NEXT_STALL_DEBUG_PLAN.md` and `docs/STALL_FIRST_EVENT_ORDERING.md`.
None of these routes is retried.

| # | inherited fact | why it is not re-opened |
|---|---|---|
| 1 | the wedge is a real **CPU-level** failure — a CPU stops answering an **ordinary IPI** (`CONFIG_ARM64_PSEUDO_NMI=n`, so the "NMI" wording is the backtrace helper's) | it is the premise, not the question |
| 2 | onset is **~6.5–7.8 s**, from two independent timers (RCU stall − 21.02 s, soft lockup − 26 s) | all evidence this round is kept around that window |
| 3 | the **GPU is not necessary** — `msm.skip_gpu=1` wedged identically (test-198) | profile not repeated |
| 4 | the **RPMh timeout branch is not necessary** — `gts9_rpmh_debug=1` wedged with zero RPMh output (test-199) | profile not repeated |
| 5 | the **cpufreq/OSM-L3 fix did not change the rate** — 2/29 vs 1/29, Fisher p = 1.0 | EPSS / OSM L3 / 3.36 GHz Prime OPP are **kept**, never reverted to "try again" |
| 6 | the 13–14 s deferred-probe window is a **symptom timer**, not the onset | not used as an onset |
| 7 | `encoder is disabled` fires on **every** healthy boot — it is noise | never counted as an anomaly |
| 8 | console silence, a stale panel, a failed ssh and a lone `frame done timeout` are **`SUSPECT`, never `WEDGE`** (test-194) | the verdict rule is unchanged |

Two consequences that shape this round:

* **`WEDGE` requires CPU-level evidence or an unrequested restart, bound to the
  round's boot.** Nothing weaker may reach that name. The existing harness
  already enforces this; this round does not weaken it.
* **A clean series is `not reproduced in N rounds`.** It is never "fixed",
  "solved" or "root cause confirmed" — those words require the restore step in
  §6.

## 2. Instrumentation status: three things this round does **not** need to build

Verified in the pinned tree this round, and each one removes work the brief
expected to be necessary.

1. **A failed PSCI `CPU_SUSPEND` prints nothing.** In
   `drivers/cpuidle/cpuidle-psci.c` there is no `pr_*()` on the failure path:

   ```c
   ret = psci_cpu_suspend_enter(state) ? -1 : idx;
   ...
   if (ret == -1 && ds->state)
   	pm_genpd_inc_rejected(ds->pd, ds->state_idx);
   ```

   So **"no PSCI error in the log" cannot be evidence that PSCI worked.**
   The counters are the signal:
   `/sys/devices/system/cpu/cpuN/cpuidle/stateM/rejected` (CPU states) and
   `/sys/kernel/debug/pm_genpd/power-domain-cluster/idle_states` (cluster
   states). This satisfies the brief's §21 for this specific path by
   *inspection*, and the counters are read in every profile (§4).
2. **The `power:psci_domain_idle_enter` / `_exit` tracepoints already exist**
   (v6.15, `include/trace/events/power.h`, guarded by
   `#ifdef CONFIG_ARM_PSCI_CPUIDLE` which is `=y`). They print the **raw
   parameter actually sent to firmware**, per CPU. That is the brief's §16
   instrument, already upstream — no kernel patch.
3. **The msr/dmesg route is not needed to prove the profile took effect.**
   `cpuidle.off=1` makes `cpuidle_init()` (a `core_initcall`) return `-ENODEV`,
   so `cpuidle_add_interface()` never runs and
   **`/sys/devices/system/cpu/cpuidle/` does not exist at all**. That absence is
   a positive, structural check — see §4.1, which is written around it because
   the brief's suggested check (`cat .../cpuidle/current_driver`) cannot work in
   this profile.

### 2.1 One facility that is missing, and is worth turning on

`CONFIG_CSD_LOCK_WAIT_DEBUG` is **not set** in the X710 config (`=n`), and it is
the only thing in mainline that answers the question this failure actually asks.
Verified in the pinned tree, `lib/Kconfig.debug`:

```
config CSD_LOCK_WAIT_DEBUG
	bool "Debugging for csd_lock_wait(), called from smp_call_function*()"
	depends on DEBUG_KERNEL
	depends on SMP
	depends on 64BIT
	default n
	help
	  This option enables debug prints when CPUs are slow to respond
	  to the smp_call_function*() IPI wrappers.  These debug prints
	  include the IPI handler function currently executing (if any)
	  and relevant stack traces.
```

and its output, `kernel/smp.c`:

```c
pr_alert("csd: %s non-responsive CSD lock (#%d) on CPU#%d, waiting %lld ns for CPU#%02d %pS(%ps).\n",
	 firsttime ? "Detected" : "Continued", *bug_id, raw_smp_processor_id(), ...);
...
	pr_alert("\tcsd: CSD lock (#%d) handling prior %pS(%ps) request.\n", ...)
	pr_alert("\tcsd: CSD lock (#%d) %s.\n", ..., !cpu_cur_csd ? "unresponsive" : "handling this request");
```

That prints **which function the stuck CPU was executing when the IPI arrived**,
and `dump_cpu_task(cpu)` then dumps its stack. The project's whole failure
signature is a CPU that stops answering `smp_call_function*()`, and
`toggle_allocation_gate → kick_all_cpus_sync → smp_call_function_many_cond` is
the documented victim chain — so this instrument is pointed exactly at the
observed victim.

**It is a build item, not a command-line item**: `default n` on a
`DEBUG_KERNEL`-dependent symbol, and its parameters (`csdlock_debug=`,
`smp.csd_lock_timeout=`, `smp.panic_on_ipistall=`) are no-ops without it.
`CONFIG_DEBUG_KERNEL=y` is already set, and the three `depends on` are satisfied
(`SMP=y`, 64-bit, ARM64). **It is deliberately not enabled in this round**: it
changes timing on the very path being measured, so it belongs in a *diagnostic*
profile with its own pre-registered rule, exactly as `gts9_rpmh_debug` did — not
bolted onto the ablation that must stay timing-neutral. It is recorded here so
the decision to use it is a decision rather than a scramble, and it is the first
thing to reach for on the §7 branch if `cpuidle.off=1` still wedges.

## 3. The experiment: layer by layer, cheapest first

The layers were determined by source inspection, and the finding that shapes the
whole design is in `docs/SM8550_IDLE_STATE_ANALYSIS.md` §5:

* **a CPU-local deep state cannot be removed by a DTS edit.** Removing
  `domain-idle-states` from `cpu_pd3`…`cpu_pd7` makes index 0 `NULL`, which
  makes `dt_init_idle_driver()` return 0, which makes `psci_idle_init_cpu()`
  return `-ENODEV`, which makes `psci_cpuidle_probe()` roll back **every** CPU.
  The brief's proposed `IDLE-LITTLE-ONLY` profile would therefore silently be
  `cpuidle.off=1` for all eight CPUs — worse than useless, because it would be
  reported as a per-CPU result;
* **a cluster domain state can be removed cleanly** at board level:
  `of_genpd_parse_idle_states()` treats zero states as success and
  `psci_pd_init()` handles `pd->states == NULL`.

So the ablation ladder is:

| order | profile | removes | how | cost |
|---|---|---|---|---|
| **1** | `cpuidle-off` | **everything above WFI** | `cpuidle.off=1` | cmdline only |
| **2** | `no-llcc-off` | the deeper cluster state only | `/delete-property/` on the `cluster_sleep_1` phandle | DTB |
| **3** | `no-cluster-idle` | **both** cluster states | delete both phandles | DTB |

**Profile 1 first, because it is one command-line token and no DTB change**, and
because the brief itself makes it the gate: if the wedge survives with the whole
framework off, the PSCI-idle hypothesis drops in priority and the plan moves to
§7 instead of grinding through idle patches.

### 3.1 Why there is no `IDLE-LITTLE-ONLY` profile

The brief asks for one, and the reason it is absent is a source-level fact, not
a preference: **it cannot be built.** §5.1 of
`docs/SM8550_IDLE_STATE_ANALYSIS.md` has the code path. The honest replacement
is profile 2/3, which separates the *cluster* layers — the only separation the
kernel actually supports. Recorded here so the omission is a decision with a
reason rather than an oversight.

### 3.2 Why there is no `BIG-PRIME-RESTORED` profile yet

The brief's reverse experiment is the right shape, and §6 defines it. It is
deliberately **not** built in this round: it only becomes meaningful if profile
1 or 2/3 produces `not reproduced`, and building boot bundles for a branch that
may never be taken is the kind of speculative work the repository's
one-purpose-per-commit rule discourages. The restore path is specified in §6 so
it can be built the moment it is needed, without re-deriving it.

## 4. The `cpuidle.off=1` diagnostic profile

New file: `boot/cmdline.cpuidle-off.example.txt`, derived from
`boot/cmdline.stall-ab-baseline.example.txt` with **exactly one token added**.

**What it does, from the source:** `drivers/cpuidle/cpuidle.c` declares
`static int off __read_mostly;` and `module_param(off, int, 0444)`;
`cpuidle_disabled()` returns it, and `kernel/sched/idle.c::cpuidle_idle_call()`
short-circuits:

```c
if (cpuidle_not_available(drv, dev)) {          /* off || !initialized || ... */
	idle_call_stop_or_retain_tick(stop_tick);
	default_idle_call();                    /* -> arch_cpu_idle() -> wfi() */
	goto exit_idle;
}
```

On arm64 `arch_cpu_idle()` is `cpu_do_idle()` → `dsb(sy); wfi();`. So this
profile leaves **architectural WFI only** and **no `PSCI CPU_SUSPEND` call at
all** — not the CPU states, not the cluster states.

**What it does not disable, stated so it is not over-read:** the `psci`
*genpd provider* is a separate driver (`cpuidle-psci-domain.c`) which does not
consult `cpuidle_disabled()`, and the OSI-mode `psci_set_osi_mode()` call still
happens at boot. So this profile removes the *idle entry*, not the domain
topology. The `psci_domain_idle_*` tracepoints will therefore show **no
entries**, which is the positive confirmation that no suspend happened.

### 4.1 The arming gate, and why it differs from the brief's

The brief suggests confirming the profile with
`cat /sys/devices/system/cpu/cpuidle/current_driver`. **That file does not exist
under this profile** — `cpuidle_init()` returns `-ENODEV` before
`cpuidle_add_interface()` runs, so the whole `cpuidle` sysfs group is absent.
Using it as the check would make a correctly-armed profile look broken.

The gate is therefore built from evidence that must be *present or absent* in a
specific direction:

| check | armed (`off=1`) | not armed |
|---|---|---|
| `/proc/cmdline` | contains `cpuidle.off=1` | does not |
| `/sys/devices/system/cpu/cpuidle/` | **absent** | present |
| `cpuidle: using governor menu` in the previous boot's ring | **absent** | present |
| `failed to register cpuidle driver` | **absent** | absent |
| `counts` of state1 `usage` | no path | present, non-zero |

The third row is the strong one and it is available because
`cpuidle_register_governor()` is a `postcore_initcall` reached only through the
cpuidle core: with the framework off, `menu` never registers and the line
**cannot** be printed. Measured: that line is present in 64 archived boot logs
today and absent from none, which is exactly why its absence is informative.

The fourth row exists to catch a *different* failure: if `cpuidle.off=1` is
mistyped or dropped by the bootloader, the boot looks normal and the profile is
a silent no-op — the failure mode that already cost this project a round
(`msm.no_gpu=1`, see `docs/STALL_FIRST_EVENT_ORDERING.md` §"Corrected inputs").
The gate must be checked **before** any round is counted.

## 5. The pre-registered decision rule

**Written before the first boot of this profile.** If the result disagrees with
the rule, the rule stands and the disagreement is recorded — the same discipline
as `docs/WEDGE_RATE_DECISION_RULE.md`.

### 5.1 The baseline is the existing one, not a new one

The comparison rate is the **current-era harness baseline**, counted from the
committed round records rather than from a prose summary:

| era | profile | rounds | wedge | clean | rate |
|---|---|---|---|---|---|
| current harness baseline | `baseline` | 2 | **2** | 0 | — |
| current harness baseline | `baseline` (test-193, no `verdict=` field) | 5 | see note | see note | — |
| GPU ablation | `no-gpu` | 4 | **1** | 3 | — |
| RPMh diagnostic | `rpmh-debug` | 4 | **1** | 3 | — |

Records: `test-195/round-1.txt`, `test-197/round-4.txt`,
`test-198/{c-round1..3,round-4}.txt`,
`test-199/{rpmh-round1..3,wedge-round9/round-9.txt}`.

**The honest number to beat is not a percentage.** Every pre-existing series is
tiny, and the two `baseline` records are both wedges, so the current-era
baseline cannot be turned into a rate without inventing one. What the archive
supports is the older, better-sampled statement from
`docs/CPU_WEDGE_EVIDENCE.md`: **1 in 29 boots (3.4%, CI 0.6–17.2%)** post-fix,
and 2 in 29 (6.9%) on the test-191 kernel. Those two rows are the only rates
this project has with a denominator, and `docs/WEDGE_RATE_DECISION_RULE.md`
already established that they are statistically indistinguishable.

**This round uses 3.4%/boot as the null** — the *lower* and therefore harder of
the two — and reports the 6.9% comparison as secondary. Under 3.4%:

| n | expected | P(k=0) | P(k≤1) | P(k≤2) |
|---|---|---|---|---|
| 10 | 0.34 | 0.713 | 0.955 | 0.996 |
| 30 | 1.02 | 0.362 | 0.723 | 0.917 |
| 60 | 2.04 | 0.126 | 0.391 | 0.666 |
| 85 | 2.89 | 0.053 | 0.211 | 0.445 |

**Read the n=10 row carefully: 0 of 10 has a 71% probability even if nothing
changed.** Ten clean boots are *no evidence at all*. This is why the brief's
"if 10 are clean, extend to 30/60" is a rule about *when to keep going*, not
about what 10 means.

### 5.2 The rule

`k` = rounds with `verdict=wedge` bound to the round; `n` = rounds with a
usable verdict. A round that is `unattributed` — no identity binding, or a
failed probe — advances neither, exactly as in
`docs/WEDGE_RATE_DECISION_RULE.md`.

| observation | conclusion to write | next action |
|---|---|---|
| **any `k ≥ 1` with CPU-level evidence** | **`full cpuidle framework is not necessary for the wedge`** | **stop the cpuidle direction immediately**; do not run profiles 2/3; go to §7 |
| `n = 10`, `k = 0` | **`not reproduced in 10 boots`** — no more | extend to 30 |
| `n = 30`, `k = 0` | **`not reproduced in 30 boots`** (P=0.362 under 3.4%) — no more | extend to 60 |
| `n = 60`, `k = 0` | **`not reproduced in 60 boots`**; rate is below 3.4% at this sample size, and that is the whole claim | go to §6 (**not** to a fix) |
| `n = 60`, `k ≥ 1` | the wedge **survived**; `PSCI cpuidle is not necessary` | stop, go to §7 |
| arming gate fails | **nothing may be concluded** | fix the profile; the boots do not count |

**Forbidden phrasings, at every sample size**: `fixed`, `solved`,
`root cause confirmed`, `eliminates the wedge`. `0/N` may only ever be written
as `not reproduced in N boots`.

The `k ≥ 1` row is the important one and it is deliberately placed first: the
brief's expectation is that this profile may work, and the rule says a **single**
genuine wedge kills the direction. That asymmetry is intentional — a clean
series bounds a rate, but one wedge is a fact.

### 5.3 What would make `cpuidle.off=1` a *finding* rather than a tool

Nothing in §5.2 does. Even 0/60 is only "not reproduced". To move from
`not necessary`/`not reproduced` to **`necessary`** requires the restore step:
re-enable the layer and watch the failure return (§6). Until that is run and
reproduces, the only permitted claim about a clean `cpuidle.off=1` series is
that it is **`correlated`** with the absence of the failure.

## 6. The restore experiment, specified but not built

Only if profile 1 or profile 2/3 produces `not reproduced`.

Restore in the direction the kernel actually supports. **Ascending, one layer
per series, never two at once:**

1. **`cluster-sleep-0` only** (restore the shallow cluster state; `llcc-off`
   still absent) — does the failure return?
2. **`cluster-sleep-0` + `cluster-sleep-1` restored** (= `baseline` DTB) — does
   the failure return?
3. **framework back on, all states present** (= `baseline` cmdline) — the
   control that the whole stack is back.

The required shape, per the brief, is:

```
baseline reproduces
  -> disable candidate eliminates (or reduces) the failure
  -> restore candidate brings the failure back
```

**Restoring the CPU-local state alone is not available** as a step, because of
§3's index-0 constraint — restoring `cpu_pdN`'s `domain-idle-states` restores
everything. This is recorded rather than worked around: it means the finest
attribution this hardware/kernel combination permits is *cluster-level*, and a
result that cannot separate CPU-local from cluster must say so.

## 7. If `cpuidle.off=1` still wedges

Then **PSCI cpuidle is `not necessary`** and the hypothesis is `downgraded`.
Per the brief, the plan moves to, in this order:

1. **IRQ delivery.** `/proc/interrupts` and `/proc/softirqs` deltas across a
   wedge, and the `ipi:*` tracepoints, to ask whether the target CPU's GIC
   redistributor is still routing.
2. **CPU hotplug state** — `online` vs `present` vs `possible` for the wedged
   CPU at the moment of failure, and whether a `cpu_down`/`cpu_up` cycle ever
   ran.
3. **`SError`** — whether any was taken; note `CONFIG_ARM64_PSEUDO_NMI=n` means
   an SError would be an ordinary IRQ on this build.
4. **arch timer / `local-timer-stop`** — whether the wedged CPU's timer is
   still programmed, and the `timer:*` tracepoints.
5. **RCU callback / IPI delivery** — the `rcu:*` tracepoints.
6. **firmware-level CPU state** — the one thing Linux cannot see.

**The instrument for this branch, and its design constraints.** The brief's §16
asks for a tracepoint-based observer rather than hot-path printk, with the
observer effect recorded. The trapoints exist and need no kernel change
(`CONFIG_TRACEPOINTS=y`, `CONFIG_TRACING=y`, `CONFIG_EVENT_TRACING=y`,
`CONFIG_RCU_TRACE=y`; a separate `CONFIG_CPU_IDLE_TRACING` has never existed).
If this branch is reached, the run is a **separate diagnostic profile** with:

* **`rcupdate.rcu_cpu_stall_ftrace_dump`** as the primary capture. Verified in
  `kernel/rcu/tree_stall.h:858`: `if (READ_ONCE(rcu_cpu_stall_ftrace_dump))
  rcu_ftrace_dump(DUMP_ALL);`, printed **at stall detection**, while the CPU is
  still wedged and before any panic. This is the only trigger that fires early
  enough to be useful for a wedge that does not reach a panic.
* **`trace_clock=global`**, verified at `kernel/trace/trace.c:1072`
  (`{ trace_clock_global, "global", 1 }`). The whole question is *which CPU did
  what first*, and the default `local` clock is explicitly not synchronised
  between CPUs. Cross-CPU correlation with an unsynchronised clock would be
  worthless, so this is not optional here.
* **`ftrace_dump()` is single-shot** — `kernel/trace/trace.c` guards it with a
  `dump_running` atomic, so `rcu_cpu_stall_ftrace_dump`, `ftrace_dump_on_oops`
  and `panic_sys_info=ftrace` **contend rather than add**. They are therefore
  armed as a primary plus one backstop, never as three.
* **`tp_printk` is deliberately NOT used.** It carries a documented live-lock
  risk (kernel-parameters.txt warns that high-frequency events through printk
  "can cause the system to live lock") and it adds nothing: `ftrace_dump()`
  reaches the console by itself, independently of the `tracepoint_printk` key.
  Using it would put a live-lock hazard on the profile whose subject is a hang.
* **`irq_handler_entry/exit` are excluded** for the same frequency reason;
  `irq:softirq_*` is enough to read the stall splat's `softirq=` counter, which
  is the cheap discriminator for "spinning with interrupts disabled".
* **The expected signature, if idle is the mechanism**: a `power:cpu_idle`
  entry with **no matching exit** (exit is `state=4294967295`,
  `PWR_EVENT_EXIT = -1`), corroborated by `ipi:ipi_entry` with no `ipi_exit`
  and `csd:csd_function_entry` with no `csd_function_exit`. That is a
  testable prediction, which is what makes the trace worth running rather than
  merely collecting.
* **Observer effect, recorded as the brief requires**: tracing adds
  per-event overhead on the idle path itself and changes the timing in the
  6–8 s window. A trace-enabled run may therefore show a **different rate** from
  an untraced one, and a clean traced series may not be compared to the
  untraced baseline. That is why it is a separate profile with its own rule.

**A specific negative result is recorded here so it is not re-searched:** the
merged GICv3 fix `0d62a49ab55c` ("Handle CPU_PM_ENTER_FAILED correctly", v6.13)
is **already in the pinned tree** — verified at
`drivers/irqchip/irq-gic-v3.c:1484`. Reaching this branch does **not** mean
"apply a known GIC patch"; there is no outstanding GIC patch to apply. It means
look for a new one.

## 8. Upstream status: three claims checked, none actionable this round

The brief asks for a survey with explicit labels. All three were checked; two
are not merged and one is already present.

| item | status | applies to | action |
|---|---|---|---|
| `sm8550: Add domain idle state names`, msg-id `20260914-b4-idle-state-name-v1-17-660c31187819@oss.qualcomm.com` | **not merged; no commit SHA** (v1, 2026-09-14) | naming/debugfs only | **none** — see `docs/SM8550_IDLE_STATE_ANALYSIS.md` §2 |
| `pmdomain/cpuidle-psci: Fix behaviours for CPU PM domains`, msg-id `20260914150146.187622-1-ulf.hansson@oss.qualcomm.com` | **in linux-next, not mainline** | runtime idle | **not adopted** — the brief forbids adopting an unmerged series as a fix; recorded in `docs/SM8550_IDLE_STATE_ANALYSIS.md` §7.1 |
| `irqchip/gic-v3: Handle CPU_PM_ENTER_FAILED correctly`, `0d62a49ab55c` | **merged (v6.13), already in the pinned tree** | runtime idle | **none needed** |

**No backport is proposed this round**, because none of the three changes what
this round tests and the brief explicitly forbids adopting an unmerged series as
a fix. The `sm8550` rename in particular must not be backported: it is a v1
mailing-list patch that changes only what debugfs prints, and the brief's §15
says to update *this project's* vocabulary rather than to touch a pinned
upstream DTS. That vocabulary update is done in
`docs/SM8550_IDLE_STATE_ANALYSIS.md`, in prose, with no DTS edit.

### 8.1 A same-SoC prior worth recording, and its exact limits

The closest published analogue to this failure is **not** an SM8550 report:

> `[PATCH RFC] arm64: dts: qcom: hamoa: Drop cluster_cl5 idle state from CPU
> clusters` — Jens Glathe, 2026-06-04, `Suggested-by: Marc Zyngier`. Spontaneous
> resets on Hamoa/Purwa under load and at idle; removing the **deepest cluster
> state** made four consumer devices stable. The author attributes it to a
> firmware/microcode issue where `DC ZVA` can hit caches powered down by PSCI
> idle states, and notes the mitigation **depended on PSCI mode**: OSI-mode
> consumer firmware was fixed by dropping the state, while the
> platform-coordinated Dev Kit needed `cpuidle.off=1`.

What it is worth here, stated precisely:

* it is **`correlated` evidence from a different SoC family** (X1/Hamoa, not
  SM8550). It is **not** an SM8550 report and must never be cited as one;
* it is an **RFC, unmerged** — so it is not a fix to backport either;
* it is the reason profile 2 (`no-llcc-off`, dropping the deepest **cluster**
  state) is in the ladder at all, and the reason §4's profile exists as the
  floor;
* **it predicts the opposite ordering from the brief.** The brief wants to
  disable *big/prime CPU* states first; Hamoa's evidence points at the
  **cluster** state. SM8550's `cluster_sleep_1` is the structural analogue of
  `cluster_cl5`. This round runs `cpuidle.off=1` first (which covers both), then
  the cluster profile — and the CPU-local-only profile is unobtainable anyway
  (§3.1). The disagreement is recorded now so the result cannot be read as
  having confirmed either prediction after the fact.

## 9. Evidence requirements for every profile

Per the brief's §20 and the repository's existing rules. Each real round records,
in a committed `reference/boot-tests/test-NNN-*/` directory:

```
repo commit, upstream kernel commit, kernel.release
Image SHA256, DTB SHA256, boot.img SHA256, vendor_boot.img SHA256, init_boot.img SHA256
cmdline (full), profile name, boot_id, reboot_kind
```

and, on a wedge, preserved immediately: pstore (`console-ramoops-0`), dmesg,
journal, console capture, `/proc/interrupts`, `/proc/softirqs`, the cpuidle
snapshot, and the profile identity.

**New in this round, because PSCI failures are silent (§2.1):** the cpuidle
snapshot is not optional decoration. For each profile the round record also
carries, for CPU0–7 and per state, `name`, `usage`, `time`, `rejected`,
`disable`; and for `power-domain-cluster`, the `Usage` **and `Rejected`**
columns. Two reasons:

* `rejected` is the **only** signal a failed `CPU_SUSPEND` produces;
* it is the **precondition for the cluster profiles**. Per
  `docs/SM8550_IDLE_STATE_ANALYSIS.md` §7.2, `cluster_sleep_1` needs ≥ 4400 µs
  of QoS headroom and ≥ 12 950 µs to the next hrtimer. If its `Rejected` count
  shows it is essentially never entered, then ablating it is a **no-op** and a
  clean result from profile 2 is **uninformative** — so that must be known
  before the boots are spent, not after.

Old tests are never overwritten. A failed or aborted attempt is archived the
same as a successful one.

## 10. What this round does **not** do

* no touch, audio, charging or other new hardware work;
* no flash, no partition write, no BCB write, no `dd`, no repartition;
* no change to `main`;
* nothing to `vbmeta`, `recovery`, the bootloader or `userdata`;
* **no revert** of EPSS, OSM L3 or the 3.36 GHz Prime OPP;
* no GPU/ACD/AOSS or RPMh-timeout experiment — both are `downgraded`, and
  re-running them would be the "re-try a tested route" the brief forbids;
* no `rcu_nocbs`, no `RCU_EXPERT` change, no `CONFIG_CPU_IDLE_GOV_TEO` change —
  see `docs/X710_X910_CPUIDLE_DIFF.md` §1.1, §6.2 for why each is inert or
  premature;
* no adoption of an unmerged upstream series;
* no permanent `cpuidle.off=1`. If it ever becomes the answer, it is the
  **last** resort, and its cost (idle power, temperature, battery) must be
  measured and stated — see the brief's §23 D.

## 11. The decision tree this produces

```
CPU wedge  (onset ~6.5-7.8 s, a CPU stops answering an ordinary IPI)
│
├─ cpuidle.off=1  -> k >= 1 (wedge returns)
│    └─ full cpuidle framework is NOT necessary
│         → IRQ/GIC · CPU hotplug state · SError · arch timer
│           · RCU/IPI delivery · firmware CPU state      (§7)
│
└─ cpuidle.off=1  -> not reproduced in 60
     │   (a bound, NOT a fix; needs §6 to become "necessary")
     │
     ├─ no-llcc-off  -> wedge returns => the deep cluster state is implicated
     ├─ no-cluster-idle -> wedge returns => the cluster layer is implicated
     └─ restore ladder (§6) => does the failure come back?
```

## 12. The questions the brief wants answered, and their status today

| # | question | status after this round's reading |
|---|---|---|
| 1 | is CPU idle **necessary** for the wedge? | **open** — this is what profile 1 tests |
| 2 | CPU-local state or cluster state? | **partially answerable, and constrained**: on this kernel only the cluster layer is separately removable (`docs/SM8550_IDLE_STATE_ANALYSIS.md` §5) |
| 3 | only big/prime? | **correlated** — 13 of 14 (boot, CPU) pairs are big/prime, P = 0.013; but the profile that would test it is **unbuildable** (§3.1) |
| 4 | X710 firmware/board specific? | **open** — the device tree and PSCI config are *identical* to X910 (`docs/X710_X910_CPUIDLE_DIFF.md`), so a difference must be in firmware behaviour, which Linux cannot read |
| 5 | why is X910 not affected? | **unknown, and not currently knowable from this repository** — X910 has no wedge-rate denominator and its PSCI mode has not been read |
| 6 | is there an upstream fix to use? | **no** for this failure mode — the one merged GIC fix is already present; the two relevant series are unmerged (§8) |
| 7 | minimal safe workaround? | **not established.** A board-DTS cluster-state deletion is the *smallest* candidate, and it is only a candidate until §6 runs |
| 8 | workaround power cost? | **unmeasured.** `cpuidle.off=1` is known to cost power in general terms; no number exists for this board, and inventing one is forbidden |

**No "final fix" is proposed, because none of questions 1–4 has evidence yet.**
That is the state the brief asks this round to reach honestly.

## Related

* `docs/SM8550_IDLE_STATE_ANALYSIS.md` — the five states, decoded; the ablation constraint
* `docs/X710_X910_CPUIDLE_DIFF.md` — the config diff, symbol by symbol
* `docs/CPU_WEDGE_EVIDENCE.md` — the signature, the rate, the wedged CPUs
* `docs/WEDGE_RATE_DECISION_RULE.md` — the rate-rule discipline this follows
* `reference/boot-tests/test-195-20260925T1023Z/` — a complete baseline wedge
