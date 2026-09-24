# Round 8: the shutdown capture did not run, and what the attempt established

The shutdown-path experiment was attempted and **produced no data**. Recording why,
because two of the three findings below are about the measurement setup rather than
the stall, and the same class of mistake has now cost several rounds.

## What was attempted

`shutdown-capture.sh`, which raises printk's console loglevel, starts captures on
COM17 **and** COM19, issues `systemctl reboot`, and inspects the capture for a panic
or for a shutdown that never reaches `systemd-shutdown`.

## Why it produced nothing

The script holds **both** serial ports for the duration of the capture window and
then tries to issue the reboot over COM17 — which its own shell watcher is already
holding:

```
console-2.log:  watch start: port=COM19 seconds=780
                port open on COM19
                watch done: lines=0 com_disconnects=0 com_reconnects=0
trigger-2.log:  could not open COM17
```

Both captures are exactly 373 bytes — the watcher's own banner, no device output.
`trigger-2.log` shows the cause directly: `could not open COM17`.

The reboot still happened (the device came back), but it was issued by the
pre-flight step, not by the trigger, so no capture bracketed it. A design that
cannot perform its own trigger cannot observe the trigger.

**Fix for the next attempt:** hold COM19 only. Issue the trigger over COM17 from a
separate step *before* starting the COM17 watcher, or do not watch COM17 at all —
COM19 is the port that carries kernel output, which is the channel that matters
here. `shutdown-capture.sh` should be simplified to a single-port capture plus a
single trigger.

## Three things the attempt did establish

**1. printk's console loglevel can be raised at runtime.**

```
before=4 4 1 7
after=8
```

Confirming the round-7 mechanism: kernel messages are suppressed on the console by
default (`4.4.1.7`), and raising the level is what makes them visible. This is why
round 6 wrongly concluded the console was userspace-only.

**2. Historical shutdowns DID complete — the incomplete shutdown is not normal.**

Every archived capture containing a shutdown also contains exactly two
`systemd-shutdown` lines:

| capture | `systemd-shutdown` count |
|---|---|
| `test-179/host-captures/boot-minus1.log` | 2 |
| `test-179/host-captures/p4-post2.log` | 2 |
| `test-179/host-captures/boots.log` | 14 (seven boots) |

So "shutdown started, then the record ends before `systemd-shutdown`" — the
signature round 7 found in `…-8d7db274` — is **not** how this board normally
shuts down. It is a distinct failure mode, which strengthens the round-7
localisation rather than undermining it.

**3. Complication with immediate follow-on value:** a shutdown issued over COM17 is
itself an intervention. The device is rebooted by the act of observing it, so a
"shutdown stall rate" measured this way is a rate for *observed* shutdowns, not for
shutdowns in general. Any such number must be labelled that way.

## Status

Still not captured: whether the shutdown failure panics. The experiment is ready
and its flaw is identified; it needs one more attempt with the single-port fix.
Everything else about it — the loglevel mechanism, the viability of the console
channel, the abnormal-shutdown confirmation — is now established.
