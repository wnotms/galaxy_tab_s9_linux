# Shutdown series result: 16 observed cycles, zero failures

> **Correction (round 16): one of the 16 cycles contained a failure.**
> Re-scoring every raw capture with `test-188/classify-captures.py` shows that
> round 1 of the 8-round series had **two** resets in its watch session, not one.
> After the round's own reboot, boot `7f02df57` reached `graphical.target`
> normally, printed one `[drm:dpu_encoder_frame_done_timeout] enc35 frame done
> timeout` 0.9 s later, then went silent for **36.8 s with the port still open**
> and was reset by something nothing had asked for. The series never noticed,
> because `shutdown-capture.sh` scores a round from banners and this failure emits
> none — the same blind spot that hid the A-5 failure for five rounds.
>
> The tally below is therefore correct about what each round *checked* and wrong
> as a statement that nothing failed. The honest count is **15 clean cycles, plus
> one cycle that contained an unattended reset**, and that reset is the first
> failure observed on the post-fix kernel. See `docs/STALL_FAILURE_SHAPE.md` §6.
> Rounds 2–8 each show exactly one reset, their own; the check is now automatic.

Consolidated from every shutdown cycle run on the post-fix kernel. Each cycle was
issued with `systemctl reboot` over COM17 while a COM19 capture held the port across
the whole shutdown→boot transition, so each is a complete observation rather than a
sample.

## The tally

| series | date/round | cycles | clean | stalled | file |
|---|---|---|---|---|---|
| initial | round 9 | 2 | 2 | 0 | `shutdown-*-verdict.txt` |
| 6-round | round 10 | 6 | 6 | 0 | `shutdown-series-6round.txt` |
| 8-round | round 11 | 8 | 8 | 0 | `shutdown-series-8round.txt` |
| **total** | | **16** | **16** | **0** | |

Every cycle in the 8-round series reported `panic_lines=0`, `softlockup_lines=0`,
`hardlockup_lines=0`, `hungtask_lines=0`, `rcu_lines=0`, `calltrace_lines=0`, and a
non-zero `systemd_shutdown_seen` — meaning each shutdown **completed**, which is
precisely the marker whose absence defines the failure found in round 7.

## What the number means, and what it does not

**Supports:** the failure has not recurred in 16 consecutive observed shutdown
cycles, on a kernel where the opportunity for it was present every time — round 11
showed each of the 8 retained boots reaching the 13-14 s deferred-probe burst with
the full `sync_state` load and surviving it.

**Does not support a fix claim**, for a reason independent of sample size: **there is
no pre-fix rate.** The two archived failures (`176925b2`, `8d7db274`) were found by
inspecting an archive, not by counting attempts, so "16 clean" cannot be compared
against anything. A rate comparison would need "N of M failed before, 0 of 16 after"
and the first half of that does not exist.

The strongest statement the data supports is:

> On the post-fix kernel, 16 consecutive observed shutdown cycles completed with no
> panic, no lockup and no stall marker, and 8 consecutive boots reached and passed
> the 13-14 s window in which the pre-fix failures occurred.

## The confound that must be stated

Every one of these cycles was a **warm reboot issued over the console**. That is an
intervention, and it also means:

* these are warm reboots, not cold boots — no cold-boot claim is made anywhere;
* a failure that requires a cold-boot state would not appear here;
* the pre-fix failures were observed across a mix of boot types, so the two sets are
  not perfectly comparable even if a pre-fix rate existed.

## Where this leaves the investigation

The AOSS QMP + IPCC fix removed the only measured difference between surviving boots
and the archived failures (round 11: the failures carried the ACD error, the
`device_link_put_kref` warning and `probe with driver adreno failed with error -22`;
no surviving boot has any of them). Sixteen clean cycles plus eight clean boot
records are consistent with that having removed the failure.

To close it properly would require one of:

1. a **cold-boot** series on the current kernel, since the existing series is warm
   only; or
2. recovering a pre-fix rate by re-flashing a pre-fix kernel and running the same
   series — which is a deliberate regression test and needs its own authorisation,
   because it would put a known-failing kernel back on the device; or
3. accepting the current evidence as sufficient and recording the residual risk
   explicitly, which is what this document does.
