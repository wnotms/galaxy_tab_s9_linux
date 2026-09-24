# Test 182 — PCIe A/B for the cold-boot stall

**Status:** running (boot hunt in progress).  Image flashed and verified;
`pcie0` is `disabled` on the tablet and no PCIe probe message appears.

## Hypothesis under test

Test 181 reproduced the stall twice and both occurrences share one last normal
log line: the `qcom-pcie 1c00000.pcie` host-bridge probe at ~14.05 s, after
which nothing is logged until the RCU stall at ~36 s.  Healthy boots print the
same three lines and continue.  The stall itself is CPU-level (one core stops
answering NMIs) with unrelated work items stuck afterwards
(`fqdir_free_fn`/`toggle_allocation_gate`, three to four `pm_runtime_work`, a
*pending* `drm_fb_helper_damage_work`, RCU stalls), which is what a core stuck
in a bus access looks like.

So: if the stall is caused by the PCIe0 probe, disabling that controller should
stop the stalls.

## Change

`kernel/dts/sm8550-samsung-gts9wifi.dts`: `&pcie0` and `&pcie0_phy` move from
`status = "okay"` to `"disabled"`, with the reasoning in a comment.  Nothing
else changes — not the kernel, not the cmdline, not the initramfs, not the
Debian overlay.

PCIe0 carries the QCA6490 WLAN endpoint (GPIO94/96), for which mainline has no
driver, so nothing consumes it today.  If this confirms the hypothesis, the
real fix is a driver-level guard (never issue a config/link access that cannot
complete when the link did not come up) rather than a permanently disabled
node, because WiFi needs it back later.

## Images

| Partition | Before | After | Written |
|---|---|---|---|
| `boot` (sda21) | `822ca9dc…` | `8ef761dbbd562f317b3963418cf912e46291b5ced97226c1e914a1c02254c2ec` | yes, read back verified |
| `vendor_boot` (sda24) | `3c88b36b…` | `73da01f6f825b296259ae3c166a51282040000d45c5fac278b336fd2e735f63d` | yes, read back verified |
| `init_boot`, `dtbo`, `vbmeta` | unchanged | unchanged | no |

Both partitions carry the board DTB (appended to `boot.img`, DTB section in
`vendor_boot`), so the pair moves together.  The kernel payload, cmdline,
bootconfig and initramfs are unchanged (DTB only):

```text
old DTB sha256 f49b373462a278fcafb858fa9f59dac174d88b4f14810ad2638509d9c2e9e9be
new DTB sha256 137a54764c825c6514c47b1f27603708f4730041d5b7cfe335343eebb0f3c30e
```

Backups: `boot-before.img` / `vendor_boot-before.img` in the host staging
directory `/home/ms/Samsung/gts9-flash-tests/test-182-20260924T025346Z/`,
written and hash-checked by `flash-pcie-off.sh` before anything was written.

Post-flash verification on the tablet:

```text
/proc/device-tree/soc@0/pcie@1c00000/status = disabled
dmesg | grep -c pcie                         = 0
cmdline unchanged (console=tty0, gts9_poweroff_trace=1)
systemctl is-system-running                  = running
```

## Baseline (control, PCIe0 enabled)

Two stalls in the ~18 cold boots of test 181 (one in each hunt), i.e. roughly
1 in 9 boots:

| Hunt | boots | stalls |
|---|---|---|
| test 181 hunt 1 (36-event trace, 16 MiB ring) | 8 attempted, stalled on the boot after round 3 | 1 |
| test 181 hunt 2 (same) | 9 attempted, stalled on the boot after round 4 | 1 |

Each stall: console echoes but stops executing, COM17 enumerated yet not
openable, panel holds a stuck cursor, Pogo keyboard dead, only a ~15 s PMIC
hold recovers it.

## Result: hypothesis falsified, and a DPU-side stall captured in full

The A/B image stalled on its **second** boot (started ~02:59:01Z), and a later
boot of the same image produced the DPU-side failure with a complete trace.
Together they close the PCIe question and open the real one.

### The PCIe hypothesis is dead

Nothing PCIe-related appears in the stalled boot at all:

```text
dmesg | grep -c pcie                        = 0
/proc/device-tree/soc@0/pcie@1c00000/status = disabled

[   35.832010] rcu: INFO: rcu_preempt detected stalls on CPUs/tasks:
[   35.832111] After 10 seconds, these CPUS still haven't responded to the NMI: 5
[   35.876308] BUG: workqueue lockup - pool cpus=2 ... stuck for 31s!
[   36.053464]     in-flight: 140:fqdir_free_fn for 31s
[   36.053667]     in-flight: 12:pm_runtime_work for 30s
[   36.053430]     in-flight: 78:pogo_watch_work for 10s
```

The PCIe correlation in test 181 was an artefact: the host-bridge probe simply
happened to be the last thing that logged before the quiet window.  The DTS
change buys nothing and WiFi needs the node, so it must be reverted.

## Four stalls, one window

| | stall 1 | stall 2 | stall 3 (A/B) | stall 4 (DPU) |
|---|---|---|---|---|
| image | test 181 | test 181 | PCIe0 disabled | PCIe0 disabled |
| NMI-unresponsive CPU | 5 | 7 | 5 | (RCU stall reported) |
| last normal log | PCIe 14.05 s | PCIe 14.05 s | sync_state 13.54 s | DPU overflow 13.263 s |
| `pm_runtime_work` stuck | 4 | 3 | 3 | - |
| other stuck work | `fqdir_free_fn` | `toggle_allocation_gate` | `fqdir_free_fn`, `pogo_watch_work` | `drm_fb_helper_damage_work` pending |

