# test-197: a second real wedge, and the onset both wedges agree on

Run 2026-09-25T10:52–11:07Z, `baseline` profile with the fixed harness. **Nothing
was flashed.** The series ran 10 rounds and **stopped itself on round 4** with
`verdict=wedge`.

## The detector worked, on its own, for the first time

Round 4 produced, from the USB presence trace:

```
presence_outages=2
automatic_reboot=yes
second_outage_gone=2026-09-25T11:04:20.722Z
second_outage_back=2026-09-25T11:04:40.283Z
```

One outage is the harness's own reboot; the second is the panic's restart, which
nothing the harness did can explain. Rounds 1-3 reported `presence_outages=1`,
`automatic_reboot=no`, `verdict=clean`.

This is the signal that was silently dead until the `klog-watch` typo was fixed
earlier in this round, and it is the reason this wedge was caught automatically
rather than by reading the console. The harness copied `wedge-round-4/` with a
self-describing manifest, read the tablet's own pstore verbatim, and broke out of
the loop instead of rounding on.

## The onset both wedges agree on

Two independent kernel timers, both measured from the moment a CPU stopped
executing, applied to the two complete records:

| record | soft lockup | minus 26 s | RCU stall | minus 21 s | stalled CPU |
|---|---|---|---|---|---|
| test-195 | 33.127 s | **7.13 s** | 28.839 s | **7.82 s** | 6 |
| test-197 | 32.546 s | **6.55 s** | 28.763 s | **7.74 s** | 6 |

`CONFIG_SOFTLOCKUP_DETECTOR` reports "stuck for 26s", and
`CONFIG_RCU_CPU_STALL_TIMEOUT=21` with `CONFIG_HZ=250` gives `t=5255 jiffies` =
21.02 s, both confirmed in `out/kernel-gts9wifi/config` rather than assumed.

**So the stall begins at ~6.5-7.8 s, and the RCU stall at ~28.8 s is 21 s of
silence later, not the onset.** The two records agree to within ~1.2 s across two
different victim CPUs (5 and 2) and two different kworkers (`u32:7`, `u32:8`).

That is earlier than any marker previously used as the "first abnormal event":
`frame done timeout` was recorded at 6.7-7.7 s and the DPU early-return at
4.4-4.8 s. It also means the 13-14 s window was never the onset - it was where a
*different* detector happened to fire.

## Neither wedge carries the markers the old ordering relied on

In the pstore console of **both** wedges: `frame done timeout` **0**,
`mmc1 Timeout` **0**, `AMC RPMH` **0**. `docs/STALL_FIRST_EVENT_ORDERING.md`
tabled those three as "present in 3 of 3 failure records"; these two records break
that, and they are the only two captured with a working two-channel instrument.

What both *do* carry is the complete CPU-level set: RCU stall, `Sending NMI`,
soft lockup, panic, the `toggle_allocation_gate -> jump_label_update ->
kick_all_cpus_sync -> smp_call_function_many_cond` chain, and
`SMP: failed to stop secondary CPUs`.

## What is not established

* Which driver, if any. `toggle_allocation_gate` is the canary - it needs every CPU
  to ACK an IPI - so it reports the wedge rather than causing it.
* Whether the aborted CPU was doing something specific. The KLOG channel holds
  every level, and in the wedged boot's 4.6 s → 29 s window there are exactly
  **two** kernel/daemon messages, both userspace stage markers at 6.52 s and
  6.88 s. A clean round's same window is equally quiet, so the window contents do
  not discriminate; only the silence *after* 6.9 s does.
* Whether the 3 clean rounds before it mean anything. They do not: the session's
  rate on this kernel is now 3 wedges in 13 rounds, and no small series
  discriminates at that rate.

## The rate, honestly

| source | rounds | wedges |
|---|---|---|
| test-193 | 5 | 0 |
| test-195 | 1 | 1 |
| test-197 | 4 (stopped on the wedge) | 1 |
| this session, total | **10** | **2** |

Plus the rate2/rate3 series earlier in the session. The point worth keeping is not
the number but that **wedges are frequent enough to catch within a handful of
rounds when the detector works** - which is the opposite of what the broken
detector implied.

## Files

| file | what it is |
|---|---|
| `MANIFEST.txt` | the harness's own manifest: identity, verdict, markers, outage times |
| `on-device-console-ramoops.txt` | the tablet's pstore console for the wedged boot, verbatim |
| `on-device-pmsg.txt` | the marker as it survived the reboot, proving the binding |
| `round-4.txt` | the per-round record |
| `klog-4.txt` | the wedged boot's kernel ring, every level |
| `pstore-4.txt` | the same pstore as the probe read it, `PSTORE `-tagged |
| `console-4-watch.txt` | the COM19 capture with the two presence outages |
| `mark-4.txt` | the identity stamped into `/dev/kmsg` and `/dev/pmsg0` before the reboot |
