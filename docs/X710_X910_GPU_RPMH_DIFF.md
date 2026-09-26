# X710 vs X910: GPU / GMU / AOSS / ACD / RPMh topology diff

Scope: only what bears on the `docs/GPU_GMU_RPMH_STALL_PLAN.md` failure chain.
This is not a general port comparison. Every row is classified with one of the
five labels the brief asks for:

`same hardware` · `different hardware` · `possibly relevant` ·
`definitely unrelated` · `needs stock X710 evidence`

Sources (all read directly; nothing here is quoted from the brief):

| tree | path | revision |
|---|---|---|
| X710 board DTS | `kernel/dts/sm8550-samsung-gts9wifi.dts` | this repo |
| X710 base SoC | `.work/linux-mainline/arch/arm64/boot/dts/qcom/sm8550.dtsi` | `a13c140cc` (v7.2-rc3) |
| X710 rendered DTB | `dtc -I dtb -O dts out/kernel-gts9wifi/sm8550-samsung-gts9wifi.dtb` | build of this repo |
| X710 resolved config | `out/kernel-gts9wifi/config` | build of this repo |
| X710 runtime | live `ttyGS0` probe, preflight of `scripts/stall-ab.sh` | this device |
| X910 board DTS | `.work/x910/ubuntu-galaxy-tab-s9-ultra/kernel/dts/sm8550-samsung-gts9uwifi.dts` | `4ff9d4b` |
| X910 config | `.work/x910/ubuntu-galaxy-tab-s9-ultra/kernel/config/config-mainline.aarch64` | `4ff9d4b` |

The X910 tree is a throwaway clone under `.work/` (not committed). To reproduce
this comparison:

```sh
git clone --depth 50 https://github.com/agcarbajo/ubuntu-galaxy-tab-s9-ultra \
    .work/x910/ubuntu-galaxy-tab-s9-ultra
git -C .work/x910/ubuntu-galaxy-tab-s9-ultra log -1 --format=%H
# 4ff9d4b0ba1ae40e7605ad54c0ffe561c1e26a60
```

Every X910 row below was read at that revision. If the upstream branch moves,
re-read the two files before trusting the quoted values.

---

## 0. Headline: the two ports compile the *same* SoC device tree

Both board DTS files `#include "sm8550.dtsi"`, and the X910 port pins the same
upstream commit this repo does (`a13c140cc289c0b7b3770bce5b3ad42ab35074aa`).

**Therefore `gpu@3d00000`, `gmu@3d6a000`, `gpucc`, `adreno_smmu`, `aoss_qmp`,
`apps_rsc`, `dispcc`, `gcc` and `ipcc` are byte-identical in both trees unless a
board DTS overrides them.** All the `qcom,opp-acd-level` values, the
`power-domains`/`power-domain-names`, the `interconnects` and the clock lists
come from the shared base and are *not* a port difference.

This matters because it removes almost every DT-level suspect from the table. The
whole GPU/AOSS/ACD delta between the two ports is:

1. **X910 adds a 9th GPU OPP** (`opp-719000000`, with its own
   `qcom,opp-acd-level`) — `possibly relevant`;
2. **X710 adds an `&scm` `interrupts` property** — `possibly relevant`;
3. **X710 disables two LPASS NOC interconnect providers X910 leaves enabled** —
   `possibly relevant`;
4. board peripherals outside the GPU/GMU nodes (`iris`, `mdss_dp0`,
   `lpass_ag_noc`, camera/fingerprint) — mostly `definitely unrelated`, listed for
   completeness;
5. **and, decisively, a Kconfig difference that is not in the DT at all:
   X910 sets `CONFIG_QCOM_AOSS_QMP=y` and X710 does not.**

---

## 1. GPU node (`gpu@3d00000`)

| item | X710 | X910 | class | note |
|---|---|---|---|---|
| `compatible` | `"qcom,adreno-43050a01", "qcom,adreno"` | same (shared base) | same hardware | |
| `reg` / `reg-names` | `0x3d00000+0x40000`, `0x3d9e000+0x1000`, `0x3d61000+0x800` / `kgsl_3d0_reg_memory`, `cx_mem`, `cx_dbgc` | same | same hardware | |
| `interrupts` | `GIC_SPI 300 LEVEL_HIGH` | same | same hardware | |
| `iommus` | `<&adreno_smmu 0 0>, <&adreno_smmu 1 0>` | same | same hardware | |
| `operating-points-v2` | `<&gpu_opp_table>` | same | same hardware | |
| `qcom,gmu` | `<&gmu>` | same | same hardware | |
| `interconnects` | `<&gem_noc MASTER_GFX3D … &mc_virt SLAVE_EBI1 …>`, name `gfx-mem` | same | same hardware | |
| `vdd-supply` / `vddcx-supply` | **ABSENT** | **ABSENT** | same hardware | ⇒ the dummy-regulator messages are expected on both; see §7 |
| `power-domains` on the GPU node | **ABSENT** (CX/GX are driven through `&gmu`) | **ABSENT** | same hardware | |
| `nvmem-cells` (speedbin) | **ABSENT** | **ABSENT** | same hardware | |
| `status` | base `disabled` → board `okay` | same override, byte-identical | same hardware | |
| `zap-shader/firmware-name` | `"qcom/a740_zap.mdt"` | identical | same hardware | |
| OPP table | 8 OPPs, 220–680 MHz | same 8 **+ `opp-719000000`** | **possibly relevant** | see §2 |

