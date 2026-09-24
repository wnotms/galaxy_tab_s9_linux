# Test 181 — DPU/DSI display pipeline: instrumentation, baseline, and one stall

**Status:** instrumentation in place; baseline captured; the intermittent stall
was **reproduced once** and its kernel-side evidence collected.  Nothing was
changed in the kernel: the msm driver already ships the tracepoints this needs,
and the reproduced stall turned out to be CPU-level rather than a frame-done
timeout.

Device SM-X710 / gts9wifi, Debian 13 on `/dev/mmcblk1p1`, Type-C attached,
runs 2026-09-24 01:16Z – 02:4xZ.  Source HEAD at the start: `22630cc`.

## Why this shape

The failure mode under investigation (`enc35 frame done timeout` →
`vblank wait timed out` → `drm_fb_helper_damage_work` → workqueue lockup → RCU
stall, test 178) removes the machine's ability to run commands, so the trace has
to be armed before it happens and has to be written somewhere that survives a
forced restart.  Both are satisfied without a kernel change:

- `gts9-dpu-trace-arm.sh` arms 32 events (`dpu:*` kickoff / frame-done /
  pdone-timeout / TE / wait-timeout, the drm vblank events, the msm atomic
  commit events) plus an `irq==186 || irq==187` filter, and turns tracing on.
- `gts9-dpu-flight.sh` snapshots the ring buffer, the kernel-log tail and the
  display IRQ counters to the microSD every few seconds.
- `gts9-dpu-flight.service` starts the recorder from early boot (before
  `gts9-panel-recover.service`), which is what makes cold-boot capture work.

See `docs/DPU_TRACE.md` for the tracepoint inventory, the driver failure chain
these markers correspond to, and how to read a snapshot.

## The reproduced stall (2026-09-24 ~02:03–02:20Z)

Cold-boot round 3 of the harness rebooted the tablet; that boot recovered the
panel normally (`panel id: 00 00 00` → cycle 1 → `80 00 04` at 4.79 s) and then
stalled.  Symptoms, in the order they were observed:

1. The COM17 port stayed enumerated but its shell stopped executing commands
   (the kernel tty still echoed input) — the same signature test 172 recorded.
2. The owner saw the cursor stuck on the panel and the Pogo keyboard dead.
3. Neither a short nor a long power-key press recovered it (the daemon logged
   `long press ignored (PMIC owns it)`; `nowatchdog` means no watchdog resets a
   stall), so it took a ~15 s PMIC hold to force a restart.

The hung boot is `a4e5bd13…`, the last-but-one journal
(`journalctl -b -2`); its journal ends abruptly at 132.4 s with no shutdown.
The kernel's own reports (`host-captures/r3-hang-evidence.log`,
`r3-stacks.log`, `r3-worker-stack.log`, `r3-boots.log`):

```text
[   4.276050] [drm:dpu_encoder_helper_wait_for_irq] *ERROR* encoder is disabled id=35,
                callback=dpu_encoder_phys_cmd_ctl_start_irq, IRQ=[1, 9]     <- the usual benign line
[  14.3     ] (last normal log: deferred-probe completion, qcom-pcie host bridge)
[  36.340021] rcu: INFO: rcu_preempt detected stalls on CPUs/tasks:
[  36.340149] rcu:     5-...0: (0 ticks this GP) idle=… softirq=696/696 fqs=1058
[  36.340219] After 10 seconds, these CPUS still haven't responded to the NMI: 5
[  36.340241] rcu: rcu_preempt kthread starved for 2495 jiffies! … ->cpu=7
[  62.449098] BUG: workqueue lockup - pool cpus=1 node=0 flags=0x0 nice=0 stuck for 56s!
[  62.491017]     in-flight: 27:fqdir_free_fn for 56s
[  62.491043]     pending: 9*psi_avgs_work, pogo_watch_work
[  62.491158]   workqueue pm: in-flight: 75:pm_runtime_work for 56s
[  62.491194]                        in-flight: 12:pm_runtime_work for 56s ,174:pm_runtime_work for 56s
[  62.491224]                        in-flight: 77:pm_runtime_work for 56s
[  93.203821]   workqueue events: pending: drm_fb_helper_damage_work       <- victim, not cause
[  93.204154] task:kworker/1:0  state:R running task … Workqueue: events fqdir_free_fn
[  93.204405]  __switch_to+0x210/0x358 (T)
[  93.204424]  0x7fffffff                                                  <- no usable stack
```

Interpretation:

- **One CPU (5) stops answering NMIs**, i.e. it is wedged in a way that even the
  NMI backtrace cannot sample.  That is the primary event; everything else
  follows from it.
