# Round 10: repeated shutdown cycles, and the post-fix boot record

Two pieces of evidence collected. The series was still running when this was
written; the boot-record finding below is complete.

## 1. The retained boot record on the fixed kernel is 8/8 clean

`/var/log/gts9-boot-evidence/` keeps the newest 8 boots (`KEEP=8`), so it is a
rolling window rather than a complete history. Read in full this round:

| evidence dir | `previous_boot_end` | non-zero markers |
|---|---|---|
| `…-1084b57a` | clean-shutdown | 0 |
| `…-14f0722f` | clean-shutdown | 0 |
| `…-7f8878b7` | clean-shutdown | 0 |
| `…-b69787e2` | clean-shutdown | 0 |
| `…-f83c4b83` | clean-shutdown | 0 |
| `…-1f85d97b` | clean-shutdown | 0 |
| `…-61f93d8e` | clean-shutdown | 0 |
| `…-cd04c0ef` | clean-shutdown | 0 |

**Eight consecutive clean shutdowns with zero stall markers.** The two anomalous
boots examined in rounds 5-7 (`176925b2`, `8d7db274`) have rotated out of the
window, so they cannot be re-read — the archive's own `KEEP=8` limit. Anyone
revisiting them must use the copies quoted in `EVIDENCE-HISTORY.md`.

**What this does and does not support.** It is consistent with the AOSS QMP + IPCC
fix having removed the failure, and 8 clean shutdowns is a meaningful run given
that the failure was previously common enough to appear twice in a similar window.
But it is **not a fix claim**: the failure was intermittent, `KEEP=8` gives no rate
denominator, and the boot records are not all attributable to shutdowns I issued.
The honest statement is that the failure has not recurred in the retained window.

## 2. The six-round shutdown series: 6/6 clean, complete

330 s capture window per round, COM19 held across each whole shutdown→boot cycle
so every round is a complete observation rather than a sample:

| round | panic | soft/hard lockup | hung task | RCU stall | `systemd-shutdown` seen | outcome |
|---|---|---|---|---|---|---|
| 1 | 0 | 0 | 0 | 0 | 13 | completed normally |
| 2 | 0 | 0 | 0 | 0 | 5 | completed normally |
| 3 | 0 | 0 | 0 | 0 | 2 | completed normally |
| 4 | 0 | 0 | 0 | 0 | 3 | completed normally |
| 5 | 0 | 0 | 0 | 0 | 3 | completed normally |
| 6 | 0 | 0 | 0 | 0 | 7 | completed normally |

**6 of 6 clean**, in ~39 minutes. With round 9's two rounds that is **8 observed
shutdown cycles on the fixed kernel with zero failures**, each bracketed by a
capture that held the port across the cycle.

`systemd-shutdown` appearing 2-13 times per round also confirms every one of these
shutdowns *completed* — the exact marker whose absence defines the failure
(round 7).

## Why the series still matters, and what it does not prove

The value of continuing is not that a failure is likely — the evidence has moved
against that — but that a *rate* is what settles the question. "8 of 8 clean"
bounds the failure rate; it does not prove zero, and the failure was intermittent
to begin with. The honest statements available are:

* the failure has not recurred in the 8 retained boot records, and
* it has not recurred in 8 deliberately observed shutdown cycles.

Neither is a fix claim. To make one, the series would need to run long enough that
the absence is statistically meaningful against the pre-fix rate, and the pre-fix
rate is itself unknown (the two archived instances were found by inspection, not
by counting). That is the gap: **no denominator exists for the pre-fix failure
rate**, so no before/after comparison can be computed from the existing record.

## Standing caveat on the observation itself

Issuing a shutdown over COM17 is an intervention. Every figure here is a rate for
*observed* shutdowns, not for shutdowns in general, and must be labelled that way.