**Confirmed at runtime, not just in DT** (live probe on this device, current boot):

```
gpu=1  gmu_bound=0  gpu_bound=0  aoss_bound=0  deferred=8
```

`3d00000.gpu` exists as a platform device and **has never bound to a driver**.
That is the direct, empirical confirmation of the §2 chain in
`docs/GPU_GMU_RPMH_STALL_PLAN.md`: the GPU is not merely warning, it is unbound.

---

## 2. GPU OPP table and ACD levels

| item | X710 | X910 | class |
|---|---|---|---|
| OPP nodes | 8 (`sm8550.dtsi`) | 9 = same 8 + `opp-719000000` | **possibly relevant** |
| `qcom,opp-acd-level` count | **8** (one per OPP) | **9** | **possibly relevant** |
| the 8 shared values | `0x882e5ffd, 0xa82f5ffd, 0xe0285ffd, 0xe0285ffd, 0xc02a5ffd, 0xe02b5ffd, 0xe02d5ffd, 0xc02f5ffd` | **identical** | same hardware |
| the 9th value | — | `0x882e5ffd` at 719 MHz | **possibly relevant** |
| `&gpu_opp_table` override | **ABSENT** | present | **possibly relevant** |
| stock justification | none recorded | comment: "Samsung X910 stock GPU bin 0: 719 MHz, SVS_L2, DDR level 9, stock ACD" | needs stock X710 evidence |

### 2.1 What the 8-vs-9 difference actually does

`a6xx_gmu_build_freq_table()` seeds `freqs[0] = 0` (the "off" level) and then
appends every OPP. So:

* X710: `nr_gpu_freqs = 1 + 8 = 9`, valid indices `0..8`;
* X910: `nr_gpu_freqs = 1 + 9 = 10`, valid indices `0..9`.

`a6xx_gmu_acd_probe()` then loops `for (i = 1; i < gmu->nr_gpu_freqs; i++)` and
does `cmd->enable_by_level |= BIT(i); cmd->data[cmd_idx++] = val;`. Therefore:

| | OPPs | `enable_by_level` | ACD level words sent |
|---|---|---|---|
| **X710** | 8 | `BIT(1)..BIT(8)` = **`0x1FE`** | 8 |
| **X910** | 9 | `BIT(1)..BIT(9)` = **`0x3FE`** | 9 |

Both fit: `struct a6xx_hfi_acd_table.data[16 * MAX_ACD_STRIDE]` is `data[32]` and
`GMU_MAX_GX_FREQS` is 32, so neither tree overflows.

**Conclusion for X710:** `cmd->enable_by_level != 0` is guaranteed, so the
`IS_ERR_OR_NULL(gmu->qmp)` branch in `a6xx_gmu_acd_probe()` **is** taken and the
probe **does** fail. This is the mechanism, and it is independent of the X910
OPP difference — X910 would hit the same branch if its QMP were unavailable.

> **Update to the plan.** `docs/GPU_GMU_RPMH_STALL_PLAN.md` §2 wrote
> `cmd->enable_by_level = 0xff`; the correct value is `0x1FE` (8 bits set, from
> `BIT(1)` upward, because index 0 is the "off" level). The conclusion is
> unchanged. Corrected there as well.

---

## 3. GMU node (`gmu@3d6a000`)

