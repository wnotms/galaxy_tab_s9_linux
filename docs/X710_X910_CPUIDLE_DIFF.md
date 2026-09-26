# X710 vs X910: the CPU-idle / PSCI / RCU / IRQ configuration diff

Scope: only what bears on the CPU-idle hypothesis in
`docs/CPU_IDLE_WEDGE_PLAN.md`. This is not a general port comparison and it is
not a second copy of `docs/X710_X910_GPU_RPMH_DIFF.md` (which covers the
GPU/GMU/AOSS/ACD/RPMh topology). It exists because the brief asks for a
*symbol-level* diff over fourteen symbol families, and because the earlier GPU
document never looked at the idle path at all.

Every row carries the two labels the brief asks for:

* **where the X710 value came from** — `stock-seed`, `fragment`,
  `upstream-default`, or `Kconfig-select`;
* **whether it differs** from X910 — `same`, `X710 only`, `X910 only`.

## Sources, read directly

| tree | path | revision |
|---|---|---|
| X710 resolved config | `out/kernel-gts9wifi/config` | build of this repo |
| X710 fragment | `kernel/config/gts9wifi-mainline.fragment` | this repo |
| X710 stock seed (5.15.153) | materialized by `scripts/materialize-stock-config.sh` | immutable evidence |
| X710 board DTS | `kernel/dts/sm8550-samsung-gts9wifi.dts` | this repo |
| X710 built DTB | `dtc -I dtb -O dts out/kernel-gts9wifi/sm8550-samsung-gts9wifi.dtb` | build of this repo |
| X910 config | `.work/x910/ubuntu-galaxy-tab-s9-ultra/kernel/config/config-mainline.aarch64` | `4ff9d4b` |
| X910 board DTS | `.work/x910/ubuntu-galaxy-tab-s9-ultra/kernel/dts/sm8550-samsung-gts9uwifi.dts` | `4ff9d4b` |
| shared SoC base | `.work/linux-mainline/arch/arm64/boot/dts/qcom/sm8550.dtsi` | `a13c140cc` (v7.2-rc3) |

The X910 tree is a throwaway clone under `.work/` (not committed). To reproduce:

```sh
git clone --depth 50 https://github.com/agcarbajo/ubuntu-galaxy-tab-s9-ultra \
    .work/x910/ubuntu-galaxy-tab-s9-ultra
git -C .work/x910/ubuntu-galaxy-tab-s9-ultra log -1 --format=%H
# 4ff9d4b0ba1ae40e7605ad54c0ffe561c1e26a60
```

Confirmed from the X910 tree's own `scripts/fetch-mainline.sh`:

```
tag=${LINUX_TAG:-v7.2-rc3}
commit=${LINUX_COMMIT:-a13c140cc289c0b7b3770bce5b3ad42ab35074aa}
```

**The two ports pin the same upstream commit, down to the SHA.** That is the
single most useful fact in this document: it means every difference below is a
*port decision*, not a kernel-version difference, and the "X910 does not wedge"
control is therefore at the same baseline.

## 0. Headline: the idle path is configured identically; the diff is in RCU

The three config lines the brief singles out as X910's known CPU-idle settings —

```
CONFIG_CPU_IDLE=y
CONFIG_CPU_IDLE_MULTIPLE_DRIVERS=y
CONFIG_CPU_IDLE_GOV_MENU=y
# CONFIG_CPU_IDLE_GOV_TEO is not set
CONFIG_DT_IDLE_STATES=y
CONFIG_DT_IDLE_GENPD=y
CONFIG_ARM_PSCI_CPUIDLE=y
CONFIG_ARM_PSCI_CPUIDLE_DOMAIN=y
```

— are **all present in the X710 config too**, with exactly one exception:

```
CONFIG_CPU_IDLE_GOV_TEO=y        # X710 only
```

So the X910-differs-from-X710 story is **not** "X910 has the PSCI idle domain
driver and X710 does not". Both have it. The real deltas that matter are:

1. **`CONFIG_CPU_IDLE_GOV_TEO=y` is X710-only**, and it came from the stock
   Samsung 5.15 seed rather than from this port's fragment (§2).
