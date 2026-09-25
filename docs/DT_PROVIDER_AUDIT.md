# Every enabled DT node that has no driver, and the pattern behind most of them

Five of this port's defects have been the same shape: a device-tree node names a
provider, the provider's driver is not built, the consumer's probe returns
`-EPROBE_DEFER`, and the device sits on the deferred list for the life of the
boot — taking its `sync_state()` consumers down with it. Every one of the five was
found by hand:

| node | provider driver | symbol | found in |
|---|---|---|---|
| `81d00000.smem` | TCSR hardware mutex | `CONFIG_HWSPINLOCK_QCOM` | round 15 |
| `power-management@c300000` | AOSS QMP | `CONFIG_QCOM_AOSS_QMP` | round 15 |
| `mailbox@408000` | IPCC | `CONFIG_QCOM_IPCC` | round 15 |
| `17d90000.interconnect` | OSM L3 | `CONFIG_INTERCONNECT_QCOM_OSM_L3` | round 20 |
| `17d91000.cpufreq` | *(consumer of the one above)* | — | round 19 |

A sixth was missed in round 19 by the audit that was supposed to find it, for a
structural reason worth restating: that audit enumerated the interconnect
providers that **had bound** and found them all present. A provider with *no*
driver has no entry in such a list — it is absent, not misnamed — so no
provider-enumeration audit can ever find one. `mc_virt` appearing as
`interconnect-1` (a virtual provider has no unit address) is what made the list
look complete.

## The pattern: upstream's defconfig says `=m`, and this port has no modules

The root cause is not five unrelated mistakes. Upstream
`arch/arm64/configs/defconfig` expresses Qualcomm platform support as **modules**,
and this port installs no module tree, so every relevant `=m` silently becomes "no
driver at all":

```
arch/arm64/configs/defconfig:1868:CONFIG_INTERCONNECT_QCOM_OSM_L3=m   ->  was unset here
arch/arm64/configs/defconfig:1660:CONFIG_QCOM_ICC_BWMON=m             ->  unset here
arch/arm64/configs/defconfig:798:CONFIG_QCOM_SPMI_TEMP_ALARM=m        ->  unset here
arch/arm64/configs/defconfig:1649:CONFIG_QCOM_RMTFS_MEM=m             ->  unset here
arch/arm64/configs/defconfig:1943:CONFIG_CRYPTO_DEV_QCOM_RNG=m        ->  unset here
```

X910 hit the same trap and says so in its own fragment header
(`kernel/config/config-ubuntu-desktop.fragment`), which is why its answer to
`epss_l3` was one line of Kconfig. The general lesson is that **"is it in
upstream's defconfig?" is not the question; "is it `=y` in *this* config?" is.**

## The method, and the three traps it had to be cured of

`scripts/audit-dt-providers.py` runs two passes and then classifies.

**Pass 1 — what the built kernel declares.** The input is the **built** board DTB
(`out/kernel-gts9wifi/sm8550-samsung-gts9wifi.dtb`), not the DTS sources: the built
artifact is what the kernel was actually handed, including every DTBO and every
board-level override. The driver side is `modules.builtin.modinfo`, which carries
`alias=of:N*T*C<c1>[C<c2>...][C*]` for every built-in driver that registered an OF
device table; splitting on `C` recovers the individual compatible strings.

**Pass 2 — what the source declares.** Anything pass 1 rejects is re-checked
against the kernel source: a `{ .compatible = "x" }` initialiser, or one of the
declarator macros `IRQCHIP_MATCH("x", …)`, `TIMER_OF_DECLARE(name, "x", …)`,
`CLK_OF_DECLARE(…)`, `OF_DECLARE(…)`. The source file is then mapped to the
`CONFIG_` symbol whose Makefile rule builds it, and that symbol is read out of
`out/kernel-gts9wifi/config`.

**Classification.** `y` means a driver is built and the node is not a gap; `n`
means the driver is genuinely not requested; `m` means the symbol **is** requested
and this port installs no module tree, so `=m` yields no driver at all — the trap
behind most of these entries.

The only judgement left in the script is a list of compatibles that correctly have
no driver of their own — CPUs, caches, PMU, idle-state and OPP description nodes,
`fixed-clock`, PSCI, the arch timer, GIC, and nodes consumed by a parent driver.
Each entry carries its reason, so "it is allowlisted" cannot become an answer by
itself. Anything in neither list prints as `UNKNOWN` and makes the exit status
non-zero, so this is a gate rather than a report nobody reads.

### Three traps, all found by checking the tool's output instead of trusting it

Each of these made the audit say "fine" when it was not, which is the worst
direction for an audit to be wrong in.

