# Round 11: every post-fix boot survives the 13-14 s burst

The single most useful comparison available, and it does not need a new reboot.

## The measurement

For each of the 8 retained boots, the previous boot's kernel log was read to find
how long that boot actually lived and how much `sync_state` activity it contained:

| evidence dir | `prev-kernel.log` lines | last monotonic timestamp | `sync_state() pending` count |
|---|---|---|---|
| `…-1084b57a` | 996 | **89.99 s** | 31 |
| `…-14f0722f` | 1003 | **90.51 s** | 31 |
| `…-7f8878b7` | 1001 | **45.21 s** | 31 |
| `…-b69787e2` | 954 | **659.61 s** | 29 |
| `…-1f85d97b` | 950 | **2615.21 s** (43.6 min) | 29 |
| `…-61f93d8e` | 950 | **709.80 s** | 29 |
| `…-994ad160` | 952 | **378.88 s** | 29 |
| `…-cd04c0ef` | 942 | **377.84 s** | 29 |

**Every one of these boots lived well past the 13-14 s window** — the shortest ran
to 45.2 s, the longest to 43.6 minutes — and every one carried the full
`sync_state` machinery (29-31 pending lines per boot). None stalled.

## What this rules out

The 13-14 s window **does not stop being reached** after the fix. Measured on the
current boot:

```
[   14.304464] platform 6800000.remoteproc: deferred probe pending: ...
[   14.306552] gcc-sm8550 100000.clock-controller: sync_state() pending due to 3d6a000.gmu
[   14.306668] gpu_cc-sm8550 3d90000.clock-controller: sync_state() pending due to 3d6a000.gmu
```

with 29 `sync_state() pending` lines total — the same order as the pre-fix boot
`8d7db274` had. The burst still happens, at the same ~14.3 s, still naming the GMU.

So:

* **The deferred-probe burst is not the differentiator.** It occurs, with the same
  shape and timing, on boots that survive and on boots that failed. Any hypothesis
  of the form "the burst itself wedges the machine" is now contradicted by 8 boots
  that reached and passed it.
* **The `sync_state` blockage is not the differentiator either.** `gcc`/`gpucc` still
  cannot complete `sync_state()` because `gmu@3d6a000` has no driver in this tree
  (round 4) — that is unchanged by the AOSS QMP + IPCC fix, and it is present on
  every surviving boot.
* What *is* different between the surviving boots and the archived failures is the
  GPU chain: the failures carried `Unable to send ACD state to AOSS`, the
  `Unable to drop a managed device link reference` warning, and
  `probe with driver adreno failed with error -22`. None of the 8 surviving boots
  has any of those. The current boot shows instead:

  ```
  [    2.134287] [drm] Initialized msm 1.13.0 for 3d00000.gpu on minor 0
  ```

  i.e. the GPU driver initialised successfully.

## The honest conclusion

The comparison supports the AOSS QMP + IPCC fix having removed the failure, and it
does so more strongly than a bare "N clean cycles" count, because it establishes
that the **opportunity** for failure — reaching the burst window with the full
`sync_state` load — was present on every surviving boot and did not produce one.

It is still not a proof, for a reason that is independent of sample size: the two
archived failures were found by inspection rather than by counting attempts, so
there is no pre-fix rate to compare against. The statement this data supports is
"the window is reached on every boot and no longer wedges", not "the failure is
eliminated".

## Correction to the round-2 hypothesis

`docs/GPU_GMU_RPMH_STALL_PLAN.md` §4.2-4.3 proposed the deferred-probe burst as the
prime suspect for the 13-14 s stalls. This round's data contradicts that as a
*sufficient* mechanism, and the plan should be read with that amendment: the burst
coincides with the window and the GPU defect was on the path into it, but the burst
demonstrably runs to completion on healthy boots.