2. **`CONFIG_CPU_IDLE_THERMAL=y` + `CONFIG_IDLE_INJECT=y` are X710-only**, also
   from the stock seed — but §3 shows they are **inert** on this board, which
   removes them from the suspect list without a test.
3. **The RCU configuration is X710-only in six symbols**, and it is inherited
   wholesale from the stock seed (§6). `CONFIG_RCU_EXPERT=y` is what *enables*
   the other five to exist at all.
4. **`CONFIG_NO_HZ=y` is X710-only** — but it is a legacy alias, not a
   behaviour (§5).

Neither port's board DTS overrides a single idle state, so item 0 in the
brief's list — "is the X710 DTS doing something X910's is not?" — has a clean
negative answer: **no** (§8).

## 1. CPU_IDLE* — one real difference

| symbol | X710 | X910 | 5.15 stock | X710 provenance | class |
|---|---|---|---|---|---|
| `CONFIG_CPU_IDLE` | y | y | y | stock-seed | same |
| `CONFIG_CPU_IDLE_MULTIPLE_DRIVERS` | y | y | y | stock-seed | same |
| `CONFIG_CPU_IDLE_GOV_MENU` | y | y | y | stock-seed | same |
| **`CONFIG_CPU_IDLE_GOV_TEO`** | **y** | **n** | y | **stock-seed** | **X710 only** |
| `CONFIG_CPU_IDLE_GOV_LADDER` | n | n | n | stock-seed | same |
| `CONFIG_DT_IDLE_STATES` | y | y | y | stock-seed | same |
| `CONFIG_DT_IDLE_GENPD` | y | y | (absent) | upstream-default | same |
| `CONFIG_ARM_PSCI_CPUIDLE` | y | y | y | stock-seed | same |
| `CONFIG_ARM_PSCI_CPUIDLE_DOMAIN` | y | y | y | stock-seed | same |

### 1.1 `CPU_IDLE_GOV_TEO=y` does **not** change the active governor

This was the lead recorded in `docs/CPU_WEDGE_EVIDENCE.md`, and reading the
pinned source settles it. `drivers/cpuidle/governor.c`
`cpuidle_register_governor()` adds a governor and switches to it when

```c
if (!cpuidle_curr_governor ||
    !strncasecmp(param_governor, gov->name, CPUIDLE_NAME_LEN) ||
    (cpuidle_curr_governor->rating < gov->rating &&
     strncasecmp(param_governor, cpuidle_curr_governor->name,
		 CPUIDLE_NAME_LEN)))
	cpuidle_switch_governor(gov);
```

and the ratings are

| governor | rating | registered from | initcall |
|---|---|---|---|
| `menu` | **20** | `drivers/cpuidle/governors/menu.c` | `postcore_initcall` |
| `teo` | 19 | `drivers/cpuidle/governors/teo.c` | — |
| `ladder` | 10 | `drivers/cpuidle/governors/ladder.c` | — |

`menu` sorts before `teo` in `drivers/cpuidle/governors/Makefile` **and** has the
higher rating, so it wins on both counts and `teo` can never displace it. That is
confirmed on the device, on 14 archived boot logs:

```
[    0.137482] [      T1] cpuidle: using governor menu
```

`reference/boot-tests/test-191-20260925T0410Z/wedge-rate-rate3-20260925T073018Z/cycle-1-dmesg.log:298`

**So `CONFIG_CPU_IDLE_GOV_TEO=y` only makes `teo` *available*, and it is not
active.** It is a real X710-only config delta and it is worth recording as one,
but it cannot be the mechanism while `menu` is the selected governor. Turning it
off is not a candidate experiment; it would change nothing at runtime.

## 2. Everything else the brief listed for CPU_IDLE is identical

There is nothing else to report in this family. In particular the brief's list of
"X910's known CPU idle configuration" is satisfied by X710 **without the
`CPU_IDLE_GOV_TEO` line** — which means the X910 config cannot be used to argue
that X710 is missing an idle-path feature.

## 3. `CONFIG_CPU_IDLE_THERMAL` is X710-only **and inert** — do not test it