1. **The modalias is not the binding test.** `of_match_node()` compares a node's
   compatible *strings* for exact equality against a driver's entries; the
   `alias=of:` modalias exists so udev can autoload a module, and it is a
   truncation of the *node's* modalias. The first version used the alias as the
   binding test, and read its `C*` form as "any compatible starting with this"
   rather than "this compatible, with further compatibles after it". That made
   `qcom,sm8550-llcc-bwmon` match the **LLCC controller's** `qcom,sm8550-llcc` —
   hiding one of the two findings this audit exists to report. There is no prefix
   matching in the script now, and a test pins that.
2. **A driver can be built and contribute no alias.** `pcie@1c00000` was reported
   as driverless: `CONFIG_PCIE_QCOM=y` and
   `drivers/pci/controller/dwc/pcie-qcom.c` matches `"qcom,pcie-sm8550"`, but the
   file registers **no** `MODULE_DEVICE_TABLE(of, ...)`, so no alias exists for
   pass 1 to see. It binds. Such nodes are now their own category, *bound, no
   `of:` alias*, and are not gaps.
3. **Mentioning a compatible is not declaring it.** `drivers/of/platform.c`'s
   `reserved_mem_matches[]` lists `"qcom,rmtfs-mem"` so that
   `of_platform_default_populate_init()` creates a platform device for that
   carve-out; it registers no driver and never binds. A bare "the file contains
   the string" filter took that as a driver and made a genuinely unbuilt one
   (`QCOM_RMTFS_MEM=n`) look built. Pass 2 therefore requires a *declaration*, and
   `drivers/of/` is excluded as device-tree infrastructure rather than drivers.

Three further Makefile idioms had to be handled in pass 2, all surfaced by nodes
that are plainly driven reporting as unresolvable. Pass 2 is also where the
pattern syntax bit: `grep -E` is POSIX ERE and has **no non-capturing groups**, so
a `(?:...)` alternation makes grep warn `? at start of expression` and match
nothing - which silently turned every gap into "no driver source at all".

* **composite objects.** `drivers/iommu/arm/arm-smmu/Makefile` has
  `obj-$(CONFIG_ARM_SMMU) += arm_smmu.o` with `arm_smmu-objs += arm-smmu.o`, and
  `drivers/soc/qcom/Makefile` has `qcom_rpmh-y += rpmh-rsc.o`. The symbol is on the
  composite's rule, not the object's;
* **objects built by an ancestor Makefile.** `drivers/gpu/drm/msm/disp/dpu1/` has
  no Makefile at all — `drivers/gpu/drm/msm/Makefile` lists `disp/dpu1/dpu_kms.o`
  inside its own `msm-y`. The lookup walks up, and at each level tries the path
  relative to that directory as well as the basename;
* **not every symbol resolves even so** (3 of 44 gaps), and the script says
  `unknown_symbol` rather than guessing. Those are listed with their source file so
  a human can finish the job.

Current result on the built kernel:

```
bound, alias in modinfo   : 107
bound, no of: alias       : 30    driver is =y, registers no MODULE_DEVICE_TABLE(of, ...)
real gaps (driver not =y) : 44
   symbol_off 30   module_only 2   no driver source 9   symbol unresolved 3
unknown                   : 0
```

**Limits, stated so the result is not over-read.** A gap means "no built-in driver
can bind this compatible". It does not by itself mean the boot is broken: the node
may be optional, may be consumed by a parent, or may not be needed by anything this
port uses yet. And a driver could bind through a non-OF path (`i2c_device_id`, a
`platform_device` registered by name) — none of the platform nodes here do, but the
audit cannot tell, so a gap is a question, not a verdict.

## The two gaps that are on the CPU path

### 1. `17d90000.interconnect` — `epss_l3` — fixed, test-191

Already enacted in `kernel/config/gts9wifi-mainline.fragment`
(`CONFIG_INTERCONNECT_QCOM_OSM_L3=y`). See `docs/PROVIDER_FOLLOWUPS.md` §4 and
`docs/X710_X910_GPU_RPMH_DIFF.md` §11. Candidate ready in
`reference/boot-tests/test-191-*`.

### 2. `24091000.pmu` and `240b6400.pmu` — the CPU and LLCC bandwidth monitors

```
soc@0/pmu@24091000   qcom,sm8550-llcc-bwmon", "qcom,sc7280-llcc-bwmon"
soc@0/pmu@240b6400   qcom,sm8550-cpu-bwmon",  "qcom,sdm845-bwmon"
```

both driven by `drivers/soc/qcom/icc-bwmon.c`, and
`# CONFIG_QCOM_ICC_BWMON is not set` (`out/kernel-gts9wifi/config:6899`).

This is the **DDR/interconnect half of the same story as `cpufreq`**. The driver
watches actual CPU↔LLCC and LLCC↔DDR traffic and votes interconnect bandwidth from
it, using `cpu_bwmon_opp_table` and `llcc_bwmon_opp_table`, which are both present
in the DTB. With it absent and `cpufreq` absent until test-191, this port had
**neither** half of CPU↔memory performance-state management: frequency was fixed at
whatever ABL left, and bandwidth was fixed at whatever vote was placed at boot.

