# Cold-boot attempt 1: a reboot occurred, but the capture missed it

## What the attempt produced

The capture window ran 23:48:19Z → 00:03:19Z on COM19. Result:

```
panic_lines=0  softlockup_lines=0  hardlockup_lines=0
hungtask_lines=0  rcu_lines=0
panel_recovery_lines=0   deferred_burst_lines=0
console_bytes=5850  lines≈41
```

and the post-boot device verdict read `previous_boot_end=clean-shutdown` with every
marker zero.

Two facts point in opposite directions and both are worth stating:

**A reboot did happen.** The boot-evidence directory list contains an id,
`20260413T193808Z-7f02df57`, that was not present before this attempt, the device's
uptime reset from ~394 s to 802.92 s across the window, and the current boot shows
the panel's cold-enable sequence:

```
[    0.808468] panel-samsung-ana38407 ae94000.dsi.0: ana38407 panel id: 00 00 00
[    4.312303] panel-samsung-ana38407 ae94000.dsi.0: ana38407 panel id: 80 00 04
```

**But the capture did not record a boot.** `grep -c 'Linux version|Booting Linux'` on
the capture returns 0, and the last device line is at 23:50:06. The capture saw
systemd activity at 23:48:52–23:50:06 and then nothing.

## Why the capture missed it

During a power cycle the USB gadget disappears and re-enumerates.

**Corrected (see REATTACH-TEST.md):** this document originally claimed the watcher
cannot re-attach inside one run. That is wrong — a deliberate test shows the same run
closing the port on read error and re-opening it 19 s later, capturing both halves of
a reboot (`00:06:09 port closed (read error)` → `00:06:28 port open on COM19`, 114
lines total). So the re-attach path works.

What actually happened here is narrower: the capture window opened at 23:48:19, the
device's shutdown began at 23:48:52, and the last device line is 23:50:06 — so the
capture **did** span the shutdown but produced no boot half, most plausibly because
the reboot's re-enumeration plus the next boot fell outside the observed portion, or
the boot half carried no messages at the default console loglevel (4.4.1.7, since a
raised level does not survive a reboot).

Either way the conclusion below is unchanged: no cold boot was captured.

## What this attempt cannot tell us, and why

The boot **cannot be classified as cold or warm** from this evidence:

* `previous_boot_end=clean-shutdown` for boot `7f02df57` means the boot *before* it
  ended via an orderly `systemd-shutdown`. A power-button press on this port goes
  through `gts9-power-key.service`, whose own description is "blank the panel only",
  so a button press may not register as a system shutdown at all; and a host-issued
  `systemctl reboot` would also read clean.
* There is no separate boot-type marker in `/proc/cmdline` or the evidence archive to
  distinguish them.

So this is a **reboot of unknown type**, not a cold boot. Recording it as a cold boot
would be exactly the substitution the brief forbids.

The one observation that is genuinely new: the panel emitted the cold-enable
`00 00 00` first read and recovered by 4.31 s, i.e. the initramfs ladder ran — which
is the same behaviour as the warm boots in `COLD-BOOT-GAP.md`. That does not
distinguish boot types either, since the ladder runs on both.

## What a retry needs

The capture must survive the USB re-enumeration. Two options, in order of preference:

1. **Two captures instead of one.** Start capture A, then power-cycle; after the
   device returns, start capture B *immediately* — B will catch the tail of the boot
   and, more importantly, B's own start is proof the device came back. Combine with
   the device's evidence archive for the previous-boot verdict.
2. **A re-attaching watcher.** Modify `console-watch.ps1` to re-open the port after a
   disconnect and keep appending to the same log, so one run spans the whole cycle.
   This is the correct long-term fix and would also have made rounds 6 and 8 cleaner.

Option 2 is the real fix; option 1 is a workaround that still loses the boot half.

## Status

Still no cold-boot datapoint. The gap named in `COLD-BOOT-GAP.md` remains open, and
the 16-cycle warm-reboot result is unchanged.
