# SM8550 idle states: what each one is, and what may be ablated

This document exists because the failure signature has been described in this
repository as "rail power collapse" for several rounds, and that wording is
wrong in two ways. It decodes the five states the X710 actually has, records
what is **verified** about each and what is **not**, and states which layers can
be disabled independently — which is what the ablation profiles in
`docs/CPU_IDLE_WEDGE_PLAN.md` depend on.

Scope: read-only, source-level. Nothing here was measured on the device.

## 1. The five states, as the pinned tree defines them

Source: `.work/linux-mainline/arch/arm64/boot/dts/qcom/sm8550.dtsi`, pinned
commit `a13c140cc289c0b7b3770bce5b3ad42ab35074aa` (v7.2-rc3), read directly.
Confirmed present in the **built, flashable** X710 DTB:

```
$ dtc -I dtb -O dts out/kernel-gts9wifi/sm8550-samsung-gts9wifi.dtb | grep idle-state-name
idle-state-name = "silver-rail-power-collapse";
idle-state-name = "gold-rail-power-collapse";
idle-state-name = "goldplus-rail-power-collapse";
```

| DT node | `idle-state-name` (pinned) | `arm,psci-suspend-param` | entry / exit / min-residency (µs) | CPUs | `local-timer-stop` |
|---|---|---|---|---|---|
| `cpu-sleep-0-0` | `silver-rail-power-collapse` | **`0x40000004`** | 550 / 750 / 6700 | 0–2 | yes |
| `cpu-sleep-1-0` | `gold-rail-power-collapse` | **`0x40000004`** | 600 / 1300 / 8136 | 3–6 | yes |
| `cpu-sleep-2-0` | `goldplus-rail-power-collapse` | **`0x40000004`** | 500 / 1350 / 7480 | 7 | yes |
| `cluster-sleep-0` | *(none in the pinned tree)* | **`0x41000044`** | 750 / 2350 / 9144 | shared | n/a (`domain-idle-state`) |
| `cluster-sleep-1` | *(none in the pinned tree)* | **`0x4100c344`** | 2800 / 4400 / 10150 | shared | n/a |

**All three CPU states carry the identical suspend parameter.** They differ only
in their latency and residency numbers. That is the first fact that matters:
there is no per-cluster PSCI parameter difference to blame, only a
per-cluster *latency table* that changes which state the governor picks.

## 2. The rename patch the brief asks about is **not merged** — do not rebase onto it

The brief refers to `arm64: dts: qcom: sm8550: Add domain idle state names` as
clarifying the semantics. Verified status:

| field | value |
|---|---|
| subject | `[PATCH 17/31] arm64: dts: qcom: sm8550: Add domain idle state names` |
| author | Maulik Shah `<maulik.shah@oss.qualcomm.com>` |
| date | 2026-09-14 |
| message-id | `20260914-b4-idle-state-name-v1-17-660c31187819@oss.qualcomm.com` |
| commit SHA | **none — mailing-list v1, never applied** |
| state | **not in v7.2-rc3, not in linux-next** (both still print the old names) |

Full message body, which is short enough to quote in full:

> Add the idle-state-name property for the domain idle state so low power modes
> are described consistently and its name is printed in pmdomain debugfs.
> While at it, update CPU idle state names to match the low power modes they
> describe.

**It is a naming and debugfs change. It changes no behaviour, and it is not a
fix.** Adopting it would alter what `pm_genpd_summary` prints and nothing else.

The semantic content the brief attributes to it is in the **series cover
letter**, not the patch:

> Most Qualcomm silver CPU idle states do not turn the silver rail off; they
> collapse the CPU and turn the PLL off. Name those states silver-pll-pc. Gold
> CPU states often turn both PLL and rail off, so use gold-pll-rail-pc to
> reflect the low power mode.

