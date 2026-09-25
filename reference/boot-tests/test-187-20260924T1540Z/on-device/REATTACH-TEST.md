# The console watcher survives a reboot — verified, and the round-8 diagnosis corrected

## The test

Deliberately simple: start `console-watch.ps1` on COM19, issue `systemctl reboot`,
and see whether the **one run** spans both halves of the cycle.

## Result: it does

```
00:06:00.410  PRESENCE com=True ports=[COM17,COM19]
00:06:00.434  port open on COM19
00:06:08.887  RECV  Stopping session-1.scope - Session 1 of User root...
00:06:09.327  port closed (read error)
00:06:28.377  port open on COM19
00:06:29.691  RECV  Started user@0.service - User Manager for UID 0.
00:06:29.898  RECV  Finished gts9-debian-multi-user-stage.service
00:11:29.523  port closed (watch end)
              watch done: lines=114 com_disconnects=0 com_reconnects=0
```

One process caught the shutdown, lost the port at 00:06:09, **re-opened it at
00:06:28**, and caught the next boot reaching multi-user — 114 lines across the whole
transition.

## Correction to the round-8 diagnosis

Round 8 concluded that "a single-process serial reader does not reliably re-attach
inside the same run" and that this was why its captures were empty. **That was
wrong.** The watcher's re-open path works, as the log above shows directly
(`port closed (read error)` → `port open on COM19`).

The real cause of round 8's 373-byte captures was already found and fixed in the same
round by a different route: the script held COM17 for a shell watcher *and* tried to
trigger over COM17, so `trigger-2.log` read `could not open COM17` and no reboot was
ever issued during the window. The 373 bytes were the watcher's own banner with
nothing to observe. `COLD-BOOT-ATTEMPT-1.md` repeats the round-8 claim, so this
document supersedes it on that point; the rest of that document — that no cold boot
was captured and that the reboot could not be classified as cold or warm — stands.

## What this changes for the cold-boot attempt

Round 8's "retry needs a re-attaching watcher" recommendation is unnecessary: the
watcher already re-attaches. A cold-boot retry needs only the existing script plus a
window long enough to cover the re-enumeration gap and the next boot.

Two limits to keep in mind:

* the re-open took ~9 s here (00:06:09 → 00:06:28), so a very early kernel message
  could fall inside the gap — the device's own evidence archive remains the
  authority for the previous boot's verdict;
* the boot half shows systemd messages, not kernel ones, because
  `/proc/sys/kernel/printk` is `4.4.1.7` until something raises it, and after a
  reboot the raised level is gone. Shutdown-time messages captured before the reset
  are the ones that benefit from the raised level.

## Standing value

`lines=114 com_disconnects=0 com_reconnects=0` also confirms the re-open is clean
enough that the disconnect/reconnect counters do not even fire — the counters track
COM-port *presence* transitions, and the gadget never left the port list, only the
read failed. That is worth knowing for interpreting those counters in future rounds:
`com_disconnects=0` does **not** mean no reboot happened.
