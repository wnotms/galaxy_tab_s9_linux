# The HWSPINLOCK_QCOM fix works on hardware: 8 → 3 deferred, all four failures gone

Flashed `boot.img bf6a02bbe19e9561…` (the hwspinlock build) and verified on the
device. Every failure the fix targeted is gone.

## Before and after, measured on the device

| check | before | after |
|---|---|---|
| `81d00000.smem` bound | ✗ (deferred, "failed to retrieve hwlock") | ✓ `/sys/bus/platform/drivers/qcom-smem` |
| `1f40000.hwlock` (TCSR mutex) bound | ✗ (no driver) | ✓ `/sys/bus/platform/drivers/qcom_hwspinlock` |
| `smp2p-adsp` / `-cdsp` / `-modem` | ✗ "unable to allocate local smp2p item" | ✓ all three bound |
| `6800000.remoteproc` (ADSP) | ✗ "wait for supplier /smp2p-adsp/slave-kernel" | ✓ `/sys/bus/platform/drivers/qcom_q6v5_pas` |
| `3d00000.gpu` | ✓ adreno | ✓ adreno |
| **deferred list length** | **8** | **3** |

Current deferred list, reduced from 8 entries to 3:

```
17d91000.cpufreq.qcom-cpufreq-hw: Failed to find icc paths
aux_bridge.aux_bridge.0.aux_bridge.aux_bridge: failed to acquire drm_bridge
1c00000.pcie.qcom-pcie: cannot initialize host
```

So this was the **fourth** provider defect of the same shape as the AOSS QMP, IPCC and
their predecessors: a node present in the device tree, its provider driver missing from
the config, and a whole chain of consumers deferred permanently behind it. The chain
here was SMEM → smp2p ×3 → ADSP remoteproc.

## What appeared afterwards, and it is NOT caused by the fix

The boot after the flash shows 10 `arm-smmu 15000000.iommu: Unhandled context fault`
messages, all with the same signature:

```
fsr=0x402 [Format=2 TF], iova=0xb87b1200, fsynr=0x630021, cbfrsynra=0x1c00, cb=9
FSYNR0 = 00630021 [S1CBNDX=99 PNU PLVL=1]
```

and immediately after them:

```
[    0.399111] remoteproc remoteproc0: adsp is available
[    0.399161] [     T63] remoteproc remoteproc0: request_firmware failed: -2
```

**`-2` is `-ENOENT`: the ADSP firmware is not present on the root filesystem.** These
faults are the ADSP's memory traffic being translated by a context bank that
`request_firmware` failure left unprogrammed — a *consequence of missing firmware*, not
of the hwspinlock change. Two reasons to be confident it is not the fix's doing:

* the fix only makes drivers **bind**; it does not start any remoteproc or change any
  IOMMU mapping;
* the ADSP remoteproc previously never got far enough to be "available" at all — it was
  stuck behind `/smp2p-adsp/slave-kernel`. The fix is what allowed it to reach the
  firmware request and fail there.

The honest reading: the fix exposed a pre-existing gap (missing ADSP firmware) that was
previously hidden behind the deferred chain. Whether those faults are harmless or need
attention is **not determined here**, and ADSP/audio bring-up is explicitly out of scope
for this round.

## Also observed on that boot, unexplained

The panel showed a long pause on this screen before clearing to the login prompt, with:

```
[    1.138149] msm_dpu ae01000.display-controller: no GPU device was found
[    1.17...] systemd-shutdown-generator: Failed to find module 'autofs4'
[    1.24...] qcom_sysmon ...: Cannot assign requested address
```

`msm_dpu … no GPU device was found` at 1.14 s is notable because the GPU *does* bind
(confirmed `adreno` afterwards) — so the DPU's probe ran before the GPU was available
and the message is about probe ordering, not about a missing GPU. It is recorded here
rather than analysed; it was not present in the earlier boots' captured logs, which may
mean it is new, or may mean it was simply not captured before.

## Standing conclusions unchanged

This fix does not change the stall assessment. The stall was localised to the shutdown
path, the AOSS QMP + IPCC fix removed the only measured difference between failing and
surviving boots, and this provider fix removes four more permanently-deferred devices —
none of which was implicated in the stall.