That claim is worth taking seriously as a *description*, and it is why this
repository must stop calling the little-cluster state a "rail power collapse".
But it is a statement in a mailing-list cover letter, by one Qualcomm engineer,
about Qualcomm's states in general. **It is not measured on this board, it is
not merged, and nothing in the pinned tree corroborates the per-state power
topology.** It is recorded here as `vendor claim, unverified on X710`.

## 3. What the suspend parameters actually mean

This is the part that **is** verifiable from the pinned tree, and it is worth
being precise because it is easy to over-read.

`arm,psci-suspend-param` is passed verbatim to `PSCI CPU_SUSPEND` as
`power_state`. `drivers/cpuidle/cpuidle-psci.c::psci_dt_parse_state_node()`
reads it and rejects anything `psci_power_state_is_valid()` does not accept:

```c
err = of_property_read_u32(np, "arm,psci-suspend-param", state);
...
if (!psci_power_state_is_valid(*state)) {
	pr_warn("Invalid PSCI power state %#x\n", *state);
	return -EINVAL;
}
```

`psci_power_state_is_valid()` (`drivers/firmware/psci/psci.c`) uses the
**extended** mask once firmware advertises extended states:

```c
const u32 valid_mask = psci_has_ext_power_state() ?
		       PSCI_1_0_EXT_POWER_STATE_MASK :
		       PSCI_0_2_POWER_STATE_MASK;
return !(state & ~valid_mask);
```

with, from `include/uapi/linux/psci.h`,

```
PSCI_0_2_POWER_STATE_MASK     = ID(0xffff) | TYPE(1<<16) | AFFL(3<<24) = 0x0301ffff
PSCI_1_0_EXT_POWER_STATE_MASK = ID(0xfffffff) | TYPE(1<<30)              = 0x4fffffff
```

**This yields a proof about our firmware, not an assumption.** Test
`0x40000004` against both:

```
0x40000004 & ~0x0301ffff = 0x40000004  != 0   -> INVALID under PSCI 0.2
0x40000004 & ~0x4fffffff = 0           == 0   -> VALID   under PSCI 1.0 extended
```

An invalid parameter makes `psci_cpu_init_idle()` return `-EINVAL`, which makes
`psci_idle_init_cpu()` fail, which makes `psci_cpuidle_probe()` roll back and
print `pr_err("CPU %d failed to PSCI idle\n")`. The device instead reports

```
$ cat /sys/devices/system/cpu/cpuidle/current_driver
psci_idle
```

(`docs/CPU_WEDGE_EVIDENCE.md`), with no `failed to PSCI idle` line in any of the
14 archived boot logs. **Therefore the X710 firmware advertises extended power
states, i.e. `psci: OSI mode supported.` is a real capability of this firmware
and bit 30 of these parameters is meaningful.**

Bit 30 is `PSCI_1_0_EXT_POWER_STATE_TYPE_MASK`, and
`psci_power_state_loses_context()` tests exactly that bit:

```c
return state & mask;   /* mask = EXT_POWER_STATE_TYPE_MASK when extended */
```

So **bit 30 set ⇒ context is lost**, and `psci_cpu_suspend_enter()` takes the
full save/restore path:

```c
if (!psci_power_state_loses_context(state)) {
	... arm_cpuidle_save_irq_context(&context);
	ret = psci_ops.cpu_suspend(state, 0);
	arm_cpuidle_restore_irq_context(&context);
} else {
	ret = cpu_suspend(state, psci_suspend_finisher);   /* <- our states */
}
```

**All five SM8550 states have bit 30 set.** They are therefore all
context-losing states: the CPU goes through `cpu_suspend()` → `cpu_resume`.
That is a strong, source-derived statement and it is the one the brief wanted.

### 3.1 What is **not** decoded, and must not be asserted

The brief's framing implies a known bit layout for `0x40000004` /
`0x41000044` / `0x4100c344`. **It is not known.** Verified:

* the DT binding defines no bit layout. `Documentation/devicetree/bindings/cpu/idle-states.yaml`
  says only: *"power_state parameter to pass to the ARM PSCI suspend call"*;