| item | X710 | X910 | class |
|---|---|---|---|
| `compatible` | `"qcom,adreno-gmu-740.1", "qcom,adreno-gmu"` | same | same hardware |
| `reg` / `reg-names` | `0x3d6a000+0x35000`, `0x3d50000+0x10000`, `0xb280000+0x10000` / `gmu`, `rscc`, `gmu_pdc` | same | same hardware |
| `interrupts` / `interrupt-names` | `SPI 304`, `SPI 305` / `hfi`, `gmu` | same | same hardware |
| `power-domains` | `<&gpucc GPU_CC_CX_GDSC>, <&gpucc GPU_CC_GX_GDSC>` | same | same hardware |
| `power-domain-names` | `"cx", "gx"` | same | same hardware |
| `clocks` | 7: `GPU_CC_AHB_CLK`, `GPU_CC_CX_GMU_CLK`, `GPU_CC_CXO_CLK`, `GCC_DDRSS_GPU_AXI_CLK`, `GCC_GPU_MEMNOC_GFX_CLK`, `GPU_CC_HUB_CX_INT_CLK`, `GPU_CC_DEMET_CLK` | same | same hardware |
| `qcom,qmp` | **`<&aoss_qmp>` — present** | same | same hardware |
| `qcom,acd-level` / `qcom,arc-level` | **ABSENT** (not a 7.2-rc3 property; ACD lives in the *GPU* OPP nodes) | **ABSENT** | same hardware |
| `iommus` | `<&adreno_smmu 5 0>` | same | same hardware |
| `operating-points-v2` | `gmu_opp_table` (500/200 MHz, **no** ACD levels) | same | same hardware |
| `status` | unset ⇒ enabled | unset ⇒ enabled | same hardware |

**The GMU node is the same in both trees, `qcom,qmp` included.** The X710 DT is
therefore *correct*: it asks for the provider the driver needs. What is missing is
the **driver**, not the DT — see §5.

---

## 4. Power domains, clocks, interconnect

| item | X710 | X910 | class |
|---|---|---|---|
| CX / GX domains | `&gpucc GPU_CC_CX_GDSC` / `GPU_CC_GX_GDSC`, referenced by name `cx`/`gx` | same | same hardware |
| `qcom,gdsc` property | **ABSENT** anywhere | **ABSENT** | same hardware |
| `cx_ao` / `gx_ao` / `mx` / `rpmhpd` in the board DTS | **ABSENT** | **ABSENT** | same hardware |
| `gpucc` node | `"qcom,sm8550-gpucc"`, `0x3d90000+0xa000`, `#clock-cells=1`, `#reset-cells=1`, `#power-domain-cells=1` | same | same hardware |
| `dispcc` node | `"qcom,sm8550-dispcc"`, `0xaf00000+0x20000`, `power-domains = <&rpmhpd RPMHPD_MMCX>`, `required-opps = <&rpmhpd_opp_low_svs>` | same | same hardware |
| `gcc` node | `"qcom,sm8550-gcc"`, `0x100000+0x1f4200` | same | same hardware |
| GPU interconnect bandwidth | `opp-peak-kBps` per OPP, top 16500000 | same 8 values + `16500000` at 719 MHz | same shape, X910 one row longer |
| GPU/GMU related RPMh regulators | **none** — CX/GX are `gpucc` GDSCs, not PMIC rails | **none** | same hardware |
| `apps_bcm_voter` | `compatible = "qcom,bcm-voter"`, referenced by the NOCs | same | same hardware |
| `lpass_lpiaon_noc` / `lpass_lpicx_noc` | **`status = "disabled"`** on X710 | **left enabled** on X910 | **possibly relevant** |
| `lpass_ag_noc` | `disabled` | `disabled` | same hardware |

### 4.1 Why the LPASS NOC difference is only "possibly relevant"

Those two nodes are `qcom,bcm-voters = <&apps_bcm_voter>` interconnect
providers. Enabling or disabling them changes **which voters are aggregated into
every `ACTIVE_ONLY` RPMh batch**, including the `gfx-mem` and `mdp0-mem` paths.
The observed failure is an `ACTIVE_ONLY` RPMh transaction that never completes,
so "how many voters are in the batch" is a legitimate variable — but the X710
disables them for an unrelated historical reason and there is no evidence they
are involved. Classified `possibly relevant`, **not** investigated this round,
and **not** to be re-enabled without a dedicated A/B.

---

## 5. The actual difference: Kconfig, not device tree

This is the finding that explains why X910 does not show the X710 early anomaly.