All four begin in the **same ~13.3-14.3 s window after boot** - the deferred
probe / late-init burst.  Stalls 1-3 end in a wedged CPU; stall 4 ends in the
DPU's frame-event machinery first, and takes the machine down the same way.

## The DPU-side failure, captured in full (boot `d5adf27e`)

`gts9-dpu-stream.sh` (which consumes `trace_pipe` instead of formatting the
whole ring) wrote 48,864 lines / 4.7 MB for that boot.  Correlating it with the
journal gives the whole chain:

```text
[    5.284091] last dpu_crtc_frame_event_done      (frame_pending reached 0)
[   13.262979] [drm:dpu_crtc_frame_event_cb] *ERROR* crtc103 event 1 overflow
[   13.26 ...] 37 such messages, interleaved with successful events
[  109.852601] dpu_enc_kickoff: id=35                                          <- last kickoff
[  109.867301] dpu_enc_frame_done_cb + dpu_crtc_frame_event_cb: id=103 event=1 <- last frame done
[  109.87 ...] no kickoff, no frame-done, no crtc frame event
[  172.6  ...] irq=186 msm-kms + dpu_crtc_vblank_cb every ~8 ms to the end     <- vblanks keep coming
[  182.856861] last journal line: another crtc103 overflow; console already dead
```

Measured over that boot: `dpu_enc_kickoff` 65, `dpu_enc_frame_done_cb` 66,
`dpu_crtc_frame_event_cb` 66, `dpu_crtc_frame_event_done` 29,
`frame_event_more_pending` 0, `frame_done_timeout` 0, `pdone_timeout` 0.

Read against `dpu_crtc.c`:

- `dpu_crtc_frame_event_cb()` takes one entry from a fixed-size
  `frame_event_list` and queues it on the CRTC's kthread worker
  (`kms->event_thread[crtc_id]`).  With no entry free it drops the event and
  logs the rate-limited `overflow` message (lines 740/747).
- `dpu_crtc_frame_event_work()` decrements `frame_pending`, and on a DONE event
  runs `complete_all(&dpu_crtc->frame_done_comp)` - the completion the commit
  path waits on - then returns the entry to the list.
- So once entries are exhausted a DONE event can be **dropped**, the waiting
  commit never gets its completion, the next commit blocks forever, the DRM
  workqueue stops draining (`drm_fb_helper_damage_work` pending) and the RCU /
  workqueue reports follow.  That is exactly the sequence above: the display
  froze at 109.87 s and the machine stayed unusable until the PMIC hold.

### The questions that mattered, answered from this capture

| question | answer |
|---|---|
| last normal frame-done | 109.867301 s (`dpu_enc_frame_done_cb`, kickoff 109.852601 s) |
| first kickoff after recovery | yes - recovery at 4.79 s, kickoffs continue through the boot |
| frame-done IRQ disappears | yes, after 109.867 s (no `dpu_enc_frame_done_cb` again) |
| vblank IRQ disappears | **no** - `irq=186 msm-kms` + `dpu_crtc_vblank_cb` every ~8 ms to the end |
| IRQ arrived but state not consumed | yes: frame events are dropped (`overflow`) from 13.263 s, so the DONE completion is lost |
| CRTC still active | yes (vblank callbacks keep firing) |
| encoder still enabled | yes (no disable event; TE stays connected) |
| DSI host/PHY recovered | yes (`dsi_isr` keeps firing; panel ID stayed `80 00 04`) |
| fbcon damage worker a necessary trigger | no - it is a *victim* here: it is what blocks on the lost completion |

### Still open

1. Why the per-CRTC event kthread stops draining at ~13.3 s.  The 13.26-13.5 s
   window is the same one in which the other three stalls wedge a CPU, so the
   next step is to trace that thread's scheduling (and the
   `deferred_probe_work_func` burst in the same window) rather than the display
   path itself.
2. A defensible driver change for the drop path: never let a DONE event be
   dropped without completing `frame_done_comp`, so a lost event degrades one
   frame instead of wedging the machine.  That is a robustness fix, not the
   root cause, and must not be presented as one.

## Rollback (done)

The falsified DTS change was reverted in the same session, and the tablet was
flashed back to the known-good pair with the same verified procedure
(`rollback-write-readback.txt`):

```text
boot       <- boot-before.img        readback 822ca9dcf404de83e79f085a5509ec761bf0234359a5fae166c5d1c849e1df86  PASS
vendor_boot<- vendor_boot-before.img readback 3c88b36b7b3f1703ccd751b77522fa6d16596650e627893e3131848c96731dec  PASS
```

Verified on the tablet afterwards: `pcie0=okay`, `dmesg | grep -c pcie` = 40
(the probe runs again), `systemctl is-system-running` = running, and the
rebuilt reverted DTB is byte-identical to the original known-good one
(`f49b373462a278fcafb858fa9f59dac174d88b4f14810ad2638509d9c2e9e9be`).

The diagnostic recorder is disabled again (`systemctl disable --now
gts9-dpu-flight.service`, tracing off) so it does not keep writing the microSD;
the scripts stay installed and re-arm with
`systemctl enable --now gts9-dpu-flight.service`.
