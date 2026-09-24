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
| 10 | real stalls cluster at **13.3–14.3 s** after boot | §4.1 |
| 11 | the earliest captured software-visible anomaly in a failing boot is an **ACTIVE_ONLY RPMh transaction timeout** | `rpmh_write_batch()` `WARN_ON(1)`, `rpmh.c:386`, at +14.27 s |
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
| 24 | `RPMH_TIMEOUT_MS` is 10 s, so a +14.27 s `rpmh_write_batch()` warning means the batch was **submitted at ≈ +4.27 s**. | `drivers/soc/qcom/rpmh.c:25` |

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
> device tree requires for ACD. That leaves the GPU in a permanent probe-defer,
> and the resulting early-boot init/cleanup burst — GPU probe + device-link
> teardown + deferred-probe retry storm + sync_state at
> `CONFIG_DRIVER_DEFERRED_PROBE_TIMEOUT` — is the trigger that wedges the apps_rsc
> TCS machinery at ≈ +4.27 s and produces the observed 13–14 s stall.

Stated as a chain, with the *unproven* links marked:

```
CONFIG_QCOM_AOSS_QMP unset                    [PROVEN, fact 19]
        ↓
aoss_qmp device has no driver                 [PROVEN]
        ↓
qmp_get() → -EPROBE_DEFER                     [PROVEN, source]
        ↓
a6xx_gmu_acd_probe() → "Unable to send ACD state to AOSS", -EINVAL   [PROVEN, source + log]
        ↓
GPU probe fails; device_link_del() WARN       [PROVEN, log]
        ↓
GPU permanently deferred; retried forever     [PROVEN, source]
        ↓
??? early-boot init/cleanup burst ???         [HYPOTHESIS]
        ↓
apps_rsc stops completing TCS transactions ≈ +4.27 s   [OBSERVED, §4.2]
        ↓
RPMh clients block on their 10 s completions  [OBSERVED, §4.2]
        ↓
CPU#5 stops running the watchdog kthread      [OBSERVED, §4.1]
        ↓
soft lockup fires at +13.4 s, RPMh WARN at +14.27 s   [OBSERVED, §4.1]
```

The `???` link is the whole question. It is **not** established that the missing
config causes the RSC wedge; it is established that the missing config is a real
bug that must be fixed regardless, and that it makes every GPU/GMU/RPMh hypothesis
untestable until it is fixed.

**Necessary correction to the brief's framing.** The brief lists
`msm.disable_acd=1` as an A/B "to isolate the GPU ACD → AOSS QMP path". Because
QMP is *already* non-functional (fact 19), `disable_acd=1` is not an isolation of
ACD — it is a **substitute for the missing provider**: it takes the first branch
of `a6xx_gmu_acd_probe()` and returns success before the QMP check. It is still a
useful and cheap experiment, but it must be described as *"does the GPU come up if
we remove the ACD requirement?"*, not *"is ACD the cause?"*.

---

## 4. Measured timeline (from real hardware evidence only)

All figures are `journalctl -o short-monotonic` / console-capture monotonic
timestamps. No screen ordering is used (test-184 fact 8).

### 4.1 The stall, from `reference/boot-tests/test-186-*/fixtures/victim.log`

| monotonic | event |
|---|---|
| ~4.09 s | `printk: legacy console [ttyMSM0] enabled` — GPU probe window opens |
| ~4.12 s | `adreno 3d00000.gpu: supply vdd not found, using dummy regulator` |
| ~4.13 s | `adreno 3d00000.gpu: supply vddcx not found, using dummy regulator` |
| ~4.14 s | `platform 3d6a000.gmu: [drm:a6xx_gmu_acd_probe] *ERROR* Unable to send ACD state to AOSS` |
| ~4.15 s | `Unable to drop a managed device link reference` + `device_link_put_kref` WARN, `Workqueue: events_unbound deferred_probe_work_func` |
| **13.400 s** | `watchdog: BUG: soft lockup - CPU#5 stuck for 22s! [kworker/u32:18:174]` |
| **14.270 s** | `WARNING: drivers/soc/qcom/rpmh.c:386 at rpmh_write_batch` (10 s timeout ⇒ submit ≈ **4.27 s**) |

Note the soft-lockup line's own arithmetic: "stuck for 22s" at 13.400 s places the
last run of that CPU's watchdog kthread at ≈ **-8.6 s**, i.e. before kernel start.
That number is not usable as a stall-onset estimate; it is quoted here so nobody
later reads 13.4 s as "the stall began at 13.4 s". The reliable statement is the
weaker one: **by 13.4 s, CPU#5 had not run its watchdog kthread for far longer
than the threshold.**