* the `0x40` / `0x41` high nibble, and the `0x44` / `0xc3` low bytes, have **no**
  documented meaning in this tree.

So `0x40000004` vs `0x41000044` vs `0x4100c344` can be described as
**empirically distinct parameters that firmware accepts**, and *not* as
"CPU level / cluster level / LLCC off" in any load-bearing sense. The brief's
`l3-pc` and `llcc-off` names come from the unmerged cover letter. This document
uses them as **labels of convenience only**, and every experiment below is
defined by the parameter value it changes, never by the name.

**This is why the ablation must be done by removing a state from
`domain-idle-states`, not by rewriting a parameter.** Rewriting a parameter
would require knowing what the bits mean, and that is exactly what is not known.

## 4. The Linux call path, end to end

```
do_idle()                                   kernel/sched/idle.c
 └─ cpuidle_idle_call(got_tick)
     ├─ cpuidle_not_available(drv, dev)?  -> default_idle_call() -> wfi
     └─ call_cpuidle(drv, dev, next_state)
         └─ drv->states[idx].enter()          <- set at registration
```

Which `enter()` is installed depends on whether **OSI** is in use. In
`psci_dt_cpu_init_topology()` (`drivers/cpuidle/cpuidle-psci.c`):

```c
/* Currently limit the hierarchical topology to be used in OSI mode. */
if (!psci_has_osi_support())
	return 0;
...
drv->states[state_count - 1].enter = psci_enter_domain_idle_state;
```

**This board is in OSI mode** — quoted from a clean boot log
(`reference/boot-tests/test-191-20260925T0410Z/wedge-rate-rate3-20260925T073018Z/cycle-1-dmesg.log`):

```
[    0.000000] [      T0] psci: PSCIv1.1 detected in firmware.
[    0.000000] [      T0] psci: OSI mode supported.
[    0.139095] [      T1] CPUidle PSCI: Initialized CPU PM domain topology using OSI mode
```

So the deepest CPU state does **not** use the simple `psci_enter_idle_state`
path. It uses the hierarchical one:

```c
/* drivers/cpuidle/cpuidle-psci.c, __psci_enter_domain_idle_state() */
ret = cpu_pm_enter();
pm_runtime_put_sync_suspend(pd_dev);        /* runs the genpd governor */
ds = this_cpu_ptr(&psci_domain_state);
if (ds->state)
	state = ds->state;                  /* <- the CLUSTER state WINS */
trace_psci_domain_idle_enter(dev->cpu, state, s2idle);
ret = psci_cpu_suspend_enter(state) ? -1 : idx;
trace_psci_domain_idle_exit(dev->cpu, state, s2idle);
```

**That `if (ds->state) state = ds->state;` is the single most important line in
this document.** It means:

> When the CPU-local deepest state is entered **and** the cluster genpd has
> independently chosen a domain state, the parameter sent to firmware is the
> **cluster's** `0x41000044` or `0x4100c344`, not the CPU's `0x40000004`.

Consequently **"the CPU's own state" and "the state actually sent to PSCI" are
not the same thing**, and disabling a CPU-local state is not a clean way to
remove the CPU-local layer. Any ablation design that assumes otherwise is
wrong. This is why the profiles in `docs/CPU_IDLE_WEDGE_PLAN.md` are defined by
*which layer is removed*, not by which sysfs file is written.

## 5. Which layers can be disabled independently, and how

The brief asks specifically whether the layers can be separated. They can, but
**not in the way the brief proposes**, and the reason is a source-level
constraint that was worth finding before writing a patch.

### 5.1 A CPU-local state **cannot** be removed by deleting its
`domain-idle-states` property

The brief suggests removing `domain-idle-states` from `cpu_pd3`…`cpu_pd7` so
those CPUs keep only WFI. That does not work, and the failure mode is silent
degradation rather than an error, so it must be recorded.

