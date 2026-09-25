# X710 GPU / GMU / AOSS / ACD / RPMh stall plan

Status: **plan of record for test-187.** Written before any code or config of
this phase, so the decision points below cannot be re-interpreted afterwards.

Supersedes `docs/NEXT_STALL_DEBUG_PLAN.md` as the *active* plan. That document's
RPMh/RSC framing is still valid and is carried forward in §6; what changed is the
discovery in §3 that the GPU init chain never reaches RPMh at all on this board,
which gives the next experiment a much cheaper and sharper entry point than
"backport the Qualcomm RSC debug series and hope to catch a stall".

---

## 1. Confirmed facts (do not re-derive)

| # | fact | evidence |
|---|---|---|
| 1 | ABL → mainline Linux → Debian boots on real hardware | `reference/boot-tests/test-178-*`, `docs/MINIMAL_ROOTFS_BOOT.md` |
| 2 | microSD rootfs reaches Debian multi-user reliably | test-178 stage history |
| 3 | display works (ANA38407 panel, DPU/DSI) | `docs/DISPLAY_X710_OFFICIAL_V1.md` |
| 4 | `ttyGS0` = USB ACM userspace root shell | `docs/USB_SERIAL_CONSOLE.md`, test-184 |
| 5 | `ttyGS1` = USB ACM kernel printk console | test-183/184 |
| 6 | software watchdog panics on soft lockup / hung task; `panic=10` reboots | test-183: 3/3 soft-lockup, 1/1 hung-task rounds |
| 7 | PCIe0 is **not** the stall cause | test-182 A/B with `pcie0` + PHY disabled still stalled |
| 8 | the 4.7 s → 125 s "pause" was `/dev/console → tty0 → fbcon → DRM` output backlog | test-184: all 28 report lines journal-timestamped `[4.646574]` |
| 9 | the DPU really does fail later in a stall, but that is not proof it is the common cause | `docs/DPU_TRACE.md` |
| 10 | real stalls cluster at **13.3–14.3 s** after boot, and that window is the deferred-probe-timeout burst | `docs/DPU_TRACE.md` four-stall table; real dump at 14.3076 s in `test-181-*/host-captures/r3-shutdown-window.log` — §4.2 |
| 11 | an **ACTIVE_ONLY RPMh transaction timeout** has been seen in a failing boot | round brief; **no captured dump exists in this repository** — patch `0021` has never run on the device (test-186 was never executed), so the exact timestamp is not evidence here. Corrected in round 2; see §4.4. |
| 12 | `pogo_watch_work` is a *victim*, not established as the cause | `docs/NEXT_STALL_DEBUG_PLAN.md` §1 |
| 13 | ramoops is registered but no record survives a reboot | test-183/184 |
| 14 | no Gunyah/`qcom,gh-watchdog` driver exists in this tree | test-183 audit |

### 1.1 Newly confirmed in this phase (source- and config-level, no device needed)

| # | fact | evidence |
|---|---|---|
| 15 | `msm.no_gpu=1` really exists in the pinned tree. `drivers/gpu/drm/msm/adreno/adreno_device.c` declares `static bool skip_gpu;` with `MODULE_PARM_DESC(no_gpu, ...)` and `module_param(skip_gpu, bool, 0400)` — the cmdline literal is `no_gpu`, not `skip_gpu`. | **built kernel ground truth**: `.work/build/linux-out/modules.builtin.modinfo` contains `msm.parm=no_gpu:Disable GPU driver register ...` and `msm.parmtype=skip_gpu:bool`; module name is `msm` |
| 16 | `msm.disable_acd=1` really exists. `adreno_device.c`: `bool disable_acd; MODULE_PARM_DESC(disable_acd, "Forcefully disable GPU ACD"); module_param_unsafe(disable_acd, bool, 0400);` | same `modules.builtin.modinfo`: `msm.parm=disable_acd:Forcefully disable GPU ACD` |
| 17 | `msm.no_gpu=1` does **more** than disable the GPU: `skip_gpu` makes `adreno_has_gpu()` return `false` and makes `adreno_register()` return before `platform_driver_register()`. No adreno driver is ever registered, so `3d00000.gpu` never probes. | `adreno_device.c:187-194, 419-425` |
| 18 | `msm.disable_acd=1` short-circuits `a6xx_gmu_acd_probe()` *before* it ever touches QMP: `if (disable_acd) { DRM_DEV_ERROR(..., "Skipping GPU ACD probe\n"); return 0; }`. It therefore removes the QMP dependency from GMU init. | `a6xx_gmu.c:1983-1989` |
| 19 | **`CONFIG_QCOM_AOSS_QMP` is not set in this build.** | `out/kernel-gts9wifi/config:6873` → `# CONFIG_QCOM_AOSS_QMP is not set`; the symbol appears nowhere in `kernel/config/gts9wifi-mainline.fragment` |
| 20 | The X710 DT *does* wire the GMU to AOSS QMP: the rendered DTB has `qcom,qmp = <0xba>` in `gmu@3d6a000`, and `0xba` is `power-management@c300000` (`compatible = "qcom,sm8550-aoss-qmp", "qcom,aoss-qmp"`, no `status` override → enabled). | `dtc -I dtb -O dts out/kernel-gts9wifi/sm8550-samsung-gts9wifi.dtb` |
| 21 | Upstream `sm8550.dtsi` gives **all eight** GPU OPP nodes a `qcom,opp-acd-level`, and the X710 DTS does not remove them (its only `&gpu` override is `status = "okay"` + `zap-shader/firmware-name`). So `cmd->enable_by_level != 0` is guaranteed on this board. `a6xx_gmu_build_freq_table()` seeds index 0 with the "off" level, so `nr_gpu_freqs = 9` and the ACD loop sets `BIT(1)..BIT(8)` = **`0x1fe`**. | `sm8550.dtsi:2879-2939` (8 × `qcom,opp-acd-level`); `kernel/dts/sm8550-samsung-gts9wifi.dts:1459-1466`; `a6xx_gmu.c` `a6xx_gmu_build_freq_table()` |
| 22 | The X910 port **does** enable AOSS QMP: `CONFIG_QCOM_AOSS_QMP=y` in its mainline config, and it carries a patch that pulls the provider in. | `.work/x910/ubuntu-galaxy-tab-s9-ultra/kernel/config/config-mainline.aarch64:9924`; `.../kernel/patches/build-wcn-pcie-providers-in.patch` |
| 23 | `CONFIG_DRIVER_DEFERRED_PROBE_TIMEOUT=10` is the resolved value. | `out/kernel-gts9wifi/config:1871` |
| 24 | `RPMH_TIMEOUT_MS` is 10 s, so **if** a `rpmh_write_batch()` warning is ever captured at time T, the batch was submitted at ≈ T−10 s. No such warning is currently on record from a real boot. | `drivers/soc/qcom/rpmh.c:25` |

