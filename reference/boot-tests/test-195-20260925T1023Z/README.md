# test-195: a real CPU-level wedge, captured with the round identity proven

2026-09-25T10:22–10:24Z, one baseline round run by the fixed harness. **Nothing
was flashed** - the `baseline` profile is byte-identical to what the tablet runs.

This is the first failure captured since the round-identity work, and the first
whose provenance does not have to be inferred: the round wrote its own name into
the kernel ring and into ramoops before rebooting, so every artifact below is
bound to one round by construction.

## The binding, which is the point of the round

```
round record : identity=GTS9_AB run=verify1 profile=baseline round=1 boot_id=6d8b975c
device pmsg  : GTS9_AB run=verify1 profile=baseline round=1 boot_id=6d8b975c
```

The marker was written by boot `6d8b975c` **before** its reboot, read back out of
the kernel ring by the probe, and found again in the *next* boot's ramoops pmsg
copy. So the console capture, the journal, the pstore record and the USB presence
trace are provably one round — not four artifacts that happen to be adjacent in
time, which is the mistake test-194 made.

## What the wedge looks like

From `on-device-console-ramoops.txt` (5819 B, the tablet's own copy):

```
[   28.839360][    C7] rcu: INFO: rcu_preempt detected stalls on CPUs/tasks:
[   28.846363][    C7] rcu: 	6-...0: (1 GPs behind) idle=bbfc/1/0x4000000000000000 softirq=1141/1142 fqs=1107
[   28.843906][    C7] Sending NMI from CPU 7 to CPUs 6:
[   33.126734][    C5] watchdog: BUG: soft lockup - CPU#5 stuck for 26s! [kworker/u32:7:93]
[   33.126758][    C5] Workqueue: events_unbound toggle_allocation_gate
[   33.126811][    C5]  kick_all_cpus_sync+0x48/0x7c
[   33.126813][    C5]  arch_jump_label_transform_apply+0x14/0x24
[   33.126833][    C5]  toggle_allocation_gate+0x58/0x14c
[   33.126850][    C5] Kernel panic - not syncing: softlockup: hung tasks
[   34.656557][    C5] SMP: failed to stop secondary CPUs 3,6-7
```

This is the established shape, and every marker the project counts is present:

| marker | value |
|---|---|
| `rcu detected stall` | present, 28.839 s, CPU 6 one GP behind |
| `Sending NMI from CPU 7 to CPUs 6` | present, 28.844 s |
| `soft lockup` | present, CPU#5 stuck 26 s |
| `Kernel panic - not syncing: softlockup: hung tasks` | present, 33.127 s |
| victim chain | `toggle_allocation_gate -> static_key_enable -> jump_label_update -> arch_jump_label_transform_apply -> kick_all_cpus_sync -> smp_call_function_many_cond` |
| `SMP: failed to stop secondary CPUs` | **3,6-7** |

The `Sending NMI` line is only visible now because §5 of the round-29 review
required `nmi_unresponsive` to be counted and because this build carries
`loglevel=4`… note the NMI *backtrace timeout* line
(`haven't responded to the NMI`) is **absent**: the NMI was sent and CPU 6's state
was reported through the RCU stall path instead, so this record does not carry the
`After 10 seconds, these CPUS still haven't responded` line. `rcu detected stall`
plus `soft lockup` plus the panic are the wedge-class evidence here.

Onset: the first abnormal event is `encoder is disabled` at 4.787 s, the RCU stall
at 28.839 s, the panic at 33.127 s. **Not the 13–14 s window** — consistent with
`docs/STALL_FIRST_EVENT_ORDERING.md`, which already records onsets at 6.8 s,
~52.5 s and ~76 s and states that the window is not a law.

## What this does and does not change

**It does not revive anything from test-194.** test-194 remains a false-positive
console-silence episode; this is a different round with CPU-level evidence and an
unrequested restart.

**It confirms the classifier works, and it exposed a bug in the detector.** The
harness returned `verdict=wedge` on `wedge_markers=4` (soft lockup, hung task, RCU
stall, panic - all from pstore) with `suspect_markers=0`, and `verdict=clean` on
the quiet boots.  A lone DPU timeout would have been `suspect`, as required.

But the *other* wedge signal - the unrequested restart - read 0 in this round's
record, and that was wrong:

```
presence_outages=0        (as recorded)
```

The watcher log plainly contains two outages:

```
10:23:33.082Z  False   <- the harness's own `systemctl reboot`
10:23:52.970Z  True    <- the boot under test
10:24:32.000Z  False   <- *** the panic's restart: nothing the harness did ***
10:24:51.589Z  True    <- the next boot
```

**The cause was a variable name.** The harness assigned to `klog-watch`, which is
not a valid bash identifier: `klog-watch=$DIR/console-$i-watch.txt` is parsed as
the *command* `klog-watch=...` (command not found, silently), and the reference
`"$klog-watch.txt"` expands as `${klog}` + `-watch.txt` - a path that does not
exist. So `tr ... <"$klog-watch.txt"` read nothing and every count came back 0.
**The automatic-restart detector has therefore never worked in this harness**, and
`presence_outages=0 / automatic_reboot=no` in the earlier test-193 and test-195
records must not be read as "no restart happened".

Renamed to `watch_log` and verified against this very capture: the detector now
reports `presence_outages=2`, `automatic_reboot=yes`, second outage at
`10:24:32.000Z`. The verdict was already `wedge` here on the marker count, so this
does not change the round's outcome - but it would have missed a restart that
produced no pstore markers at all, which is exactly the case the pstore cannot
cover.

**It does not identify a cause.** `toggle_allocation_gate` is the canary, exactly
as `docs/CPU_WEDGE_EVIDENCE.md` says: it needs every CPU to ACK an IPI
(`kick_all_cpus_sync`), so it reports the wedge rather than causing it. CPUs 5, 6
and 7 did not ACK. No DPU flood, no `mmc1` timeout, no RPMh error appears before
the RCU stall in this record — the only pre-onset line is the handled DPU
early-return that fires on every boot.

## Files

| file | what it is |
|---|---|
| `on-device-console-ramoops.txt` | the tablet's own ramoops console for the wedged boot, 5819 B |
| `pstore-console.txt` | the same record as the harness read it over ssh, `PSTORE `-tagged |
| `klog.txt` | the wedged boot's kernel ring (`journalctl -k -b -1`), `KLOG `-tagged |
| `round-1.txt` | the harness's per-round record, including `identity=` and the verdict |
| `console-1-watch.txt` | the COM19 capture with the USB presence transitions |

## Next

The wedge survives on `baseline`, so the ablation is meaningful. **Profile C
(`msm.skip_gpu=1`) is the next physical test** and needs one `vendor_boot` flash;
`gpu_driver=NONE` with DPU/DSI/panel still working is the check that it took. If a
wedge appears under C with this evidence quality, the GPU/GMU/ACD path is
downgraded; if C produces `verdict=clean` over enough rounds, that is
"not reproduced in N rounds" and **not** an exclusion.