| symbol | X710 | X910 | 5.15 stock | X710 provenance | class |
|---|---|---|---|---|---|
| `CONFIG_CPU_IDLE_THERMAL` | y | (absent) | y | **stock-seed** | X710 only |
| `CONFIG_IDLE_INJECT` | y | (absent) | y | **stock-seed** | X710 only |
| `CONFIG_THERMAL` | y | y | y | stock-seed | same |
| `CONFIG_THERMAL_OF` | y | y | y | stock-seed | same |
| `CONFIG_THERMAL_GOV_STEP_WISE` | y | y | y | stock-seed | same |
| `CONFIG_THERMAL_NETLINK` | y | n | y | stock-seed | X710 only |
| `CONFIG_THERMAL_GOV_USER_SPACE` | y | n | y | stock-seed | X710 only |
| `CONFIG_CPU_FREQ_THERMAL` | y | y | y | stock-seed | same |

`docs/CPU_WEDGE_EVIDENCE.md` raised `CONFIG_CPU_IDLE_THERMAL` as a lead: it adds a
cooling device that injects idle. Reading the pinned source shows it cannot
engage on this board.

`drivers/thermal/cpuidle_cooling.c`, `cpuidle_cooling_register()`, iterates
`drv->cpumask` and for each CPU does

```c
cooling_node = of_get_child_by_name(cpu_node, "thermal-idle");
if (!cooling_node) {
	pr_debug("'thermal-idle' node not found for cpu%d\n", cpu);
	continue;
}
```

So the cooling device is created only for a CPU node that has a `thermal-idle`
child. Checked directly, not inferred:

```
$ grep -rc 'thermal-idle' arch/arm64/boot/dts/qcom/sm8550.dtsi
0
$ grep -rl 'thermal-idle' arch/arm64/boot/dts/qcom/ | wc -l
0
$ grep -c 'thermal-idle' /tmp/gts9.dts     # dtc -I dtb -O dts of the built X710 DTB
0
```

**No Qualcomm device tree in this tree — base or board — declares a `thermal-idle`
node.** `cpuidle_cooling_register()` therefore calls `continue` for all eight
CPUs and registers zero cooling devices. `CONFIG_CPU_IDLE_THERMAL=y` is compiled
in and does nothing at runtime, which is why it never appeared in the
`docs/CPU_WEDGE_EVIDENCE.md` runtime observations either.

**Consequence for the plan: `CPU_IDLE_THERMAL` is removed from the candidate list
by source inspection, not by a boot test.** Neither is a candidate for an
ablation profile.

`THERMAL_NETLINK` and `THERMAL_GOV_USER_SPACE` are likewise stock-seed
inheritance with no `thermal-zones` node in the X710 board DTS to drive them.

## 4. PSCI* — byte-identical

| symbol | X710 | X910 | class |
|---|---|---|---|
| `CONFIG_ARM_PSCI_FW` | y | y | same |
| `CONFIG_ARM_PSCI_CPUIDLE` | y | y | same |
| `CONFIG_ARM_PSCI_CPUIDLE_DOMAIN` | y | y | same |
| `CONFIG_ARM_PSCI_CHECKER` | n | n | same |
| `CONFIG_ARM64_PSEUDO_NMI` | n | n | same |
| `CONFIG_QCOM_SCM` | y | y | same |
| `CONFIG_HAVE_ARM_SMCCC` | y | y | same |

**There is no PSCI configuration difference between the two ports.** A pure
config-level explanation of "X910 is stable, X710 wedges" is therefore excluded
for this family.

`CONFIG_ARM64_PSEUDO_NMI=n` is worth stating because it is what makes the
failure signature's wording misleading and it was already corrected in
`docs/CPU_WEDGE_EVIDENCE.md`: the "NMI" backtrace request is an ordinary IPI on
this build.

## 5. `CONFIG_NO_HZ=y` is X710-only, and it is not a behaviour

