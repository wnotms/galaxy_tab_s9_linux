# The strict ordering of the first abnormal event

Round 27. Three complete failure records now exist on this port, all captured from
pstore, and this file tabulates them on the kernel's own clock. It exists because
the round's working instruction is to establish

```
first abnormal event -> first stalled subsystem -> downstream failures -> watchdog recovery
```

rather than to nominate whichever subsystem printed last.

## The three records

| record | where |
|---|---|
| 04:57Z | `reference/boot-tests/test-191-*/wedge-rate-pre-test191-capture/failed-boot-pstore/console-ramoops-0` |
| 06:00Z | `reference/boot-tests/test-191-*/on-device-pstore-20260925T0600/console-ramoops-0` |
| 06:59Z | `reference/boot-tests/test-191-*/wedge-rate-20260925T065728Z/cycle-1-pstore/console-ramoops-0` |

The 06:59Z record is the only one taken on a kernel with the CPU path fixed
(`docs/PROVIDER_FOLLOWUPS.md` §4), so it is also the record that shows the wedge
survives that fix.

## All three records are warm reboots, and that matters for the A/B design

Every one of the three came from a harness-issued `systemctl reboot`, never from a
cold power-on: 04:57Z is cycle 6 of the wedge hunt (`FAILED-BOOT-20260925T0457.md`
says so in as many words), and 06:00Z and 06:59Z are series cycles in the same
way. The stall is therefore reproducible with warm reboots alone.

That is worth stating because the round brief prefers 5-10 **cold** boots per
profile, and a cold boot needs a hand on the power key. Since warm reboots are
what produced all three complete records - and the two panic-reboot restarts in
between - a warm-reboot A/B is a valid reproduction vehicle and not a weaker
substitute for one. `stall-ab.sh` records `reboot_kind=warm` on every round so
the distinction is never blurred, and a panic reboot stays a separate event that
is counted rather than assumed.

## First occurrence and count of every marker

| marker | 04:57Z | 06:00Z | 06:59Z |
|---|---|---|---|
| `encoder is disabled id=35` | 4.436 s (1) | 5.284 s (1) | 4.656 s (1) |
| **`frame done timeout`** | **6.755 s (15)** | **53.671 s (14)** | **7.703 s (1)** |
| `AMC RPMH` | 24.804 s (1) | 61.667 s (2) | 39.654 s (2) |
| `mmc1: Timeout` | 21.987 s (2) | 67.043 s (1) | 23.007 s (6) |
| `rcu detected stall` | 27.727 s (1) | present (1) | 28.647 s (1) |
| `soft lockup` | 32.275 s | 77.124 s | 64.698 s |
| `Kernel panic` | 32.275 s | 77.124 s | 74.757 s |
| `responded to the NMI` | 0 | 0 | 0 |

Consistent in all three, and this is the part worth keeping:

1. `encoder is disabled` fires once, first, at 4.4–5.3 s. **It is not a marker**:
   it fires at 4.798 s on healthy boots too, measured, and `docs/DPU_TRACE.md`
   already calls it "noise, not a timeout".
2. `frame done timeout` is the **first abnormal event** — the earliest line that a
   healthy boot does not print. It precedes `mmc1`, `AMC RPMH`, the RCU stall and
   the panic in every record.
3. `mmc1` and `AMC RPMH` interleave rather than order: 04:57Z has mmc1 first
   (21.99 vs 24.80), 06:00Z has RPMH first (61.67 vs 67.04). Two subsystems
   failing inside the same few seconds.
4. RCU stall, then soft lockup, then panic. The victim chain
   (`jump_label_update -> kick_all_cpus_sync -> smp_call_function_many_cond`) is
   identical in all three.

## The control, which did not exist before this round

`wedge-rate.sh` now counts these markers on every cycle it completes, so the
association has a denominator instead of being read off failures alone. Over the
8 completed cycles of the rate2 series, every one of them clean:

| marker | total over 8 clean cycles |
|---|---|
| `frame done timeout` | **0** |
| `mmc1: Timeout` | **0** |
| `AMC RPMH` | **0** |
| `rcu detected stall` | **0** |
| `encoder is disabled` | **8** — once per boot, on every healthy boot |