`of_get_cpu_state_node()` (`drivers/of/cpu.c`) resolves a CPU's states through
the power domain first:

```c
err = of_parse_phandle_with_args(cpu_node, "power-domains",
				"#power-domain-cells", 0, &args);
if (!err) {
	state_node = of_parse_phandle(args.np, "domain-idle-states", index);
	if (state_node)
		return state_node;
}
return of_parse_phandle(cpu_node, "cpu-idle-states", index);
```

and `dt_init_idle_driver()` iterates `index = 0, 1, 2, …` **stopping at the
first `NULL`**:

```c
for (i = 0; ; i++) {
	state_node = of_get_cpu_state_node(cpu_node, i);
	if (!state_node)
		break;                      /* <- index 0 gone means NO states at all */
```

Removing `domain-idle-states` from a `cpu_pd` node makes index 0 `NULL`, so
**that CPU gets zero DT idle states**, and then
`psci_dt_cpu_init_topology()` → `state_count` becomes 1, and
`psci_idle_init_cpu()` does

```c
ret = dt_init_idle_driver(drv, psci_idle_state_match, 1);
if (ret <= 0)
	return ret ? : -ENODEV;
```

`ret == 0` → `-ENODEV` → `psci_idle_init_cpu()` fails → and because
`psci_cpuidle_probe()` rolls back **every** CPU on any single failure:

```c
for_each_present_cpu(cpu) {
	ret = psci_idle_init_cpu(&fdev->dev, cpu);
	if (ret)
		goto out_fail;          /* unregisters all previously inited CPUs */
}
```

**the entire `psci_idle` driver disappears**, for all eight CPUs. That is not
"CPU3–7 lose deep idle"; it is `cpuidle.off=1` by accident, delivered through
the device tree, with no error visible unless one reads for
`failed to PSCI idle`. It would be indistinguishable from the blunt profile it
was meant to refine.

**Also note the second half of the same trap**: `of_device_is_available()` **is**
honoured, but in the loop above it `continue`s rather than `break`s:

```c
if (!of_device_is_available(state_node)) {
	of_node_put(state_node);
	continue;               /* index is still consumed */
}
```

so `status = "disabled"` on a CPU state node removes it from the *count* while
consuming its index — which does **not** give CPU3–7 WFI-only either, for the
same index-0 reason. **Neither DT mechanism produces the intended
"per-CPU shallow idle" profile.**

### 5.2 A cluster domain state **can** be removed cleanly, at board level

The cluster layer is different, and this is the one ablation that works as the
brief hopes. `psci_cpuidle_domain_probe()` walks the `psci` node's children and
calls `psci_pd_init()` for each node with `#power-domain-cells`, which calls
`dt_idle_pd_alloc()` → `of_genpd_parse_idle_states()`. That parser **skips**
unavailable nodes and tolerates the result being empty:

```c
/* drivers/pmdomain/core.c, genpd_iterate_idle_states() */
if (!of_match_node(idle_state_match, np))
	continue;
if (!of_device_is_available(np))
	continue;
```

```c
/* of_genpd_parse_idle_states() */
if (!ret) {
	*states = NULL;
	*n = 0;
	return 0;               /* zero states is SUCCESS, not an error */
}
```

and `dt_idle_pd_alloc()` accepts `state_count = 0` (its `pd_parse_state_nodes()`
loop simply does not execute), while `psci_pd_init()` handles it explicitly:

```c
/* Use governor for CPU PM domains if it has some states to manage. */
pd_gov = pd->states ? &pm_domain_cpu_gov : NULL;
```

**So removing a `&cluster_sleep_N` phandle from `cluster_pd`'s
`domain-idle-states` list is a supported, clean operation**: the domain keeps
working, keeps its `power_off` hook, and simply has one fewer state. Board-level
`/delete-property/` on the cluster list is therefore the correct ablation tool.

