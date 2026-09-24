# Round 9: the shutdown capture works, and the shutdown path did not stall

The single-port fix worked. Both rounds captured a complete shutdown and reboot,
and **neither stalled** — so the shutdown-path failure is intermittent, not
deterministic.

## Round 1, read from the capture's own timestamps

| time (UTC) | event |
|---|---|
| 20:25:59 | COM19 capture starts (`watch start: port=COM19 seconds=720`) |
| 20:26:07 | COM17 trigger opens |
| 20:26:28 | `TRIGGER_SHUTDOWN`, then `systemctl reboot` issued |
| 20:27:29 | the **next** boot reaches `multi-user.target` / `graphical.target` |
| 20:37:59 | capture ends, `lines=142 com_disconnects=0 com_reconnects=0` |

So the machine shut down and came back in about **61 seconds**, and the capture
held the port across the whole cycle with zero disconnects.

Note what this corrects: the round-8 script's pre-flight step had already issued a
reboot, so its "trigger" never ran — but the capture window in round 8 was also
mis-sized relative to the actual cycle. Round 9 read the timestamps instead of
inferring from a verdict line.

**Both rounds completed cleanly.** Round 1: `systemd_shutdown_seen=9`,
`panic_lines=0`, `softlockup_lines=0`, `hardlockup_lines=0`, `hungtask_lines=0`,
`rcu_lines=0`, `calltrace_lines=0`, 142 capture lines. Round 2: 13950 bytes /
118 lines, `systemd_shutdown_seen=3`, and the same zero counts for every anomaly
class. So **2 of 2 shutdowns completed normally** — the failure is intermittent,
not deterministic.

## What this establishes

**The capture mechanism is fixed and validated.** One round now yields the complete
shutdown→boot cycle with no port loss. That was the blocker in rounds 6 and 8.

**A clean shutdown takes ~61 s and touches `systemd-shutdown` nine times.** This is
the concrete baseline the failing case must be compared against. The failing case
(the archived `…-8d7db274`) reached `multi-user.target` at 62.98 s, was already
stopping services at 70.5 s, and stopped recording before any `systemd-shutdown`
line — so it diverged right after the point where a healthy boot keeps going.

**The shutdown failure is intermittent.** Two consecutive reboots completed
cleanly. Whatever the mechanism is, it is not triggered by every shutdown, so
capturing it needs repetition rather than a single run.

## Still not resolved, and now precisely bounded

Whether a shutdown failure produces a **panic** is not settled. This round tried to
answer it by holding COM19 at `loglevel=8` and did not observe a stall, so there was
nothing to see.

One measurement did complicate the picture: with `echo 8 > /proc/sys/kernel/printk`
confirmed as `CURRENT=8 4 1 7` and `console/ttyGS1` in the active console list, a
`dev/kmsg` write did **not** appear in the COM19 capture. That is unresolved — it
could be the write's own log level rather than the console's, and it does not
invalidate the round-7 observation that a marker *did* reach COM19 after
`dmesg -n 8`. It does mean "the console capture will show a panic" is **not yet
demonstrated for panic output specifically**, only for a manually raised level.

The conservative position for the next attempt: do not rely on the console alone.
Extend the capture to many rounds, and treat the device's own evidence archive
(`previous_boot_end`) plus the command-result liveness check as the primary
detectors, with the console as corroboration.
