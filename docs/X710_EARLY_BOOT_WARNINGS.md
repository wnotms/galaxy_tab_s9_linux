# The four early-boot messages on the X710 failure chain

Round 28. `GPU_GMU_RPMH_STALL_PLAN.md` §4 and the round brief both list four
messages as a suspected single initialisation chain, and both say they must not
keep being waved through as "unrelated warnings". This file audits each one
against the source, against X910, and against a live healthy boot. The
conclusion is not the one the chain hypothesis expected: **three of the four are
gone or structurally expected, and none of them is a marker.**

Measured on the healthy test-191 boot, `dmesg`, with the flash timestamps:

```
[    0.670356] disp_cc_mdss_mdp_clk_src: rcg didn't update its configuration.
[    0.694912] adreno 3d00000.gpu: supply vdd not found, using dummy regulator
[    0.694931] adreno 3d00000.gpu: supply vddcx not found, using dummy regulator
Unable to send ACD state to AOSS            count = 0
Unable to drop a managed device link ref    count = 0
```

All four, where they appear at all, land at **0.67–0.70 s** — three orders of
magnitude away from the 13–14 s window, and all of them on a boot that did not
stall.

## 1. `supply vdd not found` / `supply vddcx not found` — expected, and identical on X910

**Where it comes from.** `drivers/gpu/drm/msm/msm_gpu.c:955-964`:

```c
	/* Acquire regulators: */
	gpu->gpu_reg = devm_regulator_get(&pdev->dev, "vdd");
	if (IS_ERR(gpu->gpu_reg))
		gpu->gpu_reg = NULL;

	gpu->gpu_cx = devm_regulator_get(&pdev->dev, "vddcx");
	if (IS_ERR(gpu->gpu_cx))
		gpu->gpu_cx = NULL;
```

It is legacy code from the pre-OPP power model and it is called unconditionally
for every msm GPU. `devm_regulator_get()` does **not** fail when the DT property
is absent — it returns a dummy regulator and says so. The message is the
*normal* result of asking for a supply the platform does not describe, not a
failure to find one that should be there.

**The supply should not exist on this platform.** The upstream SM8550 GPU node
carries no `vdd-supply`, no `vddcx-supply` and no `power-domains`; it carries
`operating-points-v2 = <&gpu_opp_table>`. The GPU's CX and GX domains are
`gpucc` GDSCs, declared on the **GMU** node:

```dts
power-domains = <&gpucc GPU_CC_CX_GDSC>,
                <&gpucc GPU_CC_GX_GDSC>;
```

and the power level is voted through the OPP table's `opp-level`
(`RPMH_REGULATOR_LEVEL_*`) via the RPMh power domain. So on A740/SM8550 the
answer to the brief's question — "does it use genpd/RPMh rather than a
traditional regulator?" — is **yes**, and the two dummy-regulator messages are
what that design looks like from the legacy code path.

**X910 is the same.** Neither board DTS supplies the properties; both omit them.
`X710_X910_GPU_RPMH_DIFF.md` §7 has the row: `vdd-supply` / `vddcx-supply`
**ABSENT on both**, class `same hardware`, with the explicit consequence that the
messages are expected on both ports.

**So: do not add a regulator.** The brief anticipated this and the audit agrees.
Adding `vdd-supply` to the GPU node would replace a no-op dummy with a real
regulator that the hardware is not wired for, and would be a behaviour change
introduced to silence a message.

## 2. `Unable to send ACD state to AOSS` — gone, and it was a config bug

`a6xx_gmu_acd_probe()` (`a6xx_gmu.c`) prints this only when **both** hold:

```c
	/* It is a problem if qmp node is unavailable when ACD is required */
	if (cmd->enable_by_level && IS_ERR_OR_NULL(gmu->qmp)) {
		DRM_DEV_ERROR(gmu->dev, "Unable to send ACD state to AOSS\n");
		return -EINVAL;
	}

	/* Otherwise, nothing to do if qmp is unavailable */
	if (IS_ERR_OR_NULL(gmu->qmp))
		return 0;
```

So the historical message proves two things at once: the X710 DTB **does** carry
`qcom,opp-acd-level` (otherwise `enable_by_level` would be 0 and the function
would return 0 silently), and `gmu->qmp` was unavailable.