**This asymmetry is the main design finding of this document**, and it is why
the profiles are built the way they are: the reachable layers are
`all-or-nothing` (WFI only), `cluster-state-count`, and nothing finer.

### 5.3 The layer table

| layer | parameter | removable independently? | how |
|---|---|---|---|
| WFI | `0x0` (synthesised, state index 0) | **no** — always present | `cpuidle.off=1` reaches it by removing everything above |
| CPU-local deep | `0x40000004` | **no** — see §5.1 | only by removing *all* cpuidle (DT trap makes it all-or-nothing) |
| cluster shallow (`l3-pc`) | `0x41000044` | **yes** | delete its phandle from `cluster_pd` |
| cluster deep (`llcc-off`) | `0x4100c344` | **yes** | delete its phandle from `cluster_pd` |
| both cluster states | — | **yes** | delete both phandles |

## 6. X710 vs X910: identical, and identical to upstream

| item | X710 | X910 | class |
|---|---|---|---|
| all five state nodes | upstream `sm8550.dtsi` | upstream `sm8550.dtsi` | **same** |
| board-DTS idle override | none | none | **same** |
| `CPU_IDLE*` / `PSCI*` / `DT_IDLE*` config | see `docs/X710_X910_CPUIDLE_DIFF.md` §1, §4 | — | **same except `GOV_TEO`** |
| PSCI mode | **OSI** (`psci: OSI mode supported`) | not read | **unverified** |

Both boards include the same shared SoC dtsi and neither touches the idle
states, so this is a device-tree-identical comparison. Full detail, including
the config-level diff, is in `docs/X710_X910_CPUIDLE_DIFF.md`.

## 7. Two structural facts worth recording, neither a conclusion

### 7.1 `apps_rsc` is a non-CPU consumer of `cluster_pd`

Verified in `sm8550.dtsi`: of the nine `power-domains = <&cluster_pd>`
references, eight are the `cpu_pd0`…`cpu_pd7` nodes and the ninth is

```dts
apps_rsc: rsc@17a00000 {
	compatible = "qcom,rpmh-rsc";
	...
	power-domains = <&cluster_pd>;
};
```

That makes the RPMh RSC — the block every sleep/wake vote is flushed through —
a consumer of the CPU cluster power domain. A pending (unmerged) series,
Ulf Hansson's `[PATCH v4 0/5] pmdomain/cpuidle-psci: Fix behaviours for CPU PM
domains` (`20260914150146.187622-1-ulf.hansson@oss.qualcomm.com`, in linux-next
but not mainline), names exactly this configuration as a problem:

> A more critical problem is when a non-CPU device shares the PM domain,
> leading to their corresponding drivers not being able to trust the status of it.

**Recorded as a hypothesis and explicitly not a candidate for this round**: it
would require the pending series, and the brief forbids adopting an unmerged
series as a fix. It is relevant because it connects the idle path to the RPMh
path this project has already spent rounds on, and because it is the kind of
coupling that produces "one subsystem's power state corrupts another's" — but
nothing has been measured, and `docs/CPU_IDLE_WEDGE_PLAN.md` does not act on it.

### 7.2 The vendor's `cluster_sleep_1` may already be unreachable

Independent of any bug, a deep state is only entered when the governor's
constraints allow it. From `cpu_power_down_ok()`
(`drivers/pmdomain/governor.c`):

```c
if ((idle_duration_ns >= (genpd->states[i].residency_ns +
    genpd->states[i].power_off_latency_ns)) &&
    (global_constraint >= (genpd->states[i].power_on_latency_ns +
    genpd->states[i].power_off_latency_ns)))
	break;