| | X710 | X910 | class |
|---|---|---|---|
| `CONFIG_QCOM_AOSS_QMP` | **not set** (`out/kernel-gts9wifi/config`: `# CONFIG_QCOM_AOSS_QMP is not set`); the symbol is absent from `kernel/config/gts9wifi-mainline.fragment` | **`=y`** (`config-mainline.aarch64`: `CONFIG_QCOM_AOSS_QMP=y`) | **possibly relevant → causal** |
| **`CONFIG_DRM_MSM`** | **`=y` (built-in)** — `out/kernel-gts9wifi/config:4853` | **`=m` (module)** — `config-mainline.aarch64:6524` | **possibly relevant → causal to the timing** |
| `aoss_qmp` DT node | present, enabled, `compatible = "qcom,sm8550-aoss-qmp", "qcom,aoss-qmp"` | same | same hardware |
| GMU `qcom,qmp` phandle | present (`<&aoss_qmp>`) | same | same hardware |
| driver bound to `aoss_qmp` | **no** (`aoss_bound=0`, live probe) | yes | **causal** |
| `qmp_get()` result | `-EPROBE_DEFER` (node exists, `platform_get_drvdata()` is NULL) | valid `struct qmp *` | **causal** |
| ACD probe result | `-EINVAL`, "Unable to send ACD state to AOSS" | success | **causal** |
| GPU bound | **no** (`gpu_bound=0`, `gmu_bound=0`) | yes | **causal** |

Chain, every link read from source or measured:

```
CONFIG_QCOM_AOSS_QMP unset on X710, =y on X910
   → power-management@c300000 has no driver on X710
   → qmp_get() returns ERR_PTR(-EPROBE_DEFER)      [node present, drvdata NULL]
   → a6xx_gmu_acd_probe(): cmd->enable_by_level = 0x1FE (non-zero)
     and IS_ERR_OR_NULL(gmu->qmp)
   → "Unable to send ACD state to AOSS", return -EINVAL
   → a6xx_gmu_init() fails  (before a6xx_gmu_rpmh_init())
   → error path: device_link_del() on a managed link
   → WARN "Unable to drop a managed device link reference"
   → GPU permanently deferred
```

**X910 does not show this because its kernel contains the provider.** Its DT is
not different in any way that matters here; it simply has the driver compiled in.

### 5.1 A second, independent reason the two ports differ: `DRM_MSM` is a module on X910

X710 builds `CONFIG_DRM_MSM=y`; X910 builds `CONFIG_DRM_MSM=m`. That is not a
cosmetic difference, because `adreno_register()` is called from
`msm_drm_register()`, so the entire adreno/GMU probe lands in a different phase:

| | X710 (`=y`) | X910 (`=m`) |
|---|---|---|
| when the adreno driver registers | built-in `module_init` during `do_initcalls` | at `modprobe` time, from userspace |
| when `gpu@3d00000` is probed | inside the initcall/deferred-probe window | after userspace has started |
| does the GPU participate in `deferred_probe_timeout_work`? | **yes** | not at that point |
| can the GPU block `gcc`/`gpucc`/interconnect `sync_state()` during boot? | **yes** — real dump, §5 | no |

So X910 avoids the early-boot involvement of the GPU on *two* independent axes:
it has the AOSS QMP provider (so the GPU binds instead of deferring forever), and
it loads the display/GPU driver late (so even a deferring GPU would not be sitting
on the deferred list when the timeout burst runs).

**Do not copy `=m` to X710 as a fix.** X710 needs `msm` built in: the panel console
is the only bring-up console (`docs/DISPLAY_X710_OFFICIAL_V1.md`,
`docs/USB_SERIAL_CONSOLE.md`) and it must exist before any root filesystem, which
is exactly why the fragment keeps `CONFIG_DRM_MSM=y`. The actionable part of this
difference is the *AOSS QMP* half, which profile A/D already tests. The `=m` half
is recorded so the comparison is honest, not as a proposed change.

Independent corroboration that this dependency is real and not X710-specific: the
X910 source adds even more ACD levels (a 9th OPP with
`qcom,opp-acd-level = <0x882e5ffd>`), and it also carries a patch whose stated
purpose is to pull AOSS QMP in
(`kernel/patches/build-wcn-pcie-providers-in.patch` — `default y if ARCH_QCOM`
for the QMI helpers and the PCI power-sequencer). The port that carries *more*
ACD data is the one that made sure the provider is enabled.

---

## 6. items classified `definitely unrelated`

Recorded so they are not re-litigated, but **not** on the failure chain:

| item | X710 | X910 |
|---|---|---|
| panel / DDIC rail | `panel_ldo` + `display_avdd`, `regulator-always-on` | different panel hardware |
| touch controller | STM FTS1BA90A | Goodix GT9916 |
| WLAN | QCA6490 / `pci17cb,1103`, `wcn6855_pmu` | WCN7850 / `pci17cb,1107`, `wcn7850_pmu` |
| fingerprint | absent | EgisTec EL721, `vreg_l2b_3p3` |
| `uh_guest` carve-out | `0x3000000` | `0x3a00000` |
| `&iris` video decoder | `status = "okay"` + firmware | left `disabled` |
| `&mdss_dp0` | `status = "disabled"` | `okay` + `qcom,defer-hpd-until-first-resume` |
| `&scm { interrupts = … }` | present | absent |

