# The GPU never retracts its RPMh votes: an upstream bug that is live in this pin

Found in round 21 while checking the Qualcomm GMU series' status. This is a
**one-line inverted condition** in `drivers/gpu/drm/msm/adreno/a6xx_gmu.c`, it is
present in the pinned `v7.2-rc3` **unmodified upstream**, and the upstream fix says
its consequence is *stale RPMh (BCM) votes after GMU suspend*. That places it on the
exact chain this round is investigating:

```
GPU / GMU  ->  power domain / runtime PM  ->  interconnect / RPMh vote
           ->  RSC / TCS transaction      ->  system-wide stall
```

## 1. The defect

`a6xx_rpmh_stop()` in the pinned tree, `drivers/gpu/drm/msm/adreno/a6xx_gmu.c:637`:

```c
static void a6xx_rpmh_stop(struct a6xx_gmu *gmu)
{
	...
	if (test_and_clear_bit(GMU_STATUS_FW_START, &gmu->status))
		return;                                    /* <-- inverted */

	if (adreno_is_a840(adreno_gpu))
		bitmask = BIT(30);

	gmu_write(gmu, REG_A6XX_GMU_RSCC_CONTROL_REQ, 1);

	ret = gmu_poll_timeout_rscc(gmu, REG_A6XX_GPU_RSCC_RSC_STATUS0_DRV0,
		val, val & bitmask, 100, 10000);
	if (ret)
		DRM_DEV_ERROR(gmu->dev, "Unable to power off the GPU RSC\n");

	gmu_write(gmu, REG_A6XX_GMU_RSCC_CONTROL_REQ, 0);

	set_bit(GMU_STATUS_PDC_SLEEP, &gmu->status);
}
```

`GMU_STATUS_FW_START` is **set** by `a6xx_rpmh_start()` (`a6xx_gmu.c:328`) once the
GMU firmware is running. `test_and_clear_bit()` returns true when the bit **was**
set, so this returns early exactly when the firmware *had* started — which is the
normal case — and the entire body is skipped:

* `REG_A6XX_GMU_RSCC_CONTROL_REQ` is never raised, so the RSC is never asked to
  power the GPU off;
* the RSCC status is never polled for the acknowledgement;
* the request is never cleared;
* `GMU_STATUS_PDC_SLEEP` is never set.

Upstream inverts it to `if (!test_and_clear_bit(...))`, i.e. "return when the
firmware was never started, otherwise do the stop sequence".

**This is upstream's code, not ours.** `git show HEAD:drivers/gpu/drm/msm/adreno/
a6xx_gmu.c` has the inverted form in the committed `v7.2-rc3` tree. The only change
this repository makes to that file is patch `0007`, which touches the two
`device_link_add()` calls at lines 2238 and 2425 and nothing else.

## 2. It is on the runtime-suspend path, which is why it matters

```
a6xx_gmu_pm_suspend()            a6xx_gpu.c:2213   (msm_gpu_funcs.pm_suspend)
  -> a6xx_gmu_stop()             a6xx_gmu.c:1478
       -> if (gmu->hung) a6xx_gmu_force_off()      a6xx_gmu.c:1121
          else           a6xx_gmu_shutdown()       a6xx_gmu.c:1409
                            -> a6xx_rpmh_stop()    <- returns immediately
```

Both branches reach it: `a6xx_gmu_shutdown()` ends with `a6xx_rpmh_stop(gmu)`
(`a6xx_gmu.c:1165` is inside `a6xx_gmu_force_off()`, which is the other caller).
So **every GPU runtime suspend** skips the retraction.

There is a decoy immediately before it:

```c
	/* Make sure there are no outstanding RPMh votes */
	a6xx_gmu_rpmh_off(gmu);          /* a6xx_gmu.c:1083 */