| symbol | X710 | X910 | 5.15 stock | X710 provenance | class |
|---|---|---|---|---|---|
| **`CONFIG_NO_HZ`** | **y** | **n** | y | stock-seed | **X710 only** |
| `CONFIG_NO_HZ_IDLE` | y | y | y | stock-seed | same |
| `CONFIG_NO_HZ_COMMON` | y | y | y | stock-seed | same |
| `CONFIG_NO_HZ_FULL` | n | n | n | stock-seed | same |
| `CONFIG_HZ_PERIODIC` | n | n | n | stock-seed | same |
| `CONFIG_TICK_ONESHOT` | y | y | y | stock-seed | same |
| `CONFIG_HIGH_RES_TIMERS` | y | y | y | stock-seed | same |
| `CONFIG_HZ` / `CONFIG_HZ_250` | 250 / y | 250 / y | 250 / y | stock-seed | same |

This looks like a difference and is not one. `kernel/time/Kconfig` says so in the
symbol's own help text:

```
config NO_HZ
	bool "Old Idle dynticks config"
	help
	  This is the old config entry that enables dynticks idle.
	  We keep it around for a little while to enforce backward
	  compatibility with older config files.
```

Its only remaining role is to pick the default of the tick-handling choice:

```
choice
	prompt "Timer tick handling"
	default NO_HZ_IDLE if NO_HZ
```

**Both configs resolve the choice to `NO_HZ_IDLE=y` with
`HZ_PERIODIC` unset**, which is the state that matters. `CONFIG_NO_HZ` itself
appears nowhere in the kernel's C sources outside a comment in
`drivers/clocksource/timer-ep93xx.c`:

```
$ grep -rn 'CONFIG_NO_HZ\b' --include='*.c' --include='*.h' . | grep -v NO_HZ_IDLE
./drivers/clocksource/timer-ep93xx.c:34: * CONFIG_NO_HZ.
```

So the two ports are tick-identical: `HZ=250`, `NO_HZ_IDLE`, `TICK_ONESHOT`,
`HIGH_RES_TIMERS`. **Not a candidate.**

## 6. RCU* — the largest real delta, and it is all stock-seed

| symbol | X710 | X910 | 5.15 stock | X710 provenance | class |
|---|---|---|---|---|---|
| **`CONFIG_RCU_EXPERT`** | **y** | **n** | y | stock-seed | **X710 only** |
| `CONFIG_RCU_BOOST` | y | (absent) | y | stock-seed | X710 only |
| `CONFIG_RCU_BOOST_DELAY` | 500 | (absent) | 500 | stock-seed | X710 only |
| `CONFIG_RCU_EXP_KTHREAD` | y | (absent) | y | stock-seed | X710 only |
| `CONFIG_RCU_NOCB_CPU` | y | (absent) | y | stock-seed | X710 only |
| `CONFIG_RCU_LAZY` | y | (absent) | y | stock-seed | X710 only |
| `CONFIG_RCU_LAZY_DEFAULT_OFF` | y | (absent) | y | stock-seed | X710 only |
| `CONFIG_RCU_FANOUT` / `_LEAF` | 64 / 16 | (absent) / (absent) | 64 / 16 | stock-seed | X710 only |
| `CONFIG_RCU_CPU_STALL_TIMEOUT` | 21 | 21 | 21 | stock-seed | same |
| `CONFIG_RCU_EXP_CPU_STALL_TIMEOUT` | 0 | 0 | (absent) | upstream-default | same |
| `CONFIG_PREEMPT_RCU` / `CONFIG_TREE_RCU` | y / y | y / y | y / y | stock-seed | same |
| `CONFIG_RCU_TRACE` | y | y | y | stock-seed | same |

### 6.1 What is actually live, and what is not

`RCU_EXPERT` is a gate, not a behaviour: `kernel/rcu/Kconfig` describes it as
"Make expert-level adjustments to RCU configuration", and it is what allows
`RCU_BOOST`, `RCU_EXP_KTHREAD` and `RCU_NOCB_CPU` to be *offered*. Five of the
six X710-only RCU symbols exist only because X710 answered that stock 5.15
question `y`.

Checked for runtime effect rather than assumed:

* **`RCU_BOOST=y` is live.** It needs `RT_MUTEXES && PREEMPT_RCU && RCU_EXPERT`;
  X710 has `CONFIG_RT_MUTEXES=y` (line 883), `CONFIG_PREEMPT_RCU=y` (line 147),
  `RCU_EXPERT=y`. So RCU readers are priority-boosted on X710 and not on X910.
* **`RCU_NOCB_CPU=y` is compiled in but NOT active.** Offloading happens only for
  CPUs named on the `rcu_nocbs=` command line (or `RCU_NOCB_CPU_DEFAULT_ALL=y`,
  which is **not** set). Checked across every profile:
  ```
  $ grep -rn 'rcu_nocbs\|rcu_nocb' boot/ kernel/
  (no output)
  ```
  No X710 command line carries it, so no CPU is offloaded.
* **`RCU_LAZY=y` is neutralised by its own companion.**
  `CONFIG_RCU_LAZY_DEFAULT_OFF=y` is set, so the lazy-callback behaviour is off
  unless `rcupdate.rcu_lazy` turns it on — and no profile carries that either.
* **`RCU_EXP_KTHREAD=y` is live.** It needs `RCU_BOOST && RCU_EXPERT`, and its
  `default !PREEMPT_RT && NR_CPUS <= 32` is satisfied. Expedited grace periods
  run in a real-time kthread on X710 and not on X910.

### 6.2 Why this is recorded as *correlated*, not *necessary*

`RCU_BOOST` and `RCU_EXP_KTHREAD` are genuinely different runtime behaviour, they
are X710-only, and they sit exactly on the code path the failure signature names
(`rcu_preempt kthread starved`, `RCU_GP_DOING_FQS`). That is a real correlation
and it is worth writing down.

It is **not** a mechanism, for two reasons that must be stated together with it:

1. **`docs/CPU_WEDGE_EVIDENCE.md` already observed the same signature on a
   Wedge with `policies=3`, and the RCU stall is a *consequence* of the missing
   CPU, not a cause of it.** The stall report is what a healthy RCU prints when
   some *other* CPU stops answering; the document's own §"What the CPU was doing"
   says the spin in `rcu_exp_gp_kthr` is a victim.
2. **X910 does not provide a controlled comparison.** It is a different board,
   different firmware, different userspace, and it has never been run through
   this port's wedge-rate harness. "X910 has `RCU_BOOST=n` and does not wedge" is
   a two-variable difference, and the project's own rule
   (`docs/WEDGE_RATE_DECISION_RULE.md`) is that a rate claim needs a denominator.

**So the honest classification is `possibly relevant, untested`.** It is recorded
here because the brief asks for the diff, and it is *not* promoted to a candidate
because the brief also forbids acting on a name match. `RCU_EXPERT`,
`RCU_BOOST_DELAY`, `RCU_FANOUT*`, `RCU_NOCB_CPU`, `RCU_LAZY` are **not** in the
first ablation set; see `docs/CPU_IDLE_WEDGE_PLAN.md` §"Not this round".

## 7. IRQ* / GIC* / arch timer — same silicon, one cosmetic difference

| symbol | X710 | X910 | 5.15 stock | X710 provenance | class |
|---|---|---|---|---|---|
| `CONFIG_ARM_GIC_V3` | y | y | y | stock-seed | same |
| `CONFIG_ARM_GIC_V3_ITS` | y | y | y | stock-seed | same |
| `CONFIG_IRQ_DOMAIN` / `_HIERARCHY` | y / y | y / y | y / y | stock-seed | same |
| `CONFIG_QCOM_PDC` | y | y | n | fragment | same |
| **`CONFIG_ARM_GIC_PM`** | **(absent)** | **y** | (absent) | upstream-default | **X910 only** |
| `CONFIG_GENERIC_IRQ_IPI_MUX` | (absent) | y | (absent) | upstream-default | X910 only |
| `CONFIG_IRQ_POLL` | n | y | n | stock-seed | X910 only |
| `CONFIG_GENERIC_IRQ_STAT_SNAPSHOT` | y | (absent) | (absent) | upstream-default | X710 only |
| `CONFIG_ARM_ARCH_TIMER` | y | y | y | stock-seed | same |
| `CONFIG_ARM_ARCH_TIMER_OOL_WORKAROUND` | y | y | y | stock-seed | same |