- The workqueue report names *several unrelated* victims — `fqdir_free_fn`
  (IP fragment cleanup) on CPU 1's pool, four `pm_runtime_work` items, and
  `drm_fb_helper_damage_work` **pending** — which is what a global stall looks
  like, not a DRM-specific one.  In this instance there is **no** `frame done
  timeout` and **no** `vblank wait timed out`.
- The last normal log line is at 14.3 s (deferred-probe completion, PCIe host
  bridge enumeration); the stall is detected at 36.3 s, so the wedge began
  somewhere in the quiet interval between them.
- `nowatchdog` plus "Hard watchdog permanently disabled" is why nothing
  recovered the machine; only the PMIC hold did.

This changes the shape of the investigation: test 178's DPU hang and this stall
share the *symptom* (dead console, stuck cursor, keyboard dead) but not
necessarily the *cause*.  The DPU damage worker being merely pending here means
the DPU path is a candidate victim of the same wedge rather than proven to be
the trigger.

## What ran, and what it showed

| Experiment | Result | Capture |
|---|---|---|
| 10 + 20 framebuffer blank/unblank cycles with the full trace | 275 kickoffs = 275 frame-done callbacks, 0 pdone/frame-done timeouts, every wait `rc>0` | `r2-cycles10.log`, `r2-batch20.log` |
| One cycle with trace markers, IRQ counters before/after | msm-kms +86…91, dsi_isr +120…121 per cycle; atomic commits complete; vblank event delivered | `r2-onecycle.log`, `r2-window2.log` |
| 80 cycles with a console write between each (racing a commit against the modeset) | 1104 kickoffs, 0 `pdone_timeout`, 0 `frame_done_timeout`, 0 kickoff resets | `r3-race.log` |
| fbcon unbound (`vtcon1` found by name, not index) and 5 cycles | same per-cycle `dpu_encoder_helper_wait_for_irq … ctl_start_irq` message, 0 timeouts, rebind OK | `r3-fbconab.log` |
| Cold boots with the recovery cycle executed | no DPU error, no lockup, panel ends at `80 00 04` | `bootloop-v1.txt`, `bootloop.txt` |
| 30 backlight-only screen toggles (test 180) | 0 DPU/vblank/workqueue/RCU errors | `reference/boot-tests/test-180-…` |

## Findings

1. **The recurring DRM "error" is not the bug.**  Every blank/unblank cycle logs

   ```text
   [drm:dpu_encoder_helper_wait_for_irq] *ERROR* encoder is disabled id=35,
     callback=dpu_encoder_phys_cmd_ctl_start_irq, IRQ=[1, 9]
   ```

   which is the `DPU_ENC_DISABLED` guard returning `-EWOULDBLOCK` immediately
   (`dpu_encoder.c`), i.e. a caller asking a disabled encoder to wait for the
   ctl-start interrupt.  It appears once per cycle in every run, including runs
   with zero failures.
2. **fbcon is not what provokes it.**  With the framebuffer console unbound the
   same message still appears once per cycle, so the console damage worker is
   not a necessary trigger for the modeset-path anomaly.
3. **The healthy pipeline is tight.**  Kickoffs and frame-done callbacks match
   one for one and every `wait_event_timeout()` returns with `rc>0`; the
   kickoff deadline is 84 ms (`KICKOFF_TIMEOUT_MS`).
4. **The stall reproduced, and it is not (in that instance) a frame-done
   timeout.**  The hung boot shows an NMI-unresponsive CPU, stuck
   `fqdir_free_fn`/`pm_runtime_work` items and a *pending*
   `drm_fb_helper_damage_work`, with no DRM timeout message anywhere.  The
   recorder now keeps the previous boot's snapshot as
   `/var/log/gts9-dpu-flight.txt.prev`, so the *next* occurrence can be read
   with its trace instead of only its journal.
5. **The lockup is rare but reproducible.**  It appeared once in the ~12 cold
   boots and ~1300 modeset commits of this session; test 178 saw it once in a
   comparable number of boots.

## Files

```text
gts9-dpu-trace-arm.sh    arm/disarm the tracepoint set (device-side)
gts9-dpu-flight.sh       flight recorder (device-side, microSD snapshots)
gts9-dpu-flight.service  early-boot unit for the recorder
dpu-bootloop.sh          host-side cold-boot harness (reboot, wait, collect)
bootloop*.txt            per-boot results of the harness
host-captures/           raw COM17 captures for every experiment above
```

Rollback: `systemctl disable --now gts9-dpu-flight.service`, then remove
`/etc/systemd/system/gts9-dpu-flight.service`, `/usr/local/sbin/gts9-dpu-flight`
and `/usr/local/sbin/gts9-dpu-trace-arm`.  None of this is part of the shipped
overlay, and none of it changes kernel behaviour.
