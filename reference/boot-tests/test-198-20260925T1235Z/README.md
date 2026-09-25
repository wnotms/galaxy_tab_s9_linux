# test-198: Profile C wedges identically with the GPU never registered

2026-09-25T12:25–12:40Z, `no-gpu` profile (`msm.skip_gpu=1`), run `c3`. The series
planned 15 rounds and **stopped itself on round 4**.

## This is the result Profile C existed to produce

**The wedge survives with the Adreno driver never registered.** Same canary, same
victim chain, same `SMP: failed to stop secondary CPUs`, on a boot where
`Initialized msm 1.13.0 for 3d00000.gpu` appears **zero** times.

| | baseline (test-197) | Profile C (this) |
|---|---|---|
| `initialized msm … 3d00000.gpu` in the wedged boot | **1** (GPU bound) | **0** (never bound) |
| `adreno` / `a6xx_gmu` / ACD references | present | **0** |
| `soft lockup` | CPU#2 stuck 26 s | **CPU#2 stuck 26 s** |
| victim chain | `toggle_allocation_gate → jump_label_update → kick_all_cpus_sync → smp_call_function_many_cond` | **identical** |
| `SMP: failed to stop secondary CPUs` | 0,3,6-7 | **0,3,6-7** |
| `Kernel panic - not syncing: softlockup: hung tasks` | present | present |

By the pre-registered rule in `docs/NEXT_STALL_DEBUG_PLAN.md` and the brief's
situation 3, **the GPU / GMU / AOSS / ACD direction is decisively downgraded.** The
GPU is not necessary for the wedge.

## The ablation was real, and the gate proves it

Run before any round was trusted (`ABLATION-GATE.txt` in test-196, boot
`8495ed74`): `skip_gpu=Y` under its real name, `no_gpu` absent, `msm.skip_gpu=1`
on the cmdline, the `3d00000.gpu/driver` symlink **absent**, no `adreno` driver
registered, and the display intact — DSI `connected`, 16 display drivers bound.
The wedged boot's own kernel ring confirms it a second time: zero GPU init lines.

## And it carries the markers the two baseline wedges did NOT

This is the first wedge since the old era to carry **all three** of the markers
`STALL_FIRST_EVENT_ORDERING.md` was built on:

```
[   17.651955][  T135] Error sending AMC RPMH requests (-110)                          <- x2
[   18.731453][    C7] [drm:dpu_encoder_frame_done_timeout] enc35 frame done timeout   <- x7, 1.22 s cadence
[   23.271456][    C5] mmc1: Timeout waiting for hardware interrupt.                   <- with SDHCI dump
[   28.307449][    C6] rcu: INFO: rcu_preempt detected stalls on CPUs/tasks:
[   32.803500][    C2] watchdog: BUG: soft lockup - CPU#2 stuck for 26s!
[   32.804151][    C2] Kernel panic - not syncing: softlockup: hung tasks
[   34.920800][    C2] SMP: failed to stop secondary CPUs 0,3,6-7
```

Counted: 7 frame-done events at a 1.220/1.240 s cadence, 2 `AMC RPMH` lines and 1
`mmc1` dump. So `AMC RPMH`, the frame-done flood and `mmc1` are **not**
GPU-dependent either.
Whatever produces them is upstream of the GPU and is still running with the GPU
absent. Onset by the two-timer arithmetic (soft lockup at 32.804 s − 26 s =
**6.80 s**; RCU stall at 28.307 s − 21.02 s = **7.29 s**) lands in the same
~6.5–7.8 s band as both baseline wedges — a third independent record agreeing.

## Round history

| round | verdict | markers | outages |
|---|---|---|---|
| 1 | `clean` | 0 | 1 |
| 2 | `clean` | 0 | 1 |
| 3 | `clean` | 0 | 1 |
| 4 | **`wedge`** | **4** (9 suspect) | **3** |

Three clean rounds then a wedge, exactly as on baseline (test-197: 3 clean then a
wedge). The rate looks similar, which is itself the point — removing the GPU did
not change the failure or its frequency.

## What is now excluded, and what is not

**Excluded as necessary for the wedge:** the Adreno driver, the GMU, the AOSS/ACD
path, the GPU power domains, and the GPU's RPMh and interconnect votes. None of
them registered, and the wedge happened anyway.

**Not excluded, and now the leading candidates**, because they are what the
`AMC RPMH` / `mmc1` / frame-done cluster has in common: the RPMh/RSC path (the
BCM voter's bandwidth vote timing out at 17.65 s is the first abnormal line),
the SD controller, the display commit path, and whatever is common to all three —
power, clocks and the RSC.

**Not established:** which of those is causal. The first abnormal line here is
`AMC RPMH` at 17.65 s, but the onset arithmetic puts the CPU stopping at ~6.8 s,
so the RPMh error is ~11 s *after* the onset, not at it. The marker that is
closest to the onset is still the handled DPU early-return at 4.97 s, which fires
on every boot and therefore discriminates nothing.

## Files

| file | what it is |
|---|---|
| `MANIFEST.txt` | the harness manifest: identity, verdict, markers, all three outage times |
| `on-device-console-ramoops.txt` | the wedged boot's pstore console, 8681 B |
| `on-device-raw.txt` | the same region read again, unprocessed |
| `on-device-pmsg.txt` | the marker as it survived the reboot, proving the binding |
| `round-4.txt` | the per-round record |
| `c-round1..3.txt` | the three clean rounds |
| `klog-4.txt` | the wedged boot's kernel ring — 0 GPU init lines |
| `console-4-watch.txt` | the COM19 capture with all three presence outages |