Two of these deserve one sentence each because they are *near* the chain:

* **`&mdss_dp0` disabled on X710.** The X710 comment says the DP controller never
  finishes probing, so the msm DRM master cannot assemble. Because `adreno_bind()`
  → `msm_drm_init()` → `a6xx_gmu_init()` is the path in our captured backtrace,
  the display component set does gate *when* the GMU init path runs. It is
  `possibly relevant` to **timing**, and it is a deliberate, documented X710
  workaround that this round must not disturb. It is listed here, not acted on.
* **`&scm { interrupts = … }` only on X710.** The base `scm` node carries no
  `interrupts` in 7.2-rc3, so X710 adds the SCM waitqueue IRQ and X910 does not.
  Any TZ-mediated step in this bring-up goes through SCM. The X710 comment
  describing the upstream property as a malformed 3-cell specifier is **stale for
  this revision**; that should be corrected in the DTS comment, but the property
  itself is not to be removed this round (no evidence either way).

---

## 7. The `supply vdd` / `supply vddcx` messages: answered, not a defect

Question from the brief: are these expected, and does X910 have them?

| question | answer | evidence |
|---|---|---|
| Should the supplies exist in SM8550 upstream? | **No.** The A740 is powered through genpd/RPMh: `gmu@3d6a000` has `power-domains = <&gpucc GPU_CC_CX_GDSC>, <&gpucc GPU_CC_GX_GDSC>` and the GPU OPPs carry `opp-level`/`opp-peak-kBps`, not rails. | shared `sm8550.dtsi` |
| Is the dummy regulator expected? | **Yes.** No `vdd-supply`/`vddcx-supply` exists, so the regulator core returns the dummy regulator and logs exactly this. | `adreno_probe()` |
| Does X910 have it? | **Yes — both trees are identical here.** `vdd-supply` and `vddcx-supply` are ABSENT from the GPU node in *both*. | X910 DTS |
| Does the X710 stock DTS describe rails? | Stock 5.15 uses the downstream KGSL power-level model, which is not the mainline binding; it is not evidence for adding `*-supply` here. | `reference/stock/` |
| Should we add regulators? | **No.** There is no evidence of a missing rail, and a guessed `regulator-always-on` on a GPU rail is explicitly out of scope. | — |

**Therefore these two lines are a non-differentiator and a non-defect: closed.**

---

## 8. Deferred probe and the 13–14 s window

| item | X710 | X910 | class |
|---|---|---|---|
| `CONFIG_DRIVER_DEFERRED_PROBE_TIMEOUT` | `10` (`out/kernel-gts9wifi/config:1871`) | **`10`** (`.work/x910/…/kernel/config/config-mainline.aarch64:2097`) | **same hardware / not a differentiator** |
| pending deferred list at runtime | **8 devices** (live probe) | unknown | — |
| GPU contributes to the pending list | **yes** — permanent `-EPROBE_DEFER` | no | causal |

**The deferred-probe timeout value is identical in both ports**, so it is *not*
why X910 does not stall. Round 1 listed this as `needs stock X710 evidence`; it is
now read from the X910 resolved mainline config and closed.

What that leaves is the *composition* of the pending set, which is the actual
difference:

* **X910**: `CONFIG_QCOM_AOSS_QMP=y` → the GMU's `qmp_get()` succeeds → the GPU
  and GMU **bind** → they leave the deferred list → `gcc`, `gpucc` and the
  interconnect providers can complete `sync_state()` normally.
* **X710**: no AOSS QMP driver → the GMU defers **forever** → `gcc`, `gpucc` and
  `interconnect-1` can never finish `sync_state()` (real dump, §5) → at
  `late_initcall + 10 s` the timeout work re-probes that much larger pending set
  and walks `sync_state` across the whole graph at once.

So the correct reading of the X910 comparison is **not** "X910 avoids a
deferred-probe timeout" — both have the same 10 s timer and both fire it. It is
"X910's pending set is smaller and its `sync_state` graph is quiescent by the time
the timer fires, because its GPU actually probed."

That also means raising X710's timeout (profile G) is a legitimate *diagnostic*
for whether the burst is the trigger, but **not** a fix: it only moves the burst
later. The fix remains giving the GPU its provider.

The X710 deferred-probe timeout (10 s) sits inside the observed 13–14 s stall
window, and the GPU sits on the pending list for the whole time. This is
circumstantial: `docs/GPU_GMU_RPMH_STALL_PLAN.md` marks the link from
"deferred-probe activity" to "RSC wedge" as `???` and the experiment matrix is
designed to test it rather than assume it.

