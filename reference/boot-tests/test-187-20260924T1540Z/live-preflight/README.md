# test-187 live pre-flight — read-only state of the currently flashed image

Captured over the USB ACM shell (`COM17`) on 2026-09-24 before any flash, with
read-only commands only. Nothing was written, no boot was issued.

Purpose: confirm the round-2 mechanism against the *live* kernel rather than only
against archived logs, and record the exact state the A/B starts from.

## Device state

```
boot_id    f7b1e8de-1487-4eb3-8819-5cb273b2b740
uptime     5934.72 s
release    7.2.0-rc3-gts9wifi-dirty
```

## The GPU never binds (confirmed live)

```
/sys/bus/platform/devices/3d00000.gpu/driver          -> GPU_UNBOUND
/sys/bus/platform/devices/3d6a000.gmu/driver          -> GMU_UNBOUND
/sys/bus/platform/devices/power-management@c300000/driver -> AOSS_UNBOUND
```

and the probe fails by name, with the error code:

```
[    2.947451] platform 3d6a000.gmu: [drm:a6xx_gmu_acd_probe] *ERROR* Unable to send ACD state to AOSS
[    2.947469] Unable to drop a managed device link reference
[    2.948689] adreno 3d00000.gpu: failed to load adreno gpu
[    2.948786] adreno 3d00000.gpu: probe with driver adreno failed with error -22
```

`-22` is `-EINVAL`, which is exactly the return of the
`if (cmd->enable_by_level && IS_ERR_OR_NULL(gmu->qmp))` branch in
`a6xx_gmu_acd_probe()`. This is the first capture that shows the *numeric* probe
failure, and it closes the loop from source to device.

`/sys/kernel/debug/devices_deferred` lists 8 entries that persist indefinitely
(this is uptime ~99 min, i.e. not a transient state):

```
6800000.remoteproc      platform: wait for supplier /smp2p-adsp/slave-kernel
81d00000.smem           qcom-smem: failed to retrieve hwlock
17d91000.cpufreq        qcom-cpufreq-hw: Failed to find icc paths
aux_bridge.aux_bridge.0 aux_bridge.aux_bridge: failed to acquire drm_bridge
smp2p-adsp              qcom_smp2p: IRQ index 0 not found
smp2p-cdsp              qcom_smp2p: IRQ index 0 not found
smp2p-modem             qcom_smp2p: IRQ index 0 not found
1c00000.pcie            qcom-pcie: cannot initialize host
```

## The deferred-probe burst ran on this boot, at 35.8 s

```
[   35.805388] platform 6800000.remoteproc: deferred probe pending: ...
[   35.806189] platform 81d00000.smem: deferred probe pending: ...
[   35.807203] auxiliary aux_bridge.aux_bridge.0: deferred probe pending: ...
[   35.807740] platform smp2p-adsp: deferred probe pending: ...
[   35.812369] qnoc-sm8550 interconnect-1: sync_state() pending due to 3d00000.gpu
[   35.812827] gcc-sm8550 100000.clock-controller: sync_state() pending due to 3d6a000.gmu
[   35.813298] gpu_cc-sm8550 3d90000.clock-controller: sync_state() pending due to 3d6a000.gmu
[   35.823390] qnoc-sm8550 24100000.interconnect: sync_state() pending due to 3d00000.gpu
```

Anomaly counts for this boot (from `journalctl -b -k`):

| marker | count |
|---|---|
| `deferred probe pending` | 7 |
| `sync_state() pending due to 3d6a000.gmu` | 2 |
| `sync_state() pending due to 3d00000.gpu` | 2 |
| `soft lockup` / `hung task` / `rcu:.*stall` / `workqueue: .*stall` | **0** |
| `rpmh_write_batch` | **0** |

## Why this matters: the burst is NOT at a fixed offset

This boot had **no stall at all**, and its burst is at **35.8 s**, not the
13.3-14.3 s of the four recorded stalls. The GPU failed at 2.95 s here versus
~4.15 s in test-183, so a fixed `GPU-failure + 10 s` rule does not explain either
number.

The mechanism, from `drivers/base/dd.c` and `drivers/base/driver.c`, is that the
timer is **re-armed**:

```c
/* deferred_probe_initcall(), late_initcall */
if (driver_deferred_probe_timeout > 0)
        schedule_delayed_work(&deferred_probe_timeout_work,
                              driver_deferred_probe_timeout * HZ);

/* driver_register(), called for EVERY driver */
deferred_probe_extend_timeout();   /* mod_delayed_work(+10 s), only while pending */
```

So the burst fires **10 s after the last `driver_register()` that found the work
still pending** — it is not "late_initcall + 10 s", and it is not anchored to the
GPU failure. That single correction explains both observations:

* the four recorded stalls at 13.3-14.3 s had their last driver registration
  around 3.3-4.3 s;
* this clean boot had a later registration (or its work was queued later), putting
  the burst at 35.8 s.

**Consequence for the hypothesis.** The burst is a real, deterministic,
whole-system event and it demonstrably ran *without* wedging the machine on this
boot. So the burst alone is **not sufficient** to cause the stall, and profile G
therefore tests something slightly different from what round 2 claimed: it tests
whether *moving* the burst moves the stall, not whether the burst is the sole
cause. The plan has been corrected accordingly.

It also means the search should include **what re-arms the timer last** in a
stalling boot, since that is what pins the burst into the 13-14 s window.
