# X710 / X910 follow-ups: the providers behind the GPU fix

Written while the post-fix stall series was running on hardware. Two findings from
reading the X910 port (`agcarbajo/ubuntu-galaxy-tab-s9-ultra`, revision
`4ff9d4b0ba1ae40e7605ad54c0ffe561c1e26a60`) and the pinned tree. Neither is acted
on this round; both are recorded because they explain symptoms that appeared
*after* the AOSS QMP + IPCC fix.

## 1. The X910 port patches `qcom-ipcc` for channel starvation

X910 carries `kernel/patches/ipcc-reserve-gts9u-runtime-channels.patch`. Its own
message:

> The SM-X910 port creates some DSP endpoints after IPCC has probed, because
> changing the boot DTB layout breaks Samsung ABL. Counting only clients present
> at probe reserves seven channels; ADSP, CDSP, SPSS and MPSS need eight when
> combined with SMP2P and AOSS. MPSS plus CDSP then fails with `-EBUSY` even
> though the requested client/signal pair is unused.
>
> On this board reserve at least the 48 channels used by Samsung's downstream
> IPCC driver. This changes allocation capacity only, not interrupt routing.

and the change:

```c
/* Late-created SM-X910 DSP endpoints are absent from the initial DT. */
if (of_machine_is_compatible("samsung,gts9uwifi"))
        ipcc->num_chans = max(ipcc->num_chans, 48);
```

**Why this matters to X710.** `qcom_ipcc_setup_mbox()` sizes the mailbox
controller by *counting* the `mboxes` phandles that point at it in the DT:

```c
ipcc->num_chans = 0;
for_each_node_with_property(client_dn, "mboxes") {
        if (!of_device_is_available(client_dn))
                continue;
        i = of_count_phandle_with_args(client_dn, "mboxes", "#mbox-cells");
        for (j = 0; j < i; j++) { ... if (!ret && curr_ph.np == controller_dn) ipcc->num_chans++; }
}
```

Every channel is then an identical `{client, signal}` slot whose identity is
resolved at xlate time, so **the capacity is a pure client count and carries no
notion of which pairs exist**. Any client that appears after IPCC probed — a
late-registered platform device, a module, or an endpoint created by another
driver — consumes capacity that was never counted, and once the slots are gone
the next request fails with `-EBUSY` regardless of whether the pair is in use.

X710 had `CONFIG_QCOM_IPCC` unset until this round, so this starvation could not
have been observed before. Whether X710 hits it is **not yet determined**; what is
determined is that the mitigation is board-specific in X910 (`of_machine_is_
compatible("samsung,gts9uwifi")`) and would need an equivalent condition for
`gts9wifi`, or a non-board-specific fix.

### What X710 actually shows instead

After the IPCC fix, the `smp2p-*` devices changed their deferred reason:

| | before the fix | after the fix |
|---|---|---|
| `smp2p-adsp/cdsp/modem` | `qcom_smp2p: IRQ index 0 not found` | `qcom_smp2p: unable to allocate local smp2p item` |

The *first* reason was the missing IPCC interrupt controller, and the fix cured
it. The *second* is a different failure, from a different provider:

```c
/* drivers/soc/qcom/smp2p.c */
ret = qcom_smem_alloc(pid, smem_id, sizeof(*out));
if (ret < 0 && ret != -EEXIST)
        return dev_err_probe(smp2p->dev, ret,
                             "unable to allocate local smp2p item\n");
```

So this is **SMEM allocation**, not IPCC. It is a genuine remaining defect on
X710 and is *not* in the GPU/AOSS/ACD chain, so it neither explains nor is
explained by the GPU fix. It should be investigated on its own terms: what the
SMEM heap looks like for each remote pid, and whether `smem@81d00000` is sized or
partitioned differently from X910.

Note the ordering question this raises: IPCC channel starvation and SMEM
allocation failure are two different ways for the same three `smp2p-*` devices to
fail, and X710 currently shows the second. If the first is also present it is
masked, because `qcom_smp2p` allocates its SMEM item before it requests its
mailbox.

## 2. Why `gmu@3d6a000` can never bind, and why that is upstream-correct

The post-fix burst still reports:

```
gcc-sm8550 100000.clock-controller: sync_state() pending due to 3d6a000.gmu
gpu_cc-sm8550 3d90000.clock-controller: sync_state() pending due to 3d6a000.gmu
```

`gmu@3d6a000` has `compatible = "qcom,adreno-gmu-740.1", "qcom,adreno-gmu"`, and
in the pinned tree there is **no platform driver matching `qcom,adreno-gmu`**. The
GMU is not a standalone device: `a6xx_gpu.c` looks it up by phandle
(`qcom,gmu = <&gmu>`) and drives it through the `adreno` driver as a sub-device.
The only `qcom,adreno-gmu` string in the tree is a *compatible check* for the
wrapper variant:

```c
/* drivers/gpu/drm/msm/adreno/a6xx_gpu.c */
adreno_gpu->gmu_is_wrapper = of_device_is_compatible(node, "qcom,adreno-gmu-wrapper");
```

So the GMU platform device exists, never binds, and is a permanent `sync_state`
blocker for every clock controller that lists it as a consumer.

**This is upstream behaviour, not an X710 bug**, and it is why fixing the GPU did
not remove the `sync_state` line. It is also the mechanism behind the upstream
series already recorded in `kernel/patches/`:

> `[PATCH RFT 0/5] drm/msm: Attach a driver to GMU` — *"With the introduction of
> sync_state in the genpd framework, any consumer device of GCC and GPUCC which
> is not bound to a driver will result in bootup warnings like `gcc-kaanapali
> 100000.clock-controller: sync_state() pending due to 3d37000.gmu` … To silence
> these warnings and also to have a proper state in driver core, attach a driver
> to the GMU."*

That series is patch 5/5 — the part X710 has **not** backported. X710 carries only
patch 1/5 (`0007`, the stateless cxpd link). So the remaining `sync_state` line is
exactly the symptom the rest of that series exists to fix, and patch 5/5 is now
the natural next backport **if** the post-fix stall series shows the burst still
matters.

### Consequence for the investigation

Fixing ACD did not remove the sync_state blockage, because the blockage is
structural (no GMU driver), not ACD-dependent. So:

* if the post-fix series is clean, the remaining `sync_state` line is cosmetic and
  can wait for the upstream series to land;
* if the post-fix series still stalls in the 13-14 s window, the `sync_state`
  blockage is the prime suspect and patch 5/5 becomes the next experiment.

Either way the decision is now data-driven on the series that is running, which is
why this note stops short of proposing the backport as a fix.

## 3. Not investigated, recorded only

* **SMEM allocation failure** (§1) — needs its own analysis of
  `qcom_smem_alloc` and the `smem@81d00000` carve-out.
* **`aux_bridge.aux_bridge: failed to acquire drm_bridge`** and
  **`qcom-pcie: cannot initialize host`** remain on the deferred list. Both were
  on it before this round and are outside the GPU chain.
* **`17d91000.cpufreq: qcom-cpufreq-hw: Failed to find icc paths`** likewise.
* **Slow boot to login**: `systemd-analyze` reports 1.303 s kernel + 5.458 s
  userspace, so kernel init and systemd are both fast; the extra wall-clock time
  is before `systemd-analyze`'s window (initramfs) or in panel bring-up, and was
  not measured this round.