`gmu->qmp` comes from the GMU node's `qcom,qmp = <&aoss_qmp>`, and the provider
was missing. It is now fixed by configuration, not by a patch:
`CONFIG_QCOM_AOSS_QMP=y` and — critically — `CONFIG_QCOM_IPCC=y`, without which
the IPCC node that carries the RSC mailbox stays disabled. Measured live:

```
aoss_driver=qcom_aoss_qmp          (c300000.power-management is bound)
Unable to send ACD state to AOSS = 0
```

and `CONFIG_QCOM_AOSS_QMP=y` is now **identical to X910's** config, so this is no
longer a differentiator between the ports. The AOSS/ACD path is live and
exercised on every boot — which is exactly what makes profile B
(`msm.disable_acd=1`) a real A/B rather than a no-op: eight `qcom,opp-acd-level`
entries mean `enable_by_level != 0`, so the AOSS notification genuinely happens
today and disabling it genuinely removes it.

## 3. `Unable to drop a managed device link reference` — gone, and it was a real driver bug

This is the one the round brief matched to upstream's *"Mark cxpd device_link as
stateless"*, and the match is correct. A managed (`DL_FLAG_STATELESS` unset)
device link added during `a6xx_gmu_init()` and then dropped by hand puts the
device_link refcount out of balance, and the core reports the imbalance on the
error path.

`kernel/patches/0007-drm-msm-adreno-a6xx-mark-cxpd-device-link-stateless.patch`
is a clean backport of `[PATCH RFT 1/5]` from
*"[PATCH RFT 0/5] drm/msm: Attach a driver to GMU"*, reviewed by Dmitry
Baryshkov, still unmerged (no upstream SHA exists yet; the author promised a rev
2). It is **applied in the built kernel** — the build source tree
`.work/build/linux-src-gts9wifi` contains `DL_FLAG_STATELESS`, the pristine
checkout does not — and the message is **0** on the current boot.

Per the brief's situation 4, the honest reading is: *a real GMU driver bug was
fixed, and it is not the stall's sufficient root cause.* The stall survives this
fix (`STALL_FIRST_EVENT_ORDERING.md`), and that is not a failed fix.

## 4. `disp_cc_mdss_mdp_clk_src: rcg didn't update its configuration` — noise

Present **once** at 0.670356 s on this healthy boot, and once per boot on every
boot counted. It shares the DPU's `encoder is disabled` property exactly: it is
a boot-time, once-per-boot message that a stalling boot and a healthy boot both
print.

The reason is worth stating because the message reads like a fault. The RCG
(root clock generator) update is a *read-back poll*: the driver programs a new
configuration and then checks that the hardware reports the requested
configuration, warning if it does not settle within the poll. The display clock
is reparented early during `disp_cc` probe, and a source that is being switched
while its previous parent is still settling produces this line once and then
never again. It is not retried, it is not followed by a failure, and the display
comes up.

It is therefore added to the known-noise set alongside the DPU message, and
`wedge-rate.sh`'s `probe_markers` counts it per cycle so the claim has a
denominator rather than an impression.

## What this does to the candidate chain

The brief's chain was:

```
GPU deferred probe -> GMU -> CX/GX power domain -> device_link -> AOSS QMP
  -> ACD -> GPU RPMh/interconnect -> RSC/TCS transaction -> IRQ/completion
```

Auditing its four named messages does not support it as a chain:

* two of the four (`ACD`, `device_link`) are **already gone** and were config and
  driver-bug problems respectively, not stall causes;
* one (`dummy regulator`) is **structurally expected on both ports** and is the
  signature of the genpd/OPP design working as intended;
* one (`rcg`) is once-per-boot noise with a denominator.

The chain is therefore downgraded from "important anomaly chain" to **a set of
four resolved or explained early-boot messages**, and the markers that actually
separate a stalling boot from a healthy one remain the three in
`STALL_FIRST_EVENT_ORDERING.md`: `frame done timeout`, `mmc1: Timeout`,
`AMC RPMH` — present in 3 of 3 failures, absent from 22 of 22 clean boots.

That does **not** retire profiles B and C. It changes what they test: B no
longer tests "does removing a broken AOSS path help" but "does the ACD/AOSS
interaction matter at all", and C tests whether the GPU/GMU direction is worth
any further time. Both are still the cheapest available discriminators, which is
why they are the recommended next physical test.
