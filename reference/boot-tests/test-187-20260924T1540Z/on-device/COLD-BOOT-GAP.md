# The remaining gap: every measurement so far is a warm reboot

## The gap, stated precisely

All 16 observed shutdown cycles, and all 8 retained boot records, are **warm
reboots**. The brief is explicit that a warm reboot must not be passed off as a cold
boot, and there is a specific physical reason it matters here:

* a warm reboot leaves DRAM contents and the ramoops region intact across the reset;
* a cold boot (power removed) does not;
* the pre-fix failures were observed across a mix of boot types.

So a failure that depends on cold-boot state — an uninitialised region, a power rail
that only drops on a real power cycle, firmware state that survives a warm reset —
would not appear in any measurement taken so far. That is a real limitation of the
current result rather than a technicality.

## What is already known about this boot's own timing

Measured on the current boot:

```
[    0.908241] panel-samsung-ana38407 ae94000.dsi.0: ana38407 panel id: 00 00 00
[    4.692275] panel-samsung-ana38407 ae94000.dsi.0: ana38407 panel id: 80 00 04
```

The panel's first-enable read returns `00 00 00` (the known cold-enable failure), the
initramfs recovery ladder cycles the framebuffer, and the read succeeds at 4.69 s —
about 3.8 s of recovery, **before** the deferred-probe burst at 14.30 s. So on this
boot the ladder did not overlap the stall window.

Whether a *longer* ladder (the worst case is ~13-23 s per
`docs/BOOT_TIMING_AND_STALL_EVIDENCE.md`) would push the recovery into the 14 s window
is an open question, and it is a cold-boot question: the `00 00 00` first-read is the
cold-enable behaviour.

## The experiment

A cold boot is the one thing that cannot be issued from the host — it needs the
power button. The protocol, so that nothing about it is improvised:

1. start the COM19 capture **first**, with a window long enough to span a cold boot
   (the panel ladder plus a full boot can take 4-6 minutes; 900 s is safe);
2. **you** power-cycle the tablet while the capture runs;
3. after the device returns, read
   `/var/log/gts9-boot-evidence/<newest>/verdict.txt` for `previous_boot_end` and the
   marker counts, and read the capture for panic/lockup lines;
4. compare against the warm-boot baseline: clean shutdown ~61 s, burst at 14.304 s,
   panel recovery at ~4.7 s, `sync_state` 29-31 lines.

The specific things a cold boot could reveal that no warm boot could:

* a **different burst time** than 14.30 s, if the initramfs ladder runs longer from
  cold and shifts it (the burst follows `driver_register()`, per the round-3
  correction, so anything that delays the initramfs moves it);
* a **stall** that only occurs from cold, which would explain why 16 warm cycles
  found nothing while the pre-fix failures were seen across mixed boot types;
* nothing different at all, which is itself the useful result: it would put the cold
  path on the same footing as the warm path.

## Status

Not yet run. It requires the operator, and it is the highest-value remaining test
because it is the only one that addresses a confound the current 16-cycle result
cannot remove by adding more warm cycles.