---

## 2. The X710 GPU init chain is broken at a known point

Facts 19–21 combine into a deterministic, source-level conclusion:

```
gpu@3d00000  (status = "okay" on X710, fact 21)
  └─ a6xx_gpu_init()
       └─ a6xx_gmu_init()                       a6xx_gmu.c:2400+
            ├─ device_link_add(..., DL_FLAG_PM_RUNTIME)     ← managed link
            ├─ gmu->qmp = qmp_get(gmu->dev)                 ← reads "qcom,qmp"
            │     GMU DT has qcom,qmp = <&aoss_qmp>          (fact 20)
            │     but no driver is bound to aoss_qmp,
            │     because CONFIG_QCOM_AOSS_QMP is unset     (fact 19)
            │     → platform_get_drvdata(pdev) == NULL
            │     → ERR_PTR(-EPROBE_DEFER)                   qcom_aoss.c: qmp_get()
            ├─ a6xx_gmu_pwrlevels_probe()   → nr_gpu_freqs = 8
            └─ a6xx_gmu_acd_probe()
                 ├─ loops i = 1..(nr_gpu_freqs-1) over gmu->gpu_freqs[]
                 │     nr_gpu_freqs = 1 + 8 = 9  (index 0 is the "off" level)
                 ├─ every OPP has qcom,opp-acd-level          (fact 21)
                 │     → cmd->enable_by_level = BIT(1)..BIT(8) = 0x1fe  (non-zero)
                 └─ if (cmd->enable_by_level && IS_ERR_OR_NULL(gmu->qmp)) {
                        DRM_DEV_ERROR(gmu->dev,
                            "Unable to send ACD state to AOSS\n");
                        return -EINVAL;                       ← a6xx_gmu.c:2023
                    }
       ← a6xx_gmu_init() fails
       └─ error path: device_link_del(link)
            device_link_put_kref(): link is NOT stateless, consumer IS registered
            → WARN(1, "Unable to drop a managed device link reference")   core.c:1020
```

This is exactly the warning pair captured on real hardware in test-046/047/179/183
and quoted in §5 of the brief. It is not an unrelated warning: it is the *tail* of
a GPU probe that failed for a specific reason, and `a6xx_gmu_init()` returns before
it ever calls `a6xx_gmu_rpmh_init()`.

**Consequence that changes the investigation:** on the current image the GPU never
reaches `a6xx_gmu_rpmh_init()`, never votes through GMU RPMh, and never becomes
bound. Any hypothesis of the form "GMU RPMh votes / GPU interconnect / GMU runtime
PM caused the stall" is **not reachable on this build as it stands**. The GPU is
stuck one layer earlier, at ACD/AOSS.

### 2.1 Why this is a real bug even though it is "only warnings"

* `IS_ERR_OR_NULL(gmu->qmp)` is `-EPROBE_DEFER`, which the driver explicitly
  handles as *deferrable* (`qmp_get()` returning `-EPROBE_DEFER` is the case the
  caller tests for by name). Deferring on a supplier whose driver is **not
  compiled in** is a permanent defer: `deferred_probe` will retry forever and the
  device will never bind.
* So the GPU contributes a permanent `-EPROBE_DEFER` to the deferred-probe
  pending list, and each retry re-runs the failing ACD probe and re-prints the
  `device_link_del()` WARN. That is work and log volume on every retry, including
  after `CONFIG_DRIVER_DEFERRED_PROBE_TIMEOUT=10` (fact 23) has elapsed.
* The fix is a **config** fix, not a driver change: enable the provider that the
  device tree already references.

---

## 3. Hypothesis under test (explicitly a hypothesis, not a proven root cause)

> The X710 kernel is missing `CONFIG_QCOM_AOSS_QMP`, the provider the SM8550 GPU
> device tree requires for ACD. That leaves `gmu@3d6a000` and `gpu@3d00000`
> permanently on the deferred-probe list, which in turn prevents `gcc`, `gpucc`
> and the interconnect providers from ever completing `sync_state()`. At
> `late_initcall + CONFIG_DRIVER_DEFERRED_PROBE_TIMEOUT` (≈4.3 s + 10 s ≈
> **14.3 s**) the deferred-probe timeout work re-probes the entire pending set and
> walks `sync_state` across the whole clock/interconnect/power-domain graph at
> once — and the four recorded stalls all begin inside that same 13.3–14.3 s
> window.

Stated as a chain, with the *unproven* links marked:

```
CONFIG_QCOM_AOSS_QMP unset                    [PROVEN, fact 19]
        ↓
aoss_qmp device has no driver                 [PROVEN]
        ↓
qmp_get() → -EPROBE_DEFER (forever)           [PROVEN, source]
        ↓
a6xx_gmu_acd_probe() → "Unable to send ACD state to AOSS", -EINVAL   [PROVEN, source + real logs §4.1]
        ↓
GPU probe fails; device_link_del() WARN       [PROVEN, real logs §4.1]
        ↓
gmu@3d6a000 + gpu@3d00000 stay deferred       [PROVEN, real dump §4.3 14.3096 s]
        ↓
gcc / gpucc / interconnect-1 can never
finish sync_state()                           [PROVEN, real dump §4.3 14.3098 s]
        ↓
deferred_probe_timeout fires 10 s after the last
driver_register() that found it pending                [PROVEN, source + real dumps §4.2]
        ↓
whole pending set re-probed + sync_state walked simultaneously [PROVEN, source §4.2]
        ↓
??? that simultaneous burst wedges a CPU ???  [HYPOTHESIS — coincidence in time, not yet causation]
        ↓
one CPU stops running its watchdog kthread    [OBSERVED, 4 real stalls §4.2]
        ↓
stall is visible in the 13.3-14.3 s window    [OBSERVED, 4 real stalls §4.2]

NOT sufficient on its own: the same burst ran to completion
without a stall at 35.8 s on a live boot with identical
GPU defects (round-3 live pre-flight).  So the burst is
necessary-looking but demonstrably not sufficient.   [OBSERVED, live §4.2]
```