The rate3 series added 14 more cycles, all clean, with the same result:

| marker | over 22 clean cycles (rate2 8 + rate3 14) |
|---|---|
| `frame done timeout` | **0** |
| `mmc1: Timeout` | **0** |
| `AMC RPMH` | **0** |
| `rcu detected stall` | **0** |
| `encoder is disabled` | **22** — exactly one per boot, on every healthy boot |

So `frame done timeout`, `mmc1: Timeout` and `AMC RPMH` are present in 3 of 3
failure records and absent from 22 of 22 clean controls. As a 2x2 table that is
`[[3,0],[0,22]]`, two-sided Fisher exact **p = 0.00043**. It is the strongest
association this project has had for any marker by a wide margin, and it is
still not causality - for the reason in the next section.

## What this does not say, and the counterexample is already on record

`docs/STALL_FAILURE_SHAPE.md` §6 established the frame-done association before
this round, and it also recorded the fact that forbids the obvious conclusion:
**test-184's A-5 failure died unasked without ever printing the message.** So the
frame-done timeout is not necessary for the failure class. Adding three records to
the "yes" column does not change that.

The honest statement, therefore:

* `frame done timeout` is the earliest **observable** event in every record that
  has one, and it is a real marker of the mid-run episode.
* It is **not** established as the cause, and the two candidate readings are still
  open:
  * **A** — the display commit path is the trigger, and everything after it is
    consequence;
  * **B** — an invisible upstream failure (clocks, power domains, RPMh/RSC
    completion) hits first, and the display is simply the **first subsystem to
    notice**, because a frame has a 1.184 s deadline and it polls. On reading B the
    frame-done timeout is a victim with a short fuse, not a cause.

`AMC RPMH` at `-110` (`ETIMEDOUT`) is what tips the balance toward reading B: an
RPMh write that times out is not downstream of a missed display frame. But the
evidence does not settle it, and both readings predict the same A/B results for
profiles A/B/C, which is why those run first.

## Why the ordering matters for the round's experiment matrix

The goal of the matrix is to remove a subsystem and see whether the stall
survives. This table says what a *removal* has to explain:

* Profile C (`msm.skip_gpu=1`) removes Adreno, GMU, ACD/AOSS and the GPU's RPMh and
  interconnect votes. It does **not** remove the display or the SD controller, so
  if the stall survives C, reading A is dead and reading B survives.
* Profile B (`msm.disable_acd=1`) removes only the ACD table and its AOSS
  notification — and it is a *real* removal: upstream `sm8550.dtsi` gives all
  eight GPU OPP nodes a `qcom,opp-acd-level`, the X710 DTS does not strip them, and
  `c300000.power-management` is bound to `qcom_aoss_qmp` on the device. So
  `cmd->enable_by_level != 0` and the AOSS notification genuinely happens today.
* Neither B nor C removes the display or `mmc1`. Given the ordering above, a
  pair of clean results from B and C would not by itself exonerate the display —
  it would only move the question to what the DPU and the SD controller have in
  common, which is power, clocks and RPMh.

## Provenance of the control counts, including a defect in the collector

The 22 clean cycles were counted by `probe_markers`, which reads the whole dmesg
at the end of each cycle - after that cycle's outcome is already decided, so the
instrument cannot influence what it measures. The counts are unaffected by the
attribution defect fixed in the same round (`CONSOLE_STATE` being set inside a
command substitution and therefore never reaching the parent shell), because that
bug touched only how a silent cycle is *labelled*, not what the marker probe
counts. The distinction is worth keeping: a clean cycle's marker row is valid
evidence even from the series whose attribution was wrong.

## Corrected inputs to this analysis

Two defects that would have corrupted the matrix were found and fixed this round;
both are recorded in `docs/GPU_GMU_RPMH_STALL_PLAN.md` §1.1 (facts 15 and 19):

* Profile C's token did not exist. It was `msm.no_gpu=1`; the registered parameter
  is `msm.skip_gpu=1` (`MODULE_PARM_DESC` only attaches a label). The kernel would
  have ignored it, and profile C would have been **indistinguishable from
  baseline** — a false negative for the entire GPU direction. `stall-ab.sh` now
  refuses to run a profile whose `msm.*` tokens are not registered parameters.