```

`a6xx_gmu_rpmh_off()` *polls* the RSCC TCS status bits and **ignores every return
value** — it waits up to 10 ms for votes that nothing has asked to be dropped yet.
It cannot retract a vote, and it cannot report that it failed.

## 3. Provenance

| | |
|---|---|
| series | `[PATCH 0/6] drm/msm: Assorted fixes - June/26` |
| our patch | **1/6** `drm/msm/a6xx: Fix stale rpmh votes after suspend` |
| author | Shivam Rawat `<shivrawa@qti.qualcomm.com>` |
| signed-off by | Akhil P Oommen `<akhilpo@oss.qualcomm.com>` |
| message-id | `20260605-assorted-fixes-june-v1-1-2caa04f7287c@oss.qualcomm.com` |
| posted | 2026-06-04 |
| lore | <https://lore.kernel.org/lkml/20260605-assorted-fixes-june-v1-1-2caa04f7287c@oss.qualcomm.com/> |
| patchew (series) | <https://patchew.org/linux/20260605-assorted-fixes-june-v1-0-2caa04f7287c@oss.qualcomm.com/> |
| latest revision | **v1** — no v2 exists, checked 2026-09-25 |
| `Fixes:` | `f248d5d5159a ("drm/msm/a6xx: Fix PDC sleep sequence")` |
| base-commit | `ef8274b9c19a4b614e10ce95553d0d363dc1c1f8` |
| review | replies from Neil Armstrong, Dmitry Baryshkov, Konrad Dybcio |

The patch's own words for the consequence:

> There are stale RPMH votes (BCM votes) observed after GMU suspend. This is
> because the rpmh stop sequences are skipped during gmu suspend. Fix this and
> also move GMU to reset state to avoid any further activity.

Note the second hunk — writing `REG_A6XX_GMU_CM3_SYSRESET` before
`a6xx_rpmh_stop()` in `a6xx_gmu_shutdown()` — is **already present** in the pinned
tree in a later upstream form (`a6xx_gmu.c:1158`, with `bus_halt` and
`a6xx_gpu_sw_reset` in between). So a backport here is hunk 1 only: **one line**.

The other five patches in the series are recovery/state-capture work
(`Recover HW before retire hung submit`, two `GPUCC register list for state
capture`, `Fix IRQ storm during msm_recovery test`, `Fix task_struct reference
leak in recover_worker`). `Fix IRQ storm during msm_recovery test` is in a related
class — an interrupt storm — but it is on the GPU-recovery test path rather than
the suspend path, so it is noted and not carried.

## 4. Why this is a better lead than the ones already closed

* it is an **upstream-acknowledged defect** with a `Fixes:` tag, not an inference
  from a symptom;
* it is on the **RPMh/BCM vote** path, and the one real `rpmh_write_batch()
  ACTIVE_ONLY transaction timeout` this project captured is reached through
  `qcom_icc_bcm_voter_commit()` — which is also the caller in the Qualcomm RSC
  debug series' own example stack
  (`docs/RPMH_RSC_DEBUG_PATCH_STATUS.md`);
* **the precondition is new on X710.** Before the round-15 AOSS QMP + IPCC fix the
  GPU never bound, `3d00000.gpu` had no driver, and nothing ever runtime-suspended.
  It binds now. The wedge rate fell from 21.7% to 3.4% at that same boundary and did
  not reach zero — which is consistent with the fix having enabled a *different*
  defect on the same path, but that consistency is not evidence;
* it is a **one-line change**, so a test of it is a genuine single-variable
  experiment.

## 5. What is *not* established, and what would settle it

**Not established: that this causes the CPU wedge.** The upstream commit reports
stale votes; it does not report hangs. Nothing yet connects a stale BCM vote to a
CPU that stops answering an ordinary IPI.

**Cheap on-device checks first, before any rebuild.** All are read-only:

```sh
# Does the GPU runtime-suspend at all on this board?  If it never does, this
# defect cannot bite and the whole lead is dead:
cat /sys/bus/platform/devices/3d00000.gpu/power/runtime_status
cat /sys/bus/platform/devices/3d00000.gpu/power/runtime_suspended_time
cat /sys/bus/platform/devices/3d00000.gpu/power/control        # expect "auto"

# Did the RSCC power-off handshake ever run?  With the bug it never does, and
# "Unable to power off the GPU RSC" never appears either:
dmesg | grep -c 'power off the GPU RSC'

# Is the RSC/PDC sleep flag ever set?  It is only set inside the skipped body:
dmesg | grep -c 'RSCC'
```

If `runtime_suspended_time` is non-zero and grows, the path is exercised and the
backport is worth a test. If the GPU never autosuspends, this lead closes and the
next step is to check why — that too is an answer.

**If it is exercised**, the experiment is one variable: apply hunk 1 alone, then
compare the wedge rate and the RPMh timeout count against the recorded baselines in
`docs/CPU_WEDGE_EVIDENCE.md`.

## 6. Status in this repository

The patch is kept at
`kernel/patches/pending/0008-drm-msm-a6xx-fix-stale-rpmh-votes-after-suspend.patch`.
`pending/` is **not** applied by `scripts/prepare-kernel.sh`, so nothing built today
carries it — deliberately, because test-191's whole value is that its `boot.img`
differs from the flashed one by exactly one config symbol, and because this round
does not modify two subsystems in one experiment.

It is a candidate for **test-192**, on its own kernel, with its own bundle. It is
not a fix claim.
