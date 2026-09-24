# test-187 stall series — attempt log and current disposition

The post-fix stall series did **not** produce usable data. Recording why, because
an empty round looks identical to a clean round in a summary table, and that
failure mode has now bitten this round twice.

## What was verified before the series

Profile A on the IPCC-fixed kernel (`boot.img 12f65577e9731d98…`), read-only
probes:

| probe | result |
|---|---|
| `readlink -f …/3d00000.gpu/driver` | `/sys/bus/platform/drivers/adreno` — **GPU bound** |
| `Unable to send ACD state to AOSS` | 0 |
| `Unable to drop a managed device link reference` | 0 |
| `failed to acquire ipc mailbox` | 0 |
| `soft lockup` / `rcu stall` / `rpmh_write_batch` | 0 / 0 / 0 |
| `deferred probe pending` burst | 7 entries |

Boots observed clean on the fixed kernel: **6** (the flash reboot, the three warm
reboots of the first attempt, and two probes). None of them stalled. That bounds
the rate; it is not a fix claim.

## Attempt 1 — poisoned by port contention (no data)

`warm-rounds.sh` issued all five warm reboots, but every probe logged
`could not open COM17` because a leftover `console-watch.ps1` from an earlier step
still held the port. All five round files were written with the probe fields
missing. **Discarded**, and the runner was replaced.

## Attempt 2 — rebooted twice, then the device went unresponsive

| time (UTC) | event |
|---|---|
| 18:31 | preflight ok, device up, GPU bound |
| 18:37 | rounds 1 and 2 issued; probes failed on a busy port again |
| 18:40–18:42 | COM17/COM19 briefly enumerated twice (duplicates), USB gadget count 3 → 0 → 3 |
| 18:43+ | no shell on COM17 (opens but never answers); `adb` reports no device; Windows still lists COM17/COM19 |

So the device rebooted on its own at least once during the series, and the USB
gadget is now flapping or gone. **This is not yet interpreted**: it could be the
stall itself (the thing under investigation), an unrelated boot problem, or a
consequence of the interrupted series. Deciding between those requires the
device's own journal from the affected boot, which needs a working console.

## Attempt 3 — false "clean" rounds again, and the fix

A third attempt used the evidence-driven runner. Round 1 was written as
`status=ok / verdict=clean` while its probe and evidence files contained **44
bytes each** — just the "console open" line, no measurements at all. `console`
had returned success because it *opened the port*; that says nothing about
whether a reply was captured.

This is the same defect as attempts 1 and 2 in a new disguise: "no data" being
recorded as a result. The runner's check was on the wrong thing (did the port
open) instead of the right thing (did we get numbers back).

The rounds loop now gates every round on the captured metrics themselves:

```sh
bid=$(sed -n 's/^BID=//p' "$DIR/metrics-$i.txt" | head -1)
gpu=$(sed -n 's/^GPU=//p' "$DIR/metrics-$i.txt" | head -1)
if [ -z "$bid" ] || [ -z "$gpu" ]; then
        ... status=no-data ... break
fi
```

and a round whose evidence verdict is missing is `verdict=unknown-evidence-missing`
rather than `clean`. A round can no longer be classified from nothing.

The device hung again during this attempt (same symptom as attempt 2: ports
enumerate, nothing transmits, adb sees no device), so no usable round was
produced. The series is still outstanding.

## What the next attempt must do differently

1. **Kill every leftover console holder before starting**, and verify the port is
   free by actually opening it — not by assuming the previous step released it.
   Two separate steps in this round silently held COM17.
2. **Never record an empty round.** If the probe cannot run, that round is
   `status=no-data`, and the series must stop rather than continue, because a
   series of empty rounds reads like a series of clean ones.
3. **Distinguish a spontaneous reboot from an issued one.** The device rebooted
   at ~18:40 without being asked. The runner should record `systemctl reboot`
   count vs observed `boot_id` changes and flag any change it did not cause —
   that is potentially the strongest evidence available and it was nearly lost.
4. **A cold boot still needs the operator.** Every round in these attempts was a
   warm reboot; no cold-boot claim is made anywhere.

## Current disposition

The tablet is not reachable over USB or the console. A physical power cycle is
the recovery step. The flashed pair is unchanged and is the post-fix profile A
(`boot 12f65577e9731d98…` + `vendor_boot 06902f993f6fe9b6…`), with the pre-test
pair backed up at
`/home/ms/Samsung/gts9-flash-tests/test-187-baseline/` and restorable via
`rollback.sh`.