* The harness's `gmu_bound` and `aoss_bound` metrics could not be anything but 0:
  `3d6a000.gmu` has no platform driver to bind by design (`a6xx_gmu_init()` takes
  it with `of_find_device_by_node()`), and the AOSS path used `@` where sysfs uses
  `.`. Both now report driver *names*.


---

# Round 30: the onset is ~6.5-7.8 s, and the marker table does not survive

Two further wedges were captured with a working two-channel instrument, and they
contradict the central table above. Both changes are corrections, not additions.

## The three markers this file is built on are absent from both new records

In the pstore console of **both** new wedges:

| marker | test-195 | test-197 |
|---|---|---|
| `frame done timeout` | **0** | **0** |
| `mmc1: Timeout` | **0** | **0** |
| `AMC RPMH` | **0** | **0** |
| `encoder is disabled` | 1 @4.787 s | 1 @4.615 s |
| `rcu detected stall` | 1 @28.839 s | 1 @28.763 s |
| `Sending NMI` | @28.844 s | — |
| `soft lockup` | @33.127 s | @32.546 s |
| `Kernel panic` | @33.127 s | @32.546 s |

The "present in 3 of 3 failure records, absent from 22 of 22 clean controls"
association above was built from the three earlier pstore records, which were
captured on a kernel that also lacked `epss_l3` and the cxpd fix. On the kernel now
flashed, neither wedge carries any of the three. The association does not
generalise from that era to this one.

## The onset, from two independent timers

`CONFIG_SOFTLOCKUP_DETECTOR` reports a stuck duration, and
`CONFIG_RCU_CPU_STALL_TIMEOUT=21` with `CONFIG_HZ=250` gives `t=5255 jiffies` =
21.02 s - both read out of `out/kernel-gts9wifi/config`, not assumed. Subtracting
each from its report time:

| record | soft lockup | minus 26 s | RCU stall | minus 21.02 s | victim |
|---|---|---|---|---|---|
| test-195 | 33.127 s | **7.13 s** | 28.839 s | **7.82 s** | CPU 5 |
| test-197 | 32.546 s | **6.55 s** | 28.763 s | **7.74 s** | CPU 2 |

**Both point at ~6.5-7.8 s.** The two records agree to ~1.2 s across different
victim CPUs (5 and 2) and different kworkers (`u32:7`, `u32:8`). The RCU stall at
~28.8 s is therefore **21 s of silence after the onset**, not the onset, and the
`soft lockup`/panic at ~33 s is 26 s after it.

That is earlier than every marker this file treats as "first":

* `frame done timeout` in the older records: 6.7-7.7 s - comparable, and now known
  not to be necessary;
* the DPU `encoder is disabled`: 4.4-4.8 s, and it fires on every healthy boot.

**And it retires the 13.0-14.3 s window as an onset.** That window is where a
*different* detector - the deferred-probe timeout, or an RPMh timeout - happened
to fire, not where the failure began.

## What survives from above

* the strict ordering *within* a record - RCU stall before soft lockup before
  panic - holds in both new records;
* the victim chain is identical in all four:
  `toggle_allocation_gate -> static_key_enable -> jump_label_update ->
  arch_jump_label_transform_apply -> kick_all_cpus_sync ->
  smp_call_function_many_cond`, with `SMP: failed to stop secondary CPUs`;
* `encoder is disabled` is still noise, now confirmed on two more boots;
* `toggle_allocation_gate` is still the canary, not the cause: it needs every CPU
  to ACK an IPI, so it reports the wedge.

## What is still not known

The onset is bracketed to ~1.3 s by two timers, but **nothing is logged there**.
In test-197's kernel ring, the window 4.6 s → 29 s contains exactly two messages,
both userspace stage markers (`GTS9_DEBIAN_STAGE=tty1-getty-active` at 6.52 s and
`=multi-user` at 6.88 s), and a clean round's window is equally quiet. So the
contents of the window do not discriminate - only the fact that a CPU stops
ACKing IPIs inside it does.

Why that CPU stops is the open question, and the answer is not in any channel the
project currently records at `loglevel=4`.