### 4.2 What actually stopped, from `test-186-*/fixtures/programmed-no-completion.log`

Both RPMh clients in the ring submitted at ≈ +4.27 s and both timed out at
+14.27 s:

| client | submitted | TCS outcome | ring summary |
|---|---|---|---|
| `1c00000.interconnect`, `kworker/6:0` | +4271 ms, `tcs=3` | `tcs_in_use=0x8`, `cmd_enable=0x1`, request still stashed | `send=2 done=1 matched_send=1 matched_done=0` → *programmed but never completed* |
| `5-002a` (pogo), `kworker/u32:18` | not in ring | `holder_tcs=-1` | `send=1 done=0 matched_send=0` → *did not reach TCS programming* |

So one client had its command written into a TCS that was never completed, and a
*different* client could not get a TCS at all. A plausible reading — hypothesis,
not fact — is that one stuck TCS plus the client-side cache blocked behind it
stops every later RPMh client on that RSC.

`tcs_in_use=0x8`, `irq_status=0x0`, `irq_enable=0x7fff`: the TCS bit is set as
in-use, no TCS completion bit was raised, and the RSC irq was enabled. Per the
decision tree in `docs/NEXT_STALL_DEBUG_PLAN.md` §8 this is the
"programmed, no completion, TCS still in use with CMD_ENABLE set" row — i.e.
**the request reached the RSC and never completed**, which points at RSC/TCS
hardware completion, not at IRQ delivery.

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

The RPMh/RSC layer work is still the right long-term direction and its analysis
stands unchanged:

* the `rpmh_write_batch()` **request-lifetime hazard** (`tcs->req[]` still points
  at a batch that the timeout path `kfree()`s) is real, is reported by patch
  `0021`, and is analysed in `docs/RPMH_TIMEOUT_LIFETIME_ANALYSIS.md`;
* the request/TCS/IRQ decision tree (§8 of that document) is the right tool for
  classifying a captured timeout, and §4.2 above already lands in one of its rows.

What changes is **priority**: the ACD/AOSS config defect is cheaper to test, is a
defect either way, and currently prevents the GPU from reaching the RPMh layer at
all. Test it first.

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

Notes:

* A, B and C share **one kernel** and differ only in `vendor_boot` cmdline. That is
  the cheapest possible A/B and it is why they come first.
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

Changing a profile changes **only `vendor_boot.img`**. `boot.img` (kernel + DTB)
and `init_boot.img` (initramfs) are byte-identical across A/B/C by construction.

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

1. `disp_cc_mdss_mdp_clk_src: rcg didn't update its configuration` — display clock
   RCG not locking. Display is known-working afterwards, so this is either a
   benign re-configuration or a real timing issue in `dispcc`.
2. The `-ENOMEM` from a pstore `memcpy`-through-`copy_from` path seen on some
   stalls (a witness of memory corruption *if* real; not reproduced under control).
3. `deferred_probe_timeout` expiry at +10 s with a non-empty pending list — the
   GPU contributes to that list by construction (fact 20 chain).

---

## 10. Decision tree (fixed before data collection)

| Observation | Conclusion to draw | Next step |
|---|---|---|
| A stalls, **B does not** | the ACD requirement is on the causal path; GPU now binds | fix properly with **D**, not by shipping `disable_acd`; investigate ACD→AOSS→GMU ordering |
| A stalls, B stalls, **C does not** | GPU/GMU *registration* is required for the stall, but not specifically ACD | go to D; if D also stalls, instrument GMU init ordering |
| **C still stalls** | GPU/GMU is **demoted**; the stall is independent of the adreno driver entirely | stop spending time on GPU; go to **E** and the §6 RPMh/RSC tree, then IRQ/scheduler/deferred-probe |
| D removes the ACD error **and** the stall | the missing provider is the cause | ship D; re-run A to confirm the rate change |
| D removes the ACD error but **not** the stall | a real bug was fixed and it is **not** the sufficient root cause | record exactly that; go to E |
| F removes the `device_link_put_kref` WARN but the stall remains | a real GMU driver bug was fixed, not sufficient for the stall | record exactly that; never call it "the fix failed" |
| no stall in any profile | "not reproduced this round" | repeat A; do not change code |

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
