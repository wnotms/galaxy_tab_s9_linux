# test-199: the RPMh debug run — a wedge, and no RPMh output at all

Flashed 2026-09-25T13:14Z (`vendor_boot` only, one token from baseline). The run
planned 12 rounds and **stopped itself on round 9** with `verdict=wedge`.

## The switch was proven live before any round was trusted

This is the run's whole premise, and it was established rather than assumed.
`0021` prints **only** when a timeout happens and exposes no sysfs or debugfs
handle, so a round with no dump is otherwise indistinguishable from a kernel that
has no such switch.

| check | result |
|---|---|
| `gts9_rpmh_debug=1` on `/proc/cmdline` | **1** |
| A/B tokens present (`msm.skip_gpu`, `msm.disable_acd`, `deferred_probe_timeout`, `cpuidle.off`) | **0 — it ran alone** |
| `gts9_rpmh_debug` in the kernel's `Unknown kernel command line parameters` list | **absent** → an `early_param` handler consumed it, so the code is present and armed |
| `gpu_driver` | `adreno` — a diagnostic, **not** an ablation |
| all 14 dump strings are `pr_err` (`KERN_ERR`) | always in the ring, so absence cannot be a loglevel artefact |

The harness reports this itself now: `preflight: gts9_rpmh_debug is consumed by a
kernel handler`. Transcript in `ARMING-GATE.txt`.

## The result: the pre-registered last row

`wedge_markers=7`, `presence_outages=2`, and **zero** RPMh output in every channel
— pstore console, kernel ring, and pmsg all `gts9-rpmh:` count **0**. The three
older markers (`AMC RPMH`, `frame done timeout`, `mmc1 Timeout`) are **0** here too.

The decision rule's last row, written before the run:

> *no RPMh output at all, and the stall still happened* → **the stall did not go
> through an RPMh timeout**; the RPMh direction is downgraded for that failure
> mode.

The `rpmh` hits in the ring are only the cmdline echo and three benign
`qcom-rpmhpd … sync_state() pending` lines at 15.09 s — no timeout, no dump. There
is no `bcm` or `voter` reference at all.

**And the victim's stack contains no RPMh path.** The interrupted CPU was in the
`toggle_allocation_gate → static_key_enable → arch_jump_label_transform_apply →
kick_all_cpus_sync → smp_call_function_many_cond` canary, with no rsc, rpmh, bcm or
interconnect frame anywhere in the trace.

So the `rpmh_write_batch()` lifetime hazard is **not** the mechanism of this wedge.
That does not falsify patch `0021`'s hazard — it never fired, so it was never
tested — but it removes the RPMh timeout branch as the explanation for the failure
mode seen in this run.

## The wedge itself, and a new wrinkle

| | test-195 | test-197 | test-198 | **test-199** |
|---|---|---|---|---|
| profile | baseline | baseline | no-gpu | rpmh-debug |
| victim CPU | 5 | 2 | 2 | **4** |
| soft lockup | 33.127 s (26 s) | 32.546 s (26 s) | 32.804 s (26 s) | **64.755 s (56 s)** |
| RCU stall | 28.839 s | 28.763 s | 28.307 s | 28.599 s |
| panic | 33.127 s | 32.546 s | 32.804 s | **74.807 s** |
| `SMP: failed to stop` | 6-7 | 0,3,6-7 | 0,3,6-7 | **3,5** |
| dump captured | — | — | — | **none** |

The **56 s** stuck duration is new: the detector reported on its *second* firing,
not its first, so this CPU was stuck ~30 s longer before anyone said so. That is
consistent with the light configuration of `watchdog_thresh` rather than a
different failure, but it is the first record where the soft-lockup line is late
enough that onset arithmetic has to allow for it.

Onset by both timers: soft lockup 64.755 − 56 = **8.75 s**; RCU stall
28.599 − 21.02 = **7.58 s**. The RCU figure matches all three previous wedges
(7.13 / 7.74 / 7.29 / 7.58 s), which is the more reliable of the two here.

## Rate

Nine rounds, one wedge — with rounds 1-8 `clean` and `presence_outages=1` each.
That is the fourth wedge in the session, and the first with the instrument that
was supposed to explain it.

## What this changes

* **The RPMh-timeout branch is out** for this failure mode, by the rule written
  before the run.
* **The `toggle_allocation_gate` canary is confirmed as the reporter, not the
  cause** — fourth record, and here it is the *entire* trace, with no RPMh frame
  anywhere near it.
* **The remaining cluster is unchanged:** `AMC RPMH`, the frame-done flood and
  `mmc1` appeared together in test-198, are absent here, and the wedge happened
  either way. So they are correlates of *some* wedges, not necessary conditions of
  any — which is the same conclusion test-197/198 forced about the old marker
  table, now from the other direction.

## Open, and not answered by this run

* **Why no dump if the timeout path is reachable?** The dump sits on the
  `rpmh_write_batch()` timeout path immediately after `WARN_ON(1)`, and its 14
  strings are all `KERN_ERR`. Nothing reached it, and no caller was found sitting
  in RPMh code. But the run cannot exclude that the *voter* abstained before
  calling rather than timing out inside — the 10 s timeout never expired.
* **Nothing here identifies the cause.** Four wedges, four victim CPUs, one
  repeated canary. The onset is consistently ~7-8 s by the RCU timer, and what
  stops a CPU there is still unobserved.

## Files

| file | what it is |
|---|---|
| `ARMING-GATE.txt` | the pre-run proof that the switch is live, single-variable and not an ablation |
| `wedge-round9/` | round 9's preserved evidence: manifest, 4051 B pstore, kernel ring, both watch channels |
| `rpmh-round1..3.txt` | three of the eight clean rounds, for contrast |