**What is proven and what is not.** The chain from the missing config down to
"the sync_state walk of the whole graph happens at 14.3 s with the GPU and GMU in
it" is proven from source plus a real dump. The single `???` link is whether that
burst *causes* the wedge. It is the only deterministic, system-wide event in the
observed stall window, which makes it the leading candidate — but coincidence in
time is not causation, and the §7 matrix exists to test it.

Note what this framing no longer depends on: the earlier revision leaned on an
"RPMh TCS machinery wedged at ≈4.27 s" story built from synthetic fixtures. That
story is gone (§4.4). The current hypothesis needs no RPMh timeout at all, which
means **the RPMh/RSC layer may be a victim rather than a participant** — and that
is precisely the possibility the brief warns against prejudging.

**Necessary correction to the brief's framing.** The brief lists
`msm.disable_acd=1` as an A/B "to isolate the GPU ACD → AOSS QMP path". Because
QMP is *already* non-functional (fact 19), `disable_acd=1` is not an isolation of
ACD — it is a **substitute for the missing provider**: it takes the first branch
of `a6xx_gmu_acd_probe()` and returns success before the QMP check. It is still a
useful and cheap experiment, but it must be described as *"does the GPU come up if
we remove the ACD requirement?"*, not *"is ACD the cause?"*.

---

## 4. Measured timeline

All figures are `journalctl -o short-monotonic` / console-capture monotonic
timestamps. No screen ordering is used (test-184 fact 8).

> **Correction (round 2).** An earlier revision of this section cited
> `reference/boot-tests/test-186-*/fixtures/victim.log` and
> `.../programmed-no-completion.log` as real hardware evidence. **They are not.**
> They are synthetic fixtures written to pin `classify-round.sh`'s branches, as
> that commit's own message states ("Three synthetic fixtures pin the branches").
> test-186 has no `rounds/` directory because it **was never run on the device**,
> and the `13.400000` / `14.270000` timestamps appear nowhere except that fixture
> file. They have been removed from this section and from fact 11. The real
> evidence is below, and it is stronger than the fixture was.

### 4.1 The GPU init failure (real, repeated on many boots)

From `test-183-*/rounds-inject/inject-{1,2,3}-console.log` and
`test-046-*` / `test-047-*` console captures:

| order | event |
|---|---|
| 1 | `platform 3d6a000.gmu: Adding to iommu group 1` |
| 2 | `adreno 3d00000.gpu: supply vdd not found, using dummy regulator` |
| 3 | `adreno 3d00000.gpu: supply vddcx not found, using dummy regulator` |
| 4 | `platform 3d6a000.gmu: [drm:a6xx_gmu_acd_probe] *ERROR* Unable to send ACD state to AOSS` |
| 5 | `Unable to drop a managed device link reference` + `device_link_put_kref` WARN, `Workqueue: events_unbound deferred_probe_work_func` |

This cluster repeats on every boot captured, in the same order. The absolute
window is the early-console window; the console's own `[...]` field on those
lines is a **delta**, not an absolute timestamp, so the exact absolute time comes
from the surrounding absolute lines (~4.1–4.2 s), not from the delta field.

### 4.2 The stall window is the deferred-probe-timeout burst (real)

This is the finding that reframes the investigation, and it comes from real
evidence in two places.

**`docs/DPU_TRACE.md` §"What four reproductions showed"** — four cold boots
stalled, all in the **~13.3–14.3 s** window, described there as *"the
deferred-probe / late-init burst"*:

| | stall 1 | stall 2 | stall 3 (PCIe0 off) | stall 4 (PCIe0 off) |
|---|---|---|---|---|
| NMI-unresponsive CPU | 5 | 7 | 5 | (RCU stall) |
| last normal log | PCIe probe **14.05 s** | PCIe probe **14.05 s** | **sync_state dump 13.54 s** | DPU overflow **13.263 s** |
| `pm_runtime_work` stuck | 4 | 3 | 3 | – |
| other stuck work | `fqdir_free_fn` | `toggle_allocation_gate` | `fqdir_free_fn`, `pogo_watch_work` | `drm_fb_helper_damage_work` pending |

**`test-181-*/host-captures/r3-shutdown-window.log`** — the same burst with
absolute monotonic timestamps, at **14.3076–14.3127 s**:

```
[   14.307609] platform 6800000.remoteproc: deferred probe pending: ...
[   14.308413] platform smp2p-adsp: deferred probe pending: qcom_smp2p: IRQ index 0 not found
[   14.308836] qnoc-sm8550 1500000.interconnect: sync_state() pending due to 1c00000.pcie
[   14.309643] qnoc-sm8550 interconnect-1: sync_state() pending due to 3d00000.gpu
[   14.309755] gcc-sm8550 100000.clock-controller: sync_state() pending due to 3d6a000.gmu
[   14.309869] gpu_cc-sm8550 3d90000.clock-controller: sync_state() pending due to 3d6a000.gmu
[   14.311135] qcom-rpmhpd 17a00000.rsc:power-controller: sync_state() pending due to ade0000.clock-controller
[   14.312532] qcom-pcie 1c00000.pcie: supply vdda not found, using dummy regulator
```

This is `deferred_probe_timeout_work_func()` in `drivers/base/dd.c`. Its
mechanism, from the source:

```c
fw_devlink_drivers_done();
driver_deferred_probe_timeout = 0;
driver_deferred_probe_trigger();   /* <- re-probes EVERY deferred device */
flush_work(&deferred_probe_work);
/* then prints the still-pending list and walks sync_state */
fw_devlink_probing_done();
```

**When it fires (corrected in round 3).** It is *not* "late_initcall + 10 s".
`deferred_probe_initcall()` arms it:

```c
if (driver_deferred_probe_timeout > 0)
        schedule_delayed_work(&deferred_probe_timeout_work,
                              driver_deferred_probe_timeout * HZ);
```

but `driver_register()` — called for **every** driver — immediately re-arms it
while it is still pending:

```c
/* drivers/base/driver.c, end of driver_register() */
deferred_probe_extend_timeout();
    -> if (delayed_work_pending(&deferred_probe_timeout_work) &&
            mod_delayed_work(..., secs_to_jiffies(driver_deferred_probe_timeout)))
```

