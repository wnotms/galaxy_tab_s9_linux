# The decision rule for the test-191 wedge rate

**This file was written while the series was still running, before any cycle had
produced a verdict.** That ordering is the point: a threshold chosen after seeing
the count is not a threshold. Nothing below is adjusted afterwards — if the result
disagrees with the rule, the rule stands and the disagreement is written down.

## The two baselines, and the honest one to test against

| era | boots | wedges | rate | CI |
|---|---|---|---|---|
| pre-fix (ACD error present, GPU never binds) | 46 | 10 | 21.7% | 12.3–35.6% |
| post-fix ACD only (GPU binds, **no cpufreq**) | 29 | 1 | 3.4% | 0.6–17.2% |

(`docs/CPU_WEDGE_EVIDENCE.md`, "The rate".)

The tempting comparison is against the pre-fix 21.7% — it was the number quoted in
`wedge-rate.sh`'s own banner. It is also the **easy** one, and passing it proves
less than it looks: 21.7% was measured on a kernel that had neither the ACD fix nor
any cpufreq driver. The ACD fix alone already moved the rate to 3.4%, so any run
that reproduces 3.4% would clear 21.7% while having demonstrated nothing about
`CONFIG_INTERCONNECT_QCOM_OSM_L3`.

**The primary test is therefore against 3.4%**, the rate measured on the kernel
immediately preceding this one. That is the rate at which the tablet still wedged
*with the GPU working and the CPU path still broken*, which is exactly the state
test-191 changes. Beating 21.7% is reported as a secondary, weaker statement.

## The rule

`k` = cycles carrying the failure signature, out of `n` completed cycles. The
signature is the project's established one — a second USB-presence outage inside
the boot, meaning something other than the harness restarted a boot the harness
had already started, or an unanswered-NMI line. A cycle that produced **neither a
clean verdict nor a wedge** — an `unattributed` cycle — is not counted in either
direction and does not advance `n`.

| observation | conclusion |
|---|---|
| any `n` ≥ 1, `k` ≥ 1 with a stack trace captured | **the wedge survives the fix.** Stop, keep the capture, and treat the CPU-path hypothesis as incomplete rather than confirmed |
| `n` = 40, `k` ≤ 3 | the fix beats 3.4% (P = 0.016 under 3.4%). Report as **positive**, and continue to 60 |
| `n` = 60, `k` = 0 | P = 0.126 under 3.4%. **Not** a demonstration that the rate is zero — only that it is below 3.4% at this sample size |
| `n` = 60, `k` = 1 | P = 0.391. **No conclusion.** The run is compatible with the pre-test-191 rate and must be reported as such |
| `n` = 85, `k` = 0 | P = 0.053 under 3.4%. The strongest statement this design can make; separating 0% from 3.4% properly needs more boots than the tablet can be asked for in one sitting |

The pre-computed numbers, so the arithmetic is not done after the fact:

```
n=40  vs 21.7%  expected= 8.68   P(k<=0)=0.0001  P(k<=1)=0.0007  P(k<=2)=0.0041  P(k<=3)=0.0159
      vs  3.4%  expected= 1.36   P(k<=0)=0.2507  P(k<=1)=0.6036  P(k<=2)=0.8458  P(k<=3)=0.9537
n=60  vs 21.7%  expected=13.02   P(k<=0)=0.0000  P(k<=1)=0.0000  P(k<=2)=0.0001  P(k<=3)=0.0004
      vs  3.4%  expected= 2.04   P(k<=0)=0.1255  P(k<=1)=0.3905  P(k<=2)=0.6657  P(k<=3)=0.8529
n=85  vs  3.4%  expected= 2.89   P(k<=0)=0.0529  P(k<=1)=0.2110  P(k<=2)=0.4447  P(k<=3)=0.6723
```

## Why the rule stops at "below", not "gone"

`n = 60, k = 0` leaves a 12.6% chance of seeing zero wedges even if the true rate is
still 3.4%. That is not a small number, and calling it a cure would be the same
mistake this project has already made once — the post-fix ACD era was announced at
1 of 29 and then produced two more wedges in the very next session
(`reference/boot-tests/test-191-*/wedge-rate-pre-test191-capture/FAILED-BOOT-20260925T0457.md`).

Two further limits belong in the record rather than in a footnote:

* **The wedge onset is not fixed.** The two complete failure records at 04:57Z and
  06:0xZ struck at 6.8 s and ~52.5 s. The "13–14 second window" is one instance,
  not a law, so a rate series that ends its cycles early is relying on an
  assumption that the evidence already contradicts. `wedge-rate.sh` keeps the full
  window whenever anything looks wrong, and the second-outage check runs
  continuously through the early-exit wait for this reason.
* **These are warm reboots.** Every cycle is `systemctl reboot`, never a cold
  power-on. A defect that needs a cold start would not appear here at all, and
  that limitation does not get smaller with more cycles.

## What would falsify the CPU-path explanation

Stated before the result, so it cannot be quietly dropped:

1. **A wedge with `policies=3`.** If a cycle wedges while cpufreq is bound and
   governing — the per-cycle verdict records `policies` — then the missing
   `epss_l3` provider was not the mechanism, and the correlation with the ACD era
   was.
2. **A rate statistically indistinguishable from 3.4%.** That would mean the CPU
   path is not what the ACD fix moved, and `docs/PROVIDER_FOLLOWUPS.md` §4 is
   wrong about which provider matters.
3. **A wedge on a second, independent unit** (the X910 port) at the same rate with
   the same fix. Not testable this round; recorded because it is the check that
   would settle this properly.

## Related

* `docs/CPU_WEDGE_EVIDENCE.md` — the signature, the 11 boots, the confounds
* `docs/PROVIDER_FOLLOWUPS.md` §4 — the `epss_l3` root cause
* `reference/boot-tests/test-191-20260925T0410Z/on-device/RESULT.md` — the fix
  verified on hardware