### 7.1 `ARM_GIC_PM` is the only GIC delta and it is not X710's to miss

`CONFIG_ARM_GIC_PM` is a hidden symbol with exactly one selector in the whole
tree:

```
$ grep -rn 'select ARM_GIC_PM' arch/*/Kconfig* drivers/irqchip/Kconfig
arch/arm64/Kconfig.platforms:401:	select ARM_GIC_PM      # ARCH_TEGRA
```

X910 sets it because it enables `CONFIG_ARCH_TEGRA=y` as part of a
multi-platform distro config (`config-mainline.aarch64:401`); X710 does not:

```
out/kernel-gts9wifi/config:384:# CONFIG_ARCH_TEGRA is not set
```

It is also **not on the CPU-idle path at all**. Its only consumer is
`drivers/irqchip/irq-gic.c` — the **GICv2** driver — where it gates
`gic_pm_init()`. The SM8550 uses `irq-gic-v3.c`, whose CPU_PM notifier is gated
on `CONFIG_CPU_PM` (line 1481), not on `ARM_GIC_PM`, and `CONFIG_CPU_PM=y` in
both configs.

**Consequence: the GICv3 redistributor save/restore notifier is present and
identical in both ports.** `ARM_GIC_PM` is `definitely unrelated`.

### 7.2 The merged GICv3 CPU_PM_ENTER_FAILED fix is already present

The one upstream GIC fix that a wedge of this shape would suggest is
`0d62a49ab55c` ("irqchip/gic-v3: Handle CPU_PM_ENTER_FAILED correctly", merged
v6.13), which fixed the driver ignoring `CPU_PM_ENTER_FAILED` and leaving the GIC
disabled. The pinned tree already has it — read directly, not inferred:

```c
/* drivers/irqchip/irq-gic-v3.c:1484 */
if (cmd == CPU_PM_EXIT || cmd == CPU_PM_ENTER_FAILED) {
	if (gic_dist_security_disabled())
		gic_enable_redist(true);
	gic_cpu_sys_reg_enable();
	gic_cpu_sys_reg_init();
}
```

**No backport needed. There is no outstanding GICv3 fix to apply here** — which
matters, because the brief's decision tree sends a `cpuidle.off=1`-still-wedges
result in the GIC direction. Reaching that branch does not mean "apply a known
GIC patch"; it means "look for a new one".

## 8. SCHED*, PM_GENERIC_DOMAINS*, ENERGY_MODEL*

| symbol | X710 | X910 | 5.15 stock | X710 provenance | class |
|---|---|---|---|---|---|
| `CONFIG_PM_GENERIC_DOMAINS` | y | y | y | stock-seed | same |
| `CONFIG_PM_GENERIC_DOMAINS_OF` | y | y | y | stock-seed | same |
| `CONFIG_PM_GENERIC_DOMAINS_SLEEP` | y | y | y | stock-seed | same |
| `CONFIG_CPU_PM` | y | y | y | stock-seed | same |
| `CONFIG_ENERGY_MODEL` | y | y | y | stock-seed | same |
| `CONFIG_SCHED_MC` | y | y | y | stock-seed | same |
| `CONFIG_SCHED_CLUSTER` | y | y | (absent) | upstream-default | same |
| `CONFIG_SCHED_HRTICK` | y | y | y | stock-seed | same |
| `CONFIG_SCHED_CACHE` | y | y | (absent) | upstream-default | same |
| `CONFIG_SCHED_HW_PRESSURE` | y | y | (absent) | upstream-default | same |
| `CONFIG_SCHEDSTATS` | y | n | y | stock-seed | X710 only |
| `CONFIG_SCHED_AUTOGROUP` | n | y | n | stock-seed | X910 only |
| **`CONFIG_SCHED_SMT`** | **n** | **y** | n | stock-seed | **X910 only** |
| `CONFIG_NR_CPUS` | 32 | 512 | 32 | stock-seed | X910 only |

