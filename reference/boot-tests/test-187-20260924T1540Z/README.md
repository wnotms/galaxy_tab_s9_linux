# test-187 — X710 GPU / ACD / AOSS / GMU / RPMh stall A/B

Status: **candidate built and verified, NOT flashed.** No partition was written
and no power action was taken. See `candidate.txt` for the image hashes, the
flash order and the pre-agreed result matrix.

## Object of this round

Test the hypothesis in `docs/GPU_GMU_RPMH_STALL_PLAN.md` §3: that the X710 boots
with `CONFIG_QCOM_AOSS_QMP` unset, so the `qcom,qmp = <&aoss_qmp>` reference in
`gmu@3d6a000` cannot resolve, `a6xx_gmu_acd_probe()` fails with
`-EINVAL`/`Unable to send ACD state to AOSS`, and the GPU never binds.

This is the first round where that can be tested at all, because it is the first
build in which the GPU *can* bind.

## Profiles

| id | kernel | cmdline delta vs A | question |
|---|---|---|---|
| **A** = also **D** | AOSS QMP on, cxpd backport | — | does the GPU bind, and does the 13–14 s stall change? |
| **B** | same | `msm.disable_acd=1` | does removing the ACD requirement change anything on top of D? |
| **C** | same | `msm.no_gpu=1` | does the stall survive with the adreno driver never registered? |
| **E** | same | `gts9_rpmh_debug=1` | if the stall survives, classify the RPMh timeout |

A/B/C share one `boot.img` and differ only in `vendor_boot.img`. Profile A on
this kernel **is** the "profile D" experiment, because the AOSS QMP fix is a
config change and therefore lives in the kernel, not the command line.

## Files

| file | purpose |
|---|---|
| `candidate.txt` | image hashes, flash order, result matrix, rollback |
| `ab-run.sh` | this round's runner: wraps `scripts/stall-ab.sh` across the three profiles and writes the round README from the summaries |

## What was established before any device work

* `msm.no_gpu=1` and `msm.disable_acd=1` are the real command-line literals,
  verified against the built kernel's `modules.builtin.modinfo` — the C
  variables are `skip_gpu` and `disable_acd`.
* `msm.no_gpu=1` makes `adreno_register()` return before
  `platform_driver_register()`, so the GPU driver genuinely never registers.
* `msm.disable_acd=1` returns from `a6xx_gmu_acd_probe()` *before* the
  `IS_ERR_OR_NULL(gmu->qmp)` check, so profile B removes the ACD requirement
  rather than isolating ACD as a cause.
* Upstream `sm8550.dtsi` gives all eight GPU OPPs a `qcom,opp-acd-level`, so
  `cmd->enable_by_level` is `0x1fe` (non-zero) on this board — the failing branch
  is always taken when QMP is unavailable.
* The GPU node has no `vdd`/`vddcx` supply in **either** the X710 or the X910
  port, so the dummy-regulator messages are expected and are not a lead.
* Live read-only preflight on the currently flashed image: `gpu_bound=0`,
  `gmu_bound=0`, `aoss_bound=0`, `deferred=8`.

## Honest limits of this candidate

* The kernel **builds** and the bundles **validate**; that is `compiled` and
  `packaged`, not `booted`. Whether the GPU binds is a physical-boot question and
  nothing here claims otherwise.
* Because patch `0007` (the stateless cxpd link) is in the same kernel as the
  config fix, the disappearance of the `device_link_put_kref` warning cannot be
  attributed to either one alone. Do not report it as a config-fix success.
* A zero-stall result in any single profile is a bound on the rate, not a fix.