So the burst fires **10 s after the last `driver_register()` that found the work
still pending**. With `CONFIG_DRIVER_DEFERRED_PROBE_TIMEOUT=10` (fact 23) a dump
at 14.3076 s means the last such registration was at ≈4.31 s — not that
"late_initcall ran at 4.31 s", and not that anything happened to the GPU then.

**Live counter-example that forces this correction.** On the currently flashed
image the same defects reproduce exactly — GPU/GMU/AOSS all unbound, ACD error,
`probe with driver adreno failed with error -22` — yet that boot was **clean**
(0 soft lockups, 0 RPMh timeouts) and its burst ran at **35.805 s**, not
13–14 s. See `reference/boot-tests/test-187-*/live-preflight/README.md`.

Two things follow, and both are recorded rather than papered over:

1. **The burst alone is not sufficient to stall the machine.** It is a real,
   deterministic, system-wide event, and here it ran to completion harmlessly.
2. **The 13.3–14.3 s clustering is a property of what last re-armed the timer in
   those boots**, not of a fixed delay. A stalling boot's last driver
   registration must have landed around 3.3–4.3 s.

So profile G tests whether *moving the burst moves the stall* — a weaker and more
honest claim than "the burst is the trigger". It remains the right experiment,
because if the stall follows the burst the mechanism is confirmed regardless of
what pins the timer, and if the stall does not follow it, the burst is
exonerated and the RPMh/RSC direction returns.

**Answering "what last re-armed the timer" in a stalling boot is now an explicit
open question**, and it is answerable from an existing capture: the interval
between the last `driver_register()` and the burst is exactly 10 s, so the
registration time is recoverable from any log that has the burst timestamp.

**So the stall is coincident with a single, deterministic, whole-system event: at
~4.3 s + 10 s the kernel re-probes every device still on the deferred list and
then walks every provider's `sync_state`.**

### 4.3 Why the GPU sits in that burst

At 14.309755 s and 14.309869 s the dump shows:

```
gcc-sm8550 100000.clock-controller: sync_state() pending due to 3d6a000.gmu
gpu_cc-sm8550 3d90000.clock-controller: sync_state() pending due to 3d6a000.gmu
```

`gcc` and `gpucc` **cannot complete `sync_state()` while the GMU is unbound**, and
the GMU is unbound precisely because of the ACD/AOSS failure in §2 — that probe
returned `-EPROBE_DEFER` and can never succeed while
`CONFIG_QCOM_AOSS_QMP` is unset. `driver_deferred_probe_timeout = 0` does not
help: `qmp_get()` returns `-EPROBE_DEFER` directly rather than through
`driver_deferred_probe_check_state()`, so no timeout value can let the GMU bind.

`qnoc-sm8550 interconnect-1: sync_state() pending due to 3d00000.gpu` shows the
interconnect is likewise waiting on the GPU.

**This is the concrete, evidenced mechanism linking the GPU defect to the stall
window** — and it is stronger than the "retry storm" wording used earlier in this
document:

```
CONFIG_QCOM_AOSS_QMP unset                       [PROVEN, fact 19]
  → aoss_qmp has no driver                        [PROVEN]
  → qmp_get() -> -EPROBE_DEFER forever            [PROVEN, source]
  → a6xx_gmu_acd_probe() -> -EINVAL               [PROVEN, source + real logs]
  → gmu@3d6a000 and gpu@3d00000 stay on the
    deferred list permanently                     [PROVEN, real dump 14.3096 s]
  → gcc / gpucc / interconnect-1 can never
    finish sync_state()                           [PROVEN, real dump 14.3098 s]
  → deferred_probe_timeout fires at ~4.3 s + 10 s [PROVEN, real dump 14.3076 s]
  → simultaneous re-probe + sync_state walk of
    the whole pending set                         [PROVEN, source]
  → the ~13.3-14.3 s stall window                  [PROVEN, 4 real stalls]
```

The last link is *coincidence in time*, not yet proof of causation: the stall has
been observed in the same window on four boots, and the burst is the only
deterministic system-wide event in that window, but no run has yet shown the
burst *causing* the wedge. That is exactly what the §7 matrix tests.

### 4.4 What is still NOT real evidence

* **There is no captured RPMh timeout dump.** Patch `0021` has never run on the
  device; test-186 was never executed. Everything in the earlier revision of this
  document about `tcs_in_use=0x8`, `irq_status=0x0`, `holder_tcs`, `ring_summary`
  and a `1c00000.interconnect` caller was synthetic-fixture content and has been
  removed. The §8 decision tree therefore remains **unexercised**.
* **The `+14.27 s` RPMh warning is not a real observation.** Fact 11 has been
  corrected: the real starting point is that an RPMh/ACTIVE_ONLY timeout *was*
  seen in a failing boot per the round brief, but its exact timestamp is not in
  this repository's evidence, and no 10-second-submission arithmetic should be
  built on it until a real dump exists.

---

### 4.4 AMENDMENT (round 11): the burst is NOT a sufficient mechanism

Rounds 9-11 tested §4.2-4.3's central claim — that the deferred-probe burst is the
trigger — against real hardware, and it does not hold as a sufficient cause.