**The domain topology the idle states hang off is configured identically**:
`PM_GENERIC_DOMAINS` + `_OF` + `_SLEEP` + `CPU_PM` + `DT_IDLE_GENPD` +
`ARM_PSCI_CPUIDLE_DOMAIN` are `y` in both. This is the family that would have
carried a "X710 is missing the genpd idle glue" story, and it does not.

`CONFIG_SCHED_SMT=y` on X910 is an artefact of the distro config: `sm8550.dtsi`
declares no SMT topology and SM8550 has no SMT cores, so it is inert. `NR_CPUS`
is a compile-time array bound, not a behaviour, at 8 present CPUs.

## 9. The board device trees do not touch the idle path — verified in the DTB

This is the brief's §"X710/X910 是否一致" question for the device tree, and it is
answered on the **compiled artifact**, not on the source.

The board DTS files `#include "sm8550.dtsi"` and neither one contains a single
`cpu_idle` / `cpuidle` / `idle-state` / `domain-idle-states` / `local-timer-stop`
/ `lpm` node or override:

```
$ grep -nE 'idle-state|cpu_pd|cluster_pd|cpuidle|lpm|domain-idle' \
      kernel/dts/sm8550-samsung-gts9wifi.dts
(no output)
$ grep -nE 'idle-state|cpu_pd|cluster_pd|cpuidle|lpm|domain-idle' \
      .work/x910/.../kernel/dts/sm8550-samsung-gts9uwifi.dts
(no output)
```

And the state names in the **built, flashable X710 DTB** are upstream's, still
carrying the pre-rename wording:

```
$ dtc -I dtb -O dts out/kernel-gts9wifi/sm8550-samsung-gts9wifi.dtb | \
      grep idle-state-name
idle-state-name = "silver-rail-power-collapse";
idle-state-name = "gold-rail-power-collapse";
idle-state-name = "goldplus-rail-power-collapse";
```

**Therefore the two ports describe identical CPU and cluster idle states, and any
X710-specific idle defect must come from firmware behaviour or from Linux, not
from the device tree.** This is what makes the ablation in
`docs/CPU_IDLE_WEDGE_PLAN.md` a *DTS diagnostic patch* rather than a fix to
something already wrong in a board file.

## 10. What this diff does and does not establish

**Establishes, from source and resolved config:**

* the X710's PSCI/CPU-idle/genpd machinery is configured the same as X910's, so
  "X710 lacks a feature X910 has" is excluded for this path;
* the two X710-only idle-family symbols (`CPU_IDLE_GOV_TEO`, `CPU_IDLE_THERMAL`)
  cannot change runtime behaviour — one loses to `menu` on rating and ordering,
  the other registers zero cooling devices because no DTS has `thermal-idle`;
* the merged GICv3 `CPU_PM_ENTER_FAILED` fix is already present, so there is no
  known GIC patch to apply;
* the device trees are identical here, confirmed in the flashed DTB.

**Does not establish:**

* that the RCU delta is harmless. Six X710-only RCU symbols are real, inherited
  from the stock seed, and two of them (`RCU_BOOST`, `RCU_EXP_KTHREAD`) are live.
  They are recorded as `correlated`, and no experiment has been run on them;
* anything at all about firmware. `psci: PSCIv1.1 detected in firmware` and
  `CPUidle PSCI: Initialized CPU PM domain topology using OSI mode` are facts
  about *this* X710's ABL/PSCI, and X910's has not been read;
* that X910 is stable. Its README claims long GNOME/Wayland runs; that is the
  X910 project's claim, not a measurement this project made, and it carries no
  denominator comparable to `docs/CPU_WEDGE_EVIDENCE.md`'s.

## Related

* `docs/SM8550_IDLE_STATE_ANALYSIS.md` — what each state *is*, PSCI params decoded
* `docs/CPU_IDLE_WEDGE_PLAN.md` — the pre-registered A/B rule and the profiles
* `docs/CPU_WEDGE_EVIDENCE.md` — the signature and the rate
* `docs/X710_X910_GPU_RPMH_DIFF.md` — the sibling diff for the GPU/RPMh path