Why it is *not* bundled into test-191, and why that is deliberate: test-191's whole
value is that four of its five images are byte-identical to what is flashed, so the
`epss_l3` symbol is the single variable. Adding `QCOM_ICC_BWMON` to the same build
would make two changes to the memory-performance path at once and make either
result uninterpretable. It is recorded here as its own candidate instead.

It is also **not** claimed to be the cause of the wedge. The honest statement is
the same as for `epss_l3`: a real gap, of a known class, on the path under
investigation.

## Everything else, classified

Complete list from the current build, with the reason each is parked:

**Provisioning gaps we would want eventually, none on the stall path**

| node(s) | symbol | why parked |
|---|---|---|
| `qcom,sm8550-trng` (`10c3000.rng`) | `CONFIG_CRYPTO_DEV_QCOM_RNG` | falls back to `qcom,trng`, which `qcom-rng.c` matches; the kernel still has other entropy sources |
| 5 × `qcom,spmi-temp-alarm` | `CONFIG_QCOM_SPMI_TEMP_ALARM` | PMIC thermal alarms; the SoC thermal zones are separate and are up |
| `qcom,spmi-adc5-gen3` | `CONFIG_QCOM_SPMI_ADC5_GEN3` | PMIC ADC; note the plain `SPMI_ADC5` **is** `=y` and is a different generation |
| `qcom,rpmh-stats` (`c3f0000.sram`) | `CONFIG_QCOM_RPMH_STATS` | debug-only counters |
| `qcom,bam-v1.7.4` (`1dc4000.dma`) | `CONFIG_QCOM_BAM_DMA` | the crypto BAM (`cryptobam`); falls back to `qcom,bam-v1.7.0`. Upstream defconfig has it `=y`, here `=n` |
| `qcom,sm8550-qce` (`1dfa000.crypto`) | `CONFIG_CRYPTO_DEV_QCE` | crypto offload, not correctness. `=n` |
| `qcom,rmtfs-mem` | `CONFIG_QCOM_RMTFS_MEM` | modem RMTFS carve-out; modem is out of scope. `=n` |
| `gpio-sbu-mux` | `CONFIG_TYPEC_MUX_GPIO_SBU` | Type-C SBU mux; the console does not need it. `=n` |
| `qcom,wcn6855-pmu` | `CONFIG_POWER_SEQUENCING_QCOM_WCN` | Wi-Fi power sequencing; out of scope. **`=m`** |
| `parade,ps5169` | *(none)* | Type-C redriver; no driver source declares it in this tree at all |

**Out of scope by instruction this round** — recorded so they are visibly parked,
not forgotten: `qcom,sm8550-camcc`, `qcom,sm8550-camss`, 2 × `qcom,sm8550-cci`,
`hynix,hi1337-gts9u-{rear,front}`, `dongwoon,dw9808-vcm`, `qcom,sm8550-videocc`,
`qcom,sm8550-iris`, `qcom,sm8550-lpass-{wsa,rx,tx,va}-macro`,
`qcom,sm8550-lpass-lpi-pinctrl`, `qcom,sm8550-sndcard`, 4 × `cirrus,cs35l45`,
`wacom,w90xx`, `st,fts1ba90a`, `siliconmitus,sm5440`, `siliconmitus,sm5714`,
`siliconmitus,sm5714-usbpd`, `qcom,wcn6855-pmu`, `qcom,wcn6855-bt`,
`pci17cb,1103`.

**Known and upstream-correct, not a defect**: `qcom,adreno-gmu-740.1`
(`3d6a000.gmu`). There is no standalone GMU platform driver upstream; `drm/msm`
drives the GMU as a sub-device, which is why it is a permanent `sync_state()`
blocker until the upstream "[PATCH RFT 0/5] drm/msm: Attach a driver to GMU"
series lands. `docs/PROVIDER_FOLLOWUPS.md` §2.

## What this does not establish

* That any of these gaps causes the CPU wedge. Two of them are on the CPU↔memory
  path and are worth one experiment each; the other forty are not on it.
* That the list is complete for drivers that *should* be built but have no DT node
  at all — this audit starts from the device tree, so a missing node and a missing
  driver look the same only when the node is missing too.
* That the `UNKNOWN` set stays empty. It is empty for this board and this build;
  a new node or a dropped symbol makes the audit fail loudly, which is the point.

## Reproducing it

```
scripts/audit-dt-providers.py            # needs a built DTB and modules.builtin.modinfo
scripts/audit-dt-providers.py --json
```

A host test runs it whenever those artifacts exist and asserts that `UNKNOWN` is
empty, so the gate lives in `python3 -B -m unittest discover -s tests` as well.