```

For `cluster_sleep_1` (exit 4400 µs, entry 2800 µs, residency 10150 µs) that
requires **≥ 4400 µs of QoS headroom and ≥ 12 950 µs to the next hrtimer** —
and `cpus_peek_for_pending_ipi()` must also come back clear.

**This is a control, not a finding.** If `cluster_sleep_1` is already rejected
on essentially every opportunity, then ablating it is a no-op and a clean result
from that profile would be uninformative. That is why the plan makes the
`Rejected` counter a **precondition** of the cluster experiments rather than an
optional observation: read it before spending boots, and record it beside the
wedge count.

## 8. Available instrumentation, and its Kconfig state

All of these exist in the pinned tree and need **no kernel change**. Whether
they are wired into the diagnostic profile is decided in
`docs/CPU_IDLE_WEDGE_PLAN.md` §"Instrumentation".

| surface | path | what it distinguishes |
|---|---|---|
| PSCI capabilities | `/sys/kernel/debug/psci` | `OSI is [not] supported`, `Extended/Original StateID format` |
| genpd domain states | `/sys/kernel/debug/pm_genpd/power-domain-cluster/idle_states` | `Usage` **and `Rejected`** per cluster state |
| per-CPU state counters | `/sys/devices/system/cpu/cpuN/cpuidle/stateM/{usage,time,rejected,disable}` | which CPU state was entered, and how often entry failed |
| PSCI idle tracepoint | `power:psci_domain_idle_enter` / `_exit` | the **raw parameter** actually sent, per CPU, per entry |
| cpuidle tracepoint | `power:cpu_idle` | state index in, `PWR_EVENT_EXIT` out |
| IPI tracepoints | `ipi:ipi_raise` / `ipi_entry` / `ipi_exit` | which IPI failed to arrive where |

Verified for each:

* **A failed PSCI `CPU_SUSPEND` prints nothing.** `cpuidle-psci.c` has no
  `pr_*()` on that path — it does `ret = psci_cpu_suspend_enter(state) ? -1 : idx;`
  and, for a domain state, `pm_genpd_inc_rejected(...)`. This is why the plan
  records the `rejected` counters as evidence and refuses to treat an empty
  dmesg as proof that PSCI behaved. `docs/CPU_WEDGE_EVIDENCE.md` §"What it does
  not establish" already says this in general terms; here is the code.
* `power:psci_domain_idle_enter/exit` are guarded by
  `#ifdef CONFIG_ARM_PSCI_CPUIDLE`, which is `=y`. They were added in v6.15.
* `/sys/kernel/debug/psci` is gated on `CONFIG_DEBUG_FS=y` only.
* `idle_states` comes from `genpd_debug_init()` (`late_initcall`), gated on
  `CONFIG_DEBUG_FS` only — not on a separate debug symbol.
* The genpd `Rejected` column and the per-CPU `rejected` file are two different
  counters: the first belongs to the **cluster** domain state, the second to the
  **CPU** state. They must not be conflated.

## 9. What this document establishes

1. **The vocabulary is corrected.** Three CPU states share one parameter; there
   are two distinct cluster parameters; the `l3-pc` / `llcc-off` names come from
   an **unmerged cover letter** and are labels only.
2. **The firmware advertises extended power states**, proved from the
   accept/reject arithmetic rather than assumed, and **all five states are
   context-losing** (bit 30 set) so all go through `cpu_suspend()`.
3. **On this board the cluster's parameter overrides the CPU's** in OSI mode,
   which means "the CPU state" and "the state sent to PSCI" are different
   objects.
4. **A CPU-local state cannot be removed by the DT edit the brief proposes**;
   the attempt silently degrades to losing all of cpuidle for all CPUs.
5. **A cluster domain state can be removed cleanly** at board level, and that is
   the only fine-grained ablation available.
6. **The rename patch is not merged and changes no behaviour**, so it is not a
   rebase candidate.

## Related

* `docs/CPU_IDLE_WEDGE_PLAN.md` — the profiles, built on §5 and §7.2
* `docs/X710_X910_CPUIDLE_DIFF.md` — the config-level diff
* `docs/CPU_WEDGE_EVIDENCE.md` — the failure signature and its rate