Measured on 8 post-fix boots (the device's own retained `gts9-boot-evidence`
records, previous boot's kernel log read per boot):

| boot | last monotonic timestamp reached | `sync_state() pending` lines |
|---|---|---|
| `…-1084b57a` | 89.99 s | 31 |
| `…-14f0722f` | 90.51 s | 31 |
| `…-7f8878b7` | 45.21 s | 31 |
| `…-b69787e2` | 659.61 s | 29 |
| `…-1f85d97b` | 2615.21 s (43.6 min) | 29 |
| `…-61f93d8e` | 709.80 s | 29 |
| `…-994ad160` | 378.88 s | 29 |
| `…-cd04c0ef` | 377.84 s | 29 |

Every one of those boots lived far past the 13-14 s window and carried the full
`sync_state` load (29-31 pending lines), and **none stalled**. The burst still
fires, in the same place, with the same shape:

```
[   14.304464] platform 6800000.remoteproc: deferred probe pending: ...
[   14.306552] gcc-sm8550 100000.clock-controller: sync_state() pending due to 3d6a000.gmu
[   14.306668] gpu_cc-sm8550 3d90000.clock-controller: sync_state() pending due to 3d6a000.gmu
```

So the burst is **not** what wedges the machine — it occurs, at the same timing and
with the same `sync_state` content, on boots that survive. And the `sync_state`
blockage on `gmu@3d6a000` (§4.3) is likewise not the differentiator: it is present
on every surviving boot, because it is upstream-correct behaviour (there is no
`qcom,adreno-gmu` platform driver in this tree), and the AOSS QMP fix does not and
should not change it.

**What does differ** between the surviving boots and the archived failures is the
GPU chain. The failures carried `Unable to send ACD state to AOSS`,
`Unable to drop a managed device link reference`, and
`probe with driver adreno failed with error -22`. None of the surviving boots has
any of those; the current boot shows instead
`[drm] Initialized msm 1.13.0 for 3d00000.gpu on minor 0`.

**Read §4.2-4.3 accordingly:** the burst coincides with the stall window and the GPU
defect was on the path into it, but the burst alone demonstrably completes without
wedging. The AOSS QMP + IPCC fix removed the GPU-probe failure chain, and 8 boots
that reached the window with the full `sync_state` load did not stall.

**Still not a proof**, for a reason independent of sample size: the two archived
failures were found by inspection rather than by counting attempts, so there is no
pre-fix rate to compare against. The supportable statement is "the window is reached
on every boot and no longer wedges", not "the failure is eliminated".

### 4.5 AMENDMENT (round 16): the failure is not in the 13-14 s window

Round 16 stopped adding instrumentation and re-read the captures this project
already had, with a classifier that scores a round on the device's own
`previous_boot_end` and on `reboot.target` rather than on `systemd-shutdown`
(which the USB gadget regularly outruns). Three things came out of that, and the
first one changes the framing of this whole document.

**1. Neither captured failure happened in the 13-14 s window.**

| failure | when it actually happened |
|---|---|
| test-184 A-5 | during **shutdown**: services stopped from monotonic 70.5 s, then 28.9 s of total silence, then an external reset |
| test-187 2-round r1, boot `1f85d97b` | during **normal running**: `enc35 frame done timeout` at kernel 6.483 s, then 37.4 s of silence, then an external reset |
| test-187 8-round r1, boot `7f02df57` | during **normal running**: `enc35 frame done timeout` at kernel 6.739 s, then 36.8 s of silence, then an external reset |

All three were captured live on the host console — the last two independently, with
silences agreeing to 0.6 s. None left a panic, a lockup banner or a watchdog
report. None sat at 13-14 s. The 13-14 s window is where the
**deferred-probe burst** is (§4.2), and §4.4 already showed that reaching it does
not wedge anything — but the two failures on record are somewhere else entirely.
The premise in the brief, "an intermittent system-level stall in the 13-14 s window
after boot", is therefore **not supported by any captured failure**, and §4.2's
mechanism should be read as "the window's one deterministic event" rather than as
the failure's address.

**2. Two of the failures were inside the series recorded as 16/16 clean.** Boots
`1f85d97b` and `7f02df57` were each reset by nothing the harness asked for, and
`shutdown-capture.sh` never noticed because it scored rounds with a banner scan and
this failure emits no banner. The honest post-fix tally across test-187 and
test-188 is **22 warm cycles, 2 containing an unattended reset, 0 shutdown-path
stalls** — not 22 clean cycles.

**3. The failure has a shape, and it is an absence.** It is not a message to grep
for: it is a console that goes quiet while the port is still open, followed by a
reset nobody requested. Measured, the longest open-port silence is **0.597-1.085 s
across 15 clean rounds** and **28.903 s** in the A-5 failure. `docs/STALL_FAILURE_SHAPE.md`
has the analysis; `test-188/classify-captures.py` implements the scoring.

**Consequences for the plan.** The §7 matrix (A/B/C/G, `msm.no_gpu`,
`msm.disable_acd`, `deferred_probe_timeout`) is **not** retired — but it was built
to attack a stall in a window the failures do not occupy, so running it now would
test the wrong hypothesis with a low-rate event. The higher-value directions are
the ones §4.5 opens:

* **who resets the machine.** §4 shows it is not a kernel watchdog and not
  `panic=`; the stock DTS points at a Gunyah hypervisor watchdog mainline does not
  drive, and arming it is explicitly out of scope this round;
* **the five outstanding stop jobs** (§5 of the shape document) — the list to
  inspect first if the shutdown stall recurs;
* **`enc35 frame done timeout`**, which is the only message that tracks the one
  mid-run failure and which the project already knows is a full-modeset hazard.

---

### 4.6 AMENDMENT (round 17): the machine wedges at ~7 s, and the DPU is downstream

Round 17 stopped guessing from 22 host-watched cycles and read the device's own
journal instead.  journald keeps **89 boots** on this tablet, and a per-boot
outcome is derivable from it with no host at all
(`rootfs-overlay/usr/libexec/gts9-journal-survey`, analysis in
`reference/boot-tests/test-189-*/`).

**One of those 89 boots contains the trace this investigation has been missing.**
Boot `1c082657` (pre-fix) is the only one of the 89 that printed
`frame done timeout` at all, and it printed it 15 times — after this:

```
  ~6.5 s   reaches multi-user normally
  ~7.0 s   the journal STOPS.  No entry again until 37.2 s.
   37.228  rcu: INFO: rcu_preempt detected stalls on CPUs/tasks:
   47.261  Sending NMI from CPU 1 to CPUs 4:
   47.261  After 10 seconds, these CPUS still haven't responded to the NMI: 4
   47.261  Sending NMI from CPU 1 to CPUs 5:
   47.262  After 10 seconds, these CPUS still haven't responded to the NMI: 5
   47.262  [drm:dpu_encoder_frame_done_timeout] enc35 frame done timeout   <- FIRST
   62.437  BUG: workqueue lockup - pool cpus=4 ... stuck for 55s!          <- since ~7.4 s
  357.395  BUG: workqueue lockup - pool cpus=4 ... stuck for 350s!         <- last line
```

Three things follow, and the third changes a claim this project has been repeating.

**1. It is a CPU-level wedge, not a slow subsystem.** `After 10 seconds, these CPUS
still haven't responded to the NMI: 4` and `: 5` is direct evidence. CPU 7 answers
the same NMI with an idle backtrace, so this is not a global freeze — two CPUs
stop and the rest keep running.

**2. It starts at ~7 s.** Three independent numbers agree: the journal has no entry
between ~7.0 s and 37.2 s; the workqueue pool reports `stuck for 55s` at 62.437 s,
i.e. since ~7.4 s; and RCU had been failing long enough to report at 37.2 s. The
boot had just reached multi-user.

**3. The documented chain is inverted here.** `docs/DPU_TRACE.md`,
`docs/WATCHDOG_X710.md:22` and `gts9-power-key.c` all record
"`enc35 frame done timeout` → vblank wait timeout → workqueue lockup". In this boot
the **first** `enc35 frame done timeout` is at **47.262 s — about 40 s after the
wedge began**, and the message histogram is a list of victims:

```
  15  Workqueue: events drm_fb_helper_damage_work
  15  kworker/2:2 stuck in drm_crtc_wait_one_vblank
  18     pending: vmstat_update
   9  pwq 18: cpus=4 ... active=1     <- stalled pools
   9  pwq  7: cpus=1 ... active=1
```

`drm_fb_helper_damage_work` is parked in a vblank wait on a machine whose CPUs 4
and 5 are gone, and a per-CPU work item on a CPU that no longer runs anything sits
`pending` forever. **The DPU messages cannot be read as the origin** — which is
exactly the trap the brief warns about, and here it can be shown rather than
asserted.  It does not follow that the DPU has no bugs; it follows that these
messages are not its fault in this boot.

**What the 89-boot table adds.** Splitting on whether a boot printed the ACD error,
and keeping only boots that reached multi-user with a full journal (46 pre-fix, 29
post-fix):

| | pre-fix | post-fix |
|---|---|---|
| ended with an orderly shutdown | **1 / 46** | **23 / 29** |
| journal stopped with no shutdown | 45 / 46 | 6 / 29 |
| stopped in the 5.5-8.0 s band (freeze fingerprint) | 8 / 46 | 2 / 29 |

The first row is the largest effect in this whole investigation, but it is **not**
a stall rate: the pre-fix era is the bring-up era, when the device was being
flashed and power-cycled constantly. The third row is the honest one and it is
**not significant** (Fisher exact p = 0.30) — 8/46 against 2/29 does not
distinguish the two eras. What the table does establish is that the fingerprint is
recognisable in the journal alone, and that `1c082657` is not a one-off shape.

**The rate, and why it is the first usable one.**  Round 17-18 counted the wedge
signature across every boot the journal retains — an unanswered NMI, an RCU stall,
a workqueue lockup or a soft lockup.  None of those four can be produced by
flashing, by entering recovery or by pulling the power, so unlike the "ended without
a shutdown" count this one measures the failure and not the operator's activity
around it:

| era | boots | with the wedge signature |
|---|---|---|
| pre-fix (`Unable to send ACD` present, GPU never binds) | 46 | **10 (21.7%)** |
| post-fix (no ACD error, `Initialized msm … for 3d00000.gpu`) | 29 | **1 (3.4%)** |

Two-sided Fisher exact **p = 0.043**, and **all 11 carry the unanswered-NMI line** —
not one is a software stall that merely tripped a detector.  The single post-fix
one is `fa0f2151`, which is the *first* boot carrying the AOSS QMP + IPCC fix: the
boot before it, `f7b1e8de`, still prints the ACD error and never binds the GPU.

On that boot the profile's own recovery worked: `softlockup_panic=1` fired at
104.3 s (`CPU#7 stuck for 53s`) and rebooted.  `workqueue.panic_on_stall_time=45`
was armed too and the pool was stuck for 42 s when the 93 s report came out — three
seconds short.  `docs/CPU_WEDGE_EVIDENCE.md` has the full analysis.

**Where this leaves the chain.** The candidate chain in §3 puts GPU/GMU at the top
and RPMh/RSC near the bottom. This trace puts a **CPU-level wedge** at the top and
everything this project has been arguing about — DPU, workqueue, RCU, and by
extension the GPU chain — downstream of it. That is not a refutation of §4.2-4.5;
it is a warning that the first abnormal event in the only detailed trace on record
is "two CPUs stop", and no mechanism proposed so far explains that.

---

## 5. Excluded directions (do not re-investigate)

* **PCIe0 / its PHY** — disabled in DTS for a full A/B, stall reproduced (fact 7).
* **The watchdog helper's own output** as a *system* stall — it was console
  backlog (fact 8).
* **The kmsg mirror / DPU ftrace stream** — off in test-184 profile A, on in
  profile D, both 0 stalls (fact 8 and test-184).
* **The pogo keyboard as root cause** — docked and answering on clean boots; only
  its call path shows up in the failing one (fact 12).
* **`ttyMSM0`/`ttyGS0` device timeouts** — getty/device ordering, fixed, and the
  stalls predate them.
* **"DPU is the common root cause"** — DPU does fail, always *after* the first
  RPMh anomaly in the one boot that has both, and its own evidence shows a
  different shape (display death at 109.87 s) from the 13–14 s wedge.
  **This does not mean DPU has no bugs.** It means DPU is not the *common* cause,
  and its bugs must be argued from its own evidence (`docs/DPU_TRACE.md`).
* **The `supply vdd` / `supply vddcx` dummy-regulator messages** — see §8; they
  are expected on this SoC and are *not* to be "fixed" by inventing regulators.
* **`disp_cc_mdss_mdp_clk_src: rcg didn't update its configuration`** — recorded,
  not yet explained; not on the proven path of the 13–14 s wedge, and it is a
  display-clock symptom. Keep it on the list of unexplained early warnings (§9)
  but do not act on it this round.

---

## 6. Carried forward from `NEXT_STALL_DEBUG_PLAN.md`

The RPMh/RSC layer work is still available and its analysis stands:

* the `rpmh_write_batch()` **request-lifetime hazard** (`tcs->req[]` still points
  at a batch that the timeout path `kfree()`s) is real in source, is reported by
  patch `0021`, and is analysed in `docs/RPMH_TIMEOUT_LIFETIME_ANALYSIS.md`;
* the request/TCS/IRQ decision tree (§8 of that document) is the right tool for
  classifying a captured timeout — **and it is still unexercised**, because no
  real timeout dump has ever been captured (§4.4). Nothing in §4.2 above "lands
  in one of its rows"; that claim came from synthetic fixtures and has been
  removed.

What changes is **priority and framing**. Two things are now true that were not
before:

1. The ACD/AOSS config defect is cheaper to test, is a defect either way, and
   currently prevents the GPU from reaching the RPMh layer at all.
2. The strongest evidenced mechanism for the stall window (§4.2/§4.3) **does not
   require an RPMh timeout**. It requires only the deferred-probe timeout burst.
   So the RPMh layer may be a victim or an unrelated bystander, and the RPMh
   debug backport drops further down the priority list than the previous revision
   of this document placed it.

Test the config fix first; reach for RPMh instrumentation only if the A/B leaves
the burst hypothesis standing.

---

## 7. Experiment matrix

One variable per round. **B+C+D+E must never be combined.**

| id | name | kernel change | cmdline delta vs A | what it answers |
|---|---|---|---|---|
| **A** | baseline | none | — | does the stall still reproduce? (rate) |
| **B** | no-ACD | none | `+ msm.disable_acd=1` | does the GPU come up when the ACD requirement is removed? does the stall change? |
| **C** | no-GPU | none | `+ msm.no_gpu=1` (keeps `msm.separate_gpu_kms=1`) | is *anything* GPU-related required for the stall? strongest falsifier |
| **D** | AOSS QMP fix | `+ CONFIG_QCOM_AOSS_QMP=y` (no patch) | — | does giving the GPU its provider fix the GPU and/or the stall? |
| **E** | D + RPMh debug | `+ CONFIG_QCOM_AOSS_QMP=y`, `GTS9_RPMH_DEBUG=1` | `+ gts9_rpmh_debug=1` | if the stall survives D, classify the timeout per the §8 tree |
| **F** | cxpd backport | `+ 0007-…-stateless.patch` | — | does the `device_link_put_kref` WARN disappear, and does the stall change? |
| **G** | burst decoupled | none (same kernel as A/B/C) | `+ deferred_probe_timeout=300` | is the **deferred-probe-timeout burst** the trigger, independently of the GPU? |

Notes:

* A, B, C and G share **one kernel** and differ only in `vendor_boot` cmdline.
  That is the cheapest possible A/B and it is why they come first.
* **G is new in round 2** and is the most decisive single test available, because
  it attacks the mechanism of §4.2/§4.3 directly: same kernel, same broken GPU,
  same pending set — only the *instant* of the whole-system re-probe + sync_state
  walk moves (to ~304 s instead of ~14.3 s). If the stall tracks the timer, the
  burst is the trigger; if it does not, the burst is exonerated. Neither outcome
  requires new code or new instrumentation.
* **D is already built and its config change is committed**
  (`config: enable QCOM_AOSS_QMP so the SM8550 GPU can bind`). The resolved
  `out/kernel-gts9wifi/config` contains `CONFIG_QCOM_AOSS_QMP=y` with
  `CONFIG_MAILBOX=y`, `CONFIG_COMMON_CLK=y` and `CONFIG_PM=y`. What is *not* yet
  known is whether the GPU binds on real hardware — that is a physical-boot
  question, and it is the single most informative round available.
  Because D changes the kernel, its `boot.img` differs from A/B/C; that is
  expected and must be recorded in the round's artifact manifest.
* F is a real upstream bugfix that is worth carrying regardless of the stall
  outcome (see `docs/X710_X910_GPU_RPMH_DIFF.md` §"upstream fix"), and it is
  **already in the default queue**, so every build from here on contains it. It is
  *only* a WARN removal: with ACD still failing, the GPU stays deferred, so F must
  not be credited with anything beyond that.
* E's patch metadata is recorded in advance in
  `docs/RPMH_RSC_DEBUG_PATCH_STATUS.md`, together with why the existing opt-in
  patch `0021` is tried first.

### 7.1 Profiles

Each profile is a `boot/cmdline.*.example.txt` file. All of them keep the
hardware-verified console mapping (`ttyGS0` shell via `gts9-acm-getty`,
`console=ttyGS1` kernel console, `console=ttyMSM0` + `earlycon`), the watchdog
detectors, and `panic=10`.

* **Profile A — baseline** (`boot/cmdline.stall-ab-baseline.example.txt`):
  `gts9_dpu_flight=0` and `gts9_kmsg_mirror=0` must be *absent*, not `=0`, to
  avoid any observer effect. No RPMh diagnostic.
* **Profile B — no-ACD** (`boot/cmdline.stall-ab-no-acd.example.txt`):
  A + `msm.disable_acd=1`, nothing else.
* **Profile C — no-GPU** (`boot/cmdline.stall-ab-no-gpu.example.txt`):
  A + `msm.no_gpu=1`, nothing else; `msm.separate_gpu_kms=1` already present.
* **Profile G — burst decoupled** (`boot/cmdline.stall-ab-late-deferred.example.txt`):
  A + `deferred_probe_timeout=300`, nothing else. Moves the deferred-probe-timeout
  burst (§4.2) from ~14.3 s to ~304 s without changing the pending set, so it
  isolates *the burst* from *the GPU*.

Changing a profile changes **only `vendor_boot.img`**. `boot.img` (kernel + DTB)
and `init_boot.img` (initramfs) are byte-identical across A/B/C/G by construction.

---

## 8. On the `supply vdd` / `supply vddcx` dummy-regulator messages

Answering the brief's questions explicitly, from source rather than by adding
regulators:

* **Should these supplies exist in SM8550 upstream?** No. The A740 on SM8550 is
  powered through **genpd / RPMh power domains**, not through named regulators:
  `gmu@3d6a000` has `power-domains = <&gpucc GPU_CC_CX_GDSC>, <&gpucc GPU_CC_GX_GDSC>`
  with `power-domain-names = "cx", "gx"`, and the GPU OPP table carries
  `opp-level` + `opp-peak-kBps` (RPMh ARC votes and interconnect bandwidth), not
  `*-supply` rails.
* **Is the dummy regulator expected?** Yes. `adreno_probe()` calls
  `devm_regulator_get_optional()`-style lookup; with no `vdd`/`vddcx` properties in
  the DT, the regulator core hands back the dummy regulator and logs exactly this
  message. It is a *diagnostic consequence of the DT not describing rails*, which
  is correct for this SoC.
* **Does X910 show the same warning?** Its DT is derived from the same upstream
  `sm8550.dtsi`, so it is expected to; this is on the §11 comparison list as
  `needs stock X710 evidence` / `same hardware`, not as a defect.
* **Should we add regulators?** **No.** There is no evidence of a missing rail,
  and a guessed `regulator-always-on` on a GPU rail is exactly the kind of change
  the brief forbids. This item is closed unless a rail measurement says otherwise.

---

## 9. Unexplained early warnings, kept on the list

These are **recorded and not yet explained**. None of them is on a proven path to
the 13–14 s wedge, and none of them is acted on this round:

1. `disp_cc_mdss_mdp_clk_src: rcg didn't update its configuration` — **resolved as a
   separate investigation in round 14; see `docs/DISPCC_RCG_WARNING.md`.** It is
   `clk_rcg2_shared_init()` failing to park the RCG (`CMD_UPDATE` never clears within
   500 us), it is a known upstream issue class with a posted fix for the `eliza`
   platform, it fires at 0.374 s on every boot including all clean ones, and it is
   therefore **not** the stall. Whether it is harmless was not established: the
   `-EBUSY` does not stop the panel working, but the clock's post-failure state was
   not checked.
2. The `-ENOMEM` from a pstore `memcpy`-through-`copy_from` path seen on some
   stalls (a witness of memory corruption *if* real; not reproduced under control).
3. `deferred_probe_timeout` expiry with a non-empty pending list — **promoted in
   round 2** from "unexplained warning" to the leading mechanism (§4.2/§4.3) and
   therefore to a testable axis, profile **G** in §7.

---

## 10. Decision tree (fixed before data collection)

| Observation | Conclusion to draw | Next step |
|---|---|---|
| A stalls, **B does not** | the ACD requirement is on the causal path; GPU now binds | fix properly with the config, not by shipping `disable_acd`; investigate ACD→AOSS→GMU ordering |
| A stalls, B stalls, **C does not** | GPU/GMU *registration* is required for the stall, but not specifically ACD | go to **G** to separate "the burst" from "the GPU"; if G also stalls, instrument GMU init ordering |
| **C still stalls** | GPU/GMU is **demoted**; the stall is independent of the adreno driver entirely | go to **G** first (tests the burst without touching the GPU), then **E** and the §6 RPMh/RSC tree |
| **G does not stall** | the deferred-probe-timeout burst is the mechanism, independent of *which* device is deferred | strongest possible confirmation of §4.2; then reduce what is pending rather than the timer |
| **G still stalls** | the burst is **not** the trigger either; both the GPU chain and the burst hypothesis are weakened | go to **E** and the §6 RPMh/RSC tree with the desktop otherwise unchanged |
| D removes the ACD error **and** the stall | the missing provider is the cause | ship D; re-run A to confirm the rate change |
| D removes the ACD error but **not** the stall | a real bug was fixed and it is **not** the sufficient root cause | record exactly that; go to G, then E |
| F removes the `device_link_put_kref` WARN but the stall remains | a real GMU driver bug was fixed, not sufficient for the stall | record exactly that; never call it "the fix failed" |
| no stall in any profile | "not reproduced this round" | repeat A; do not change code |

**Status of G after round 11 (read this before running it).** G's premise was that
the deferred-probe burst is the prime suspect. §4.4 now contradicts that: 8
post-fix boots reached the burst at the same ~14.3 s with the same `sync_state`
load and did not stall. G therefore no longer tests a leading hypothesis — it would
test a weakened one. It remains a valid ablation, but the higher-value work is now
to determine whether the pre-fix failure recurs at all, since the AOSS QMP + IPCC
fix removed the only difference observed between surviving and failing boots. Keep
G in reserve for the case where the failure returns with the GPU already bound.

**Why G is high value.** It is a pure cmdline change (`deferred_probe_timeout=300`)
on the *same* kernel as A/B/C, needs no new code, and moves the one deterministic
system-wide event out of the observed stall window while leaving every deferred
device — GPU included — exactly as broken as it is in A. If the stall follows the
timer, §4.2 is confirmed and the fix direction becomes "reduce what is pending at
late_initcall", not "find a driver bug". If the stall stays at 13–14 s with no
burst there, the burst is exonerated and the RPMh/RSC direction returns to the
front. Either answer is decisive, which is what makes it a good experiment.

The parameter cannot *disable* the burst: `drivers/base/dd.c` arms it only
`if (driver_deferred_probe_timeout > 0)`, and `= 0` additionally changes
`driver_deferred_probe_check_state()` to return `-ETIMEDOUT` instead of
`-EPROBE_DEFER`, which alters behaviour for every optional supplier rather than
ablating the burst. A large positive value is the clean way to decouple the
timing.

---

## 11. Evidence discipline

* "First thing printed" ≠ "root cause". Build the chain in monotonic order and
  say explicitly which link is missing.
* A dump proves the state **at** the timeout, not what caused it.
* Zero reproductions are a result, not a failure: they bound the rate.
* Every claimed number must come from `journalctl -o short-monotonic`, the kernel
  console capture, or a `/proc/uptime`-based trace — never from screen ordering.
* Distinguish **cold boot** from **warm reboot** from **panic reboot** in every
  round record; a warm reboot is not a cold boot.

---

## 12. Safety boundaries

* No flashing, no partition writes, no BCB writes, no `dd` to any device node
  without an explicit instruction for that specific action.
* No PMIC register writes, no regulator/voltage changes, no PCIe changes, no
  bootloader/recovery changes, no keyboard firmware, no PSCI changes.
* The RPMh diagnostic is default-off and changes nothing unless
  `gts9_rpmh_debug=1` is on the command line.
* Not in scope this round: Gunyah watchdog driver, `qcom,gh-watchdog` DTS, PMIC
  voltages, SD rails, `regulator-always-on`, DPU rewrite, Pogo rewrite, Pogo MCU
  firmware, Wi-Fi/BT/camera/audio bring-up, GPU performance work, bulk
  `trace_pipe` to microSD, printk flooding.

---

## 13. Rollback

* Kernel/config: rebuild from the pinned tree with
  `BUILD_MODULES=0 ./scripts/build-kernel.sh`; `scripts/prepare-kernel.sh`
  restores the upstream state and re-applies only the default queue, so removing
  a patch file from `kernel/patches/` or a symbol from the fragment is a complete
  rollback.
* Boot images: restore the known-good pair (`boot.img` + `vendor_boot.img`) with
  the verified backup → SHA256 → flash → readback → SHA256 chain from test-183's
  `rollback.sh`.
* Device-side services: each unit is inert without its flag;
  `systemctl disable --now` removes it.