---

## 9. Upstream fix carried for the `device_link_del` WARN

| | X710 | X910 |
|---|---|---|
| `kernel/patches/0007-drm-msm-adreno-a6xx-mark-cxpd-device-link-stateless.patch` | **present** (added in this phase) | absent |
| `msm.disable_acd` / `msm.no_gpu` cmdline profiles | present (added in this phase) | absent |
| `diagnostic/0021-gts9-rpmh-timeout-state-dump.patch` | present (opt-in) | absent |

The patch is a **port-independent upstream bugfix**:
`DL_FLAG_STATELESS` for the GMU↔cxpd link, patch 1/5 of Akhil P Oommen's
"[PATCH RFT 0/5] drm/msm: Attach a driver to GMU"
([lore](https://lore.kernel.org/all/20260513-gmu-sync-state-fix-v1-1-6e33e6aa9b4f@oss.qualcomm.com/),
[patchew](https://patchew.org/linux/20260513-gmu-sync-state-fix-v1-0-6e33e6aa9b4f@oss.qualcomm.com/)),
Reviewed-by Dmitry Baryshkov, not merged as of this writing (v2 promised).

Classification: `possibly relevant` to the stall, **certain** as a bug fix. It
does not by itself make the GPU bind — the ACD/AOSS failure aborts
`a6xx_gmu_init()` first — so it removes the WARN without removing the cause. That
distinction is recorded in advance so the result cannot be over-read later.

---

## 10. Bottom line

1. The GPU/GMU/AOSS/RPMh **device trees are the same** in both ports; only the
   X910 719 MHz OPP and the X710 `&scm` interrupt differ inside that scope.
2. The X710 GMU node is **correct** — it references `&aoss_qmp`.
3. The difference that matters is that **X710 never enabled
   `CONFIG_QCOM_AOSS_QMP`**, so that reference cannot resolve, `qmp_get()` defers
   forever, and `a6xx_gmu_acd_probe()` fails with `-EINVAL`.
4. Measured on the device right now: `gpu_bound=0`, `gmu_bound=0`,
   `aoss_bound=0`, `deferred=8`.
5. The correct first fix is therefore a **config** change (profile D in the
   plan), not a DT change and not a driver patch. The `vdd`/`vddcx` messages are
   noise, and the `device_link_del` WARN is a real but *separate* upstream
   bugfix.

---

## 11. The CPU path: `epss_l3`, the second config defect X910 had already fixed

Sections 1–10 compare the GPU chain. This section extends the same comparison to
the **CPU** path, because round 19 narrowed the wedge to the big and prime clusters
(`docs/CPU_WEDGE_EVIDENCE.md`) and the CPU path had not been diffed at all.

Summary: the two ports instantiate the **same** upstream `sm8550.dtsi` CPU nodes,
but they resolve them with **different kernels**, and the X710 kernel is missing a
provider that the X910 kernel builds.

| item | X710 | X910 | class |
|---|---|---|---|
| `sm8550.dtsi` `cpu0` `interconnects` | `gem_noc`, `mc_virt`, **`epss_l3`** (3 paths) | identical (same upstream file) | **same hardware** |
| `interconnects` phandle targets decoded | `gem-noc` (0x7), `mc-virt` (0x8), `epss-l3` (**0x9**) | `gem-noc` (0x7), `mc-virt` (0x8), `epss-l3` (**0x9**) | **same hardware** |
| `epss_l3` provider driver | **none** — `17d90000.interconnect` unbound | `osm-l3` bound | **possibly relevant** ← the difference |
| `CONFIG_INTERCONNECT_QCOM_OSM_L3` | **unset** (`out/kernel-gts9wifi/config:7817`) | `=y` (`kernel/config/config-ubuntu-desktop.fragment:136`) | causal |
| `CONFIG_INTERCONNECT_QCOM_SM8550` | `=y` | `=y` | same hardware |
| `cpufreq@17d91000` driver state | **never probes** — permanent `-EPROBE_DEFER` | probes | causal |
| cpufreq policies / governor | **none**; fixed firmware-left OPP | `307–2016` / `499–2803` / `595–2956 MHz`, `schedutil` | causal |
| `gcc-sm8550` `sync_state()` | blocked by `17d91000.cpufreq` **and** `3d6a000.gmu` | blocked by neither | causal |
| CPU OPP tables (`cpu0/3/7_opp_table`) | upstream, with `opp-peak-kBps` | identical | same hardware |
| `qcom,opp-acd-level` in CPU OPP | absent (GPU OPP only) | absent | same hardware |
| `domain-idle-states` / `cpu-sleep-*-0` | upstream rail power collapse | identical | same hardware |

### 11.1 Mechanism

`qcom-cpufreq-hw` calls `dev_pm_opp_of_find_icc_paths(cpu_dev, NULL)` before it
registers anything, and that helper walks **every** `interconnects` phandle on
`cpu0`. Path 2 resolves to `&epss_l3`, `epss_l3` is
`compatible = "qcom,sm8550-epss-l3", "qcom,epss-l3"` driven only by `osm-l3`, and
upstream `arch/arm64/configs/defconfig` asks for that driver as `=m`. This port
builds no module tree, so `=m` yields nothing, `of_icc_get_provider()` finds no
registered provider for that node and returns `-EPROBE_DEFER`, and the probe defers
for the life of the boot.

The message is misleading in exactly one way, and it is worth stating because it
cost a round: `dev_err_probe()` logs `-EPROBE_DEFER` at debug level, so the inner
`_of_find_icc_paths: Unable to get path2` never reached the console and only the
outer `Failed to find icc paths` was recorded. The missing inner message was *not*
evidence that `_bandwidth_supported()` was responsible.

### 11.2 Why the earlier provider audit missed it

The round-19 audit enumerated the interconnect providers that *were bound* and
concluded all of them were. `mc_virt` was in that list under the name
`interconnect-1`, because a virtual provider has no unit address. A provider with
**no driver has no entry at all** — it is absent, not misnamed — so a
provider-enumeration audit cannot see it. The correct check is per-consumer-path:
for each `interconnects` phandle of the consumer, does that node have a bound
driver? That is what was done here for `cpu0`, `cpu3` and `cpu7`.

### 11.3 What is still *not* claimed

The cluster asymmetry is **not** explained by this: the defect removes frequency
scaling from all three clusters equally, and the wedge lands on big and prime. The
`epss_l3` L3 vote is shared (`SLAVE_EPSS_L3_SHARED`) and is voted from the CPU OPP
bandwidth values, so the *value* of the vote differs per cluster, but no evidence
yet connects a bootloader-left L3 vote to a CPU that stops answering NMIs.

Classification of the whole item: **possibly relevant** to the stall, **certain** as
a port defect. The measurement that separates the two is the wedge rate before and
after, against the baseline in `docs/CPU_WEDGE_EVIDENCE.md`.


---

## 12. `apps_rsc`, AOSS and reserved memory (round 29)

The brief's comparison list names `apps_rsc` (regulators, child layout, interrupts,
RPMh providers), AOSS (`qmp`, mailbox, related reserved memory) and the clocks.
This section closes those, and the answer for the first two is **identical**.

### 12.1 `apps_rsc`: identical, and that is a result

Neither board DTS touches the RSC's own properties. Both `grep` to **zero**
occurrences of `tcs-config`, of the RSC interrupt specifiers, and of `bcm-voter`.
The node body therefore comes from the shared upstream `sm8550.dtsi` in both
ports, unmodified:

```dts
apps_rsc: rsc@17a00000 {
	compatible = "qcom,rpmh-rsc";
	reg = <0 0x17a00000 0 0x10000>, ... <0 0x17a30000 0 0x10000>;
	interrupts = <GIC_SPI 3 ...>, <GIC_SPI 4 ...>, <GIC_SPI 5 ...>;
	qcom,tcs-offset = <0xd00>;
	qcom,drv-id = <2>;
	qcom,tcs-config = <ACTIVE_TCS 3>, <SLEEP_TCS 2>, <WAKE_TCS 2>, <CONTROL_TCS 0>;
	power-domains = <&cluster_pd>;
	apps_bcm_voter: bcm-voter { compatible = "qcom,bcm-voter"; };
	rpmhcc: clock-controller { ... };
	rpmhpd: power-controller { ... };
};
```

Both boards then extend `&apps_rsc` with **five** `regulators-N` blocks and
**three** `regulator-always-on` rails, and they are the *same three*:

| | X710 | X910 |
|---|---|---|
| `regulators-N` blocks under `&apps_rsc` | 5 | 5 |
| `regulator-always-on` rails | 3 | 3 |
| which rails | `vreg_l1b_1p8`, `vreg_l10b_1p8`, `vreg_l16b_3p0` | **the same three** |
| `tcs-config` / RSC interrupts / `bcm-voter` overridden | no | no |

**Class: same hardware, definitely unrelated.** The RSC's static description
cannot explain why one port stalls and the other does not. That matters because
the RSC is where the timeout-state run will be looking: the *node* is not the
difference, so any difference must be in what the two systems **ask of** it at
runtime - which is exactly what a TCS/IRQ snapshot measures.

### 12.2 AOSS: identical wiring on both

Both GMU nodes carry `qcom,qmp = <&aoss_qmp>` (X710 line 237, X910 line 242), and
the provider comes from the shared `sm8550.dtsi`. `CONFIG_QCOM_AOSS_QMP=y` and
`CONFIG_QCOM_IPCC=y` are now set on X710 as they always were on X910
(`docs/GPU_GMU_RPMH_STALL_PLAN.md` fact 19). **Class: same hardware.** The AOSS
path is no longer a differentiator, and the historical
`Unable to send ACD state to AOSS` is gone on X710 (`docs/X710_EARLY_BOOT_WARNINGS.md` §2).

### 12.3 Reserved memory: the ports are not equally observable

| | X710 | X910 |
|---|---|---|
| `ramoops` mentions in the board DTS | **10** | **0** |
| `sec_log` mentions | 3 | 2 |
| board overrides total | 64 | 63 |

X710 declares a `ramoops` region and X910 does not. That is why **every complete
failure record in this repository is an X710 pstore capture** - it is not
evidence that X910 has no failures, and the two ports are not equally
instrumented. **Class: different board config, diagnostic not causal.** It belongs
in the record because "X910 does not show these early anomalies" is a claim the
evidence cannot fully support while one port is being watched through a persistent
console and the other is not.

### 12.4 The Prime OPP X910 declares and X710 does not

The board-override lists differ in two OPP tables. The GPU one is §2's 8-vs-9
difference. The CPU one is new here:

```dts
/* X910 only */
&cpu7_opp_table {
	opp-3360000000 {
		opp-hz = /bits/ 64 <3360000000>;
		opp-peak-kBps = <(933000 * 16) (3686000 * 4) (1689600 * 32)>;
	};
};
```

Upstream `sm8550.dtsi` has **no** 3.36 GHz entry (`grep -c 3360000000` → 0), and
X710 adds none. Meanwhile X710's hardware advertises exactly that frequency, and
the driver says so on every boot:

```
cpu cpu7: Voltage update failed freq=3360000
cpu cpu7: failed to update OPP for freq=3360000
```

**Mechanism** (`drivers/cpufreq/qcom-cpufreq-hw.c`). In
`qcom_cpufreq_hw_read_lut()` the driver walks the *hardware* LUT - programmed by
ABL, not by DT - and for each entry calls `qcom_cpufreq_update_opp()`, which on
this path is:

```c
	ret = dev_pm_opp_adjust_voltage(cpu_dev, freq_hz, volt, volt, volt);
	if (ret) {
		dev_err(cpu_dev, "Voltage update failed freq=%ld\n", freq_khz);
		return ret;
	}
	return dev_pm_opp_enable(cpu_dev, freq_hz);
```

`dev_pm_opp_adjust_voltage()` needs the OPP to **exist**. X710's `cpu7_opp_table`
tops out at **3.1872 GHz**, so the 3.36 GHz lookup returns `-ENOENT`, the
`dev_err` fires, the caller's `dev_warn` follows, and that LUT entry is dropped.
On X910 the OPP is declared, so the same call finds it.

*(This paragraph said 2.9568 GHz when it was written. The pinned
`arch/arm64/boot/dts/qcom/sm8550.dtsi` ends at `opp-3187200000`, verified with
`grep -oE 'opp-hz = /bits/ 64 <[0-9]+>'` against the pinned source; 2.9568 GHz is
the second-highest entry, not the top. The error made the gap look smaller than it
is and is corrected rather than left in place.)*

**Fixed on 2026-09-26** by declaring the node X910 has, on X710. See
[GALAXY_PRIME_OPP.md](GALAXY_PRIME_OPP.md) for the full account, the compiled-DTB
verification and the scope boundaries. The "needs stock X710 evidence" line at the
end of this section still stands for the question of whether *stock* uses the bin;
what the fix rests on is only that this board's own hardware LUT advertises it and
the driver says so on every boot.

**This is not caused by the `epss_l3` fix.** `icc_scaling_enabled` is set simply
by `dev_pm_opp_of_add_table()` succeeding, i.e. by the CPU having a DT OPP table
at all, which X710 has had throughout - the interconnect path is not involved in
that branch. Checked because it was the first thing worth ruling out.

**It is also not a stall marker:** measured once per boot on **every** boot,
healthy and wedged alike, exactly like the dummy-regulator and `rcg` messages.
**Class: different board config, possibly relevant, needs stock X710 evidence** -
specifically whether the stock Samsung firmware advertises and uses 3.36 GHz on
this exact model, which `cpu7: failed to update OPP` suggests it does.
