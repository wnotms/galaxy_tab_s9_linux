# The 90-second delay before poweroff completes

**Resolved 2026-09-26.** The unit below is deleted rather than shortened, and the
delay is gone: shutdown now completes in **0.82 s** with zero stop timeouts, down
from 90 s. See [test-211](../reference/boot-tests/test-211-no-serial-consoles/README.md).
The investigation is kept as the evidence for why the unit had to go.

## Symptom

On `poweroff` the console prints:

```
Broadcast message from root@gts9 (Tue 2026-04-14 00:51:59 CST):

The system will power off now!
```

and then **sits with a blinking cursor for up to ~90 seconds** before the rails
actually drop. Reported by the owner on 2026-09-25; reproducible in this repo's own
shutdown log.

## Cause

`gts9-acm-getty.service` runs:

```
ExecStart=-/usr/sbin/agetty --autologin root --noclear ttyGS0 115200 vt100
```

`--autologin` makes agetty spawn a **login shell**. On `SIGTERM` agetty exits but the
shell it spawned is not reaped, so the unit's cgroup stays populated and systemd
cannot consider the unit stopped. It waits out `TimeoutStopSec`, whose default is
90 s, and only then escalates. From the journal:

```
gts9-acm-getty.service: Stopping gts9-acm-getty.service...
gts9-acm-getty.service: State 'stop-sigterm' timed out. Killing.
gts9-acm-getty.service: Killing process 1456 (login) with signal SIGKILL.
session-38.scope: Stopping timed out. Killing.
session-38.scope: Killing process 1463 (bash) with signal SIGKILL.
gts9-acm-getty.service: Failed with result 'timeout'.
```

Two details in that log are worth noting:

* the killed processes are `login` and `bash` — i.e. an **interactive console
  session**. An idle console with nobody logged in stops promptly; the wait appears
  when someone is (or was) on ttyGS0. This is why the delay is intermittent and why
  it correlates with having just used the serial console.
* `pam_systemd(login:session): Failed to release session: Connection timed out`
  appears just before it, so the session scope is part of what holds the group open.

The blinking cursor is the panel's framebuffer with the console already stopped and
nothing left to draw. It is **not** a hang: the kernel is alive and running the
shutdown sequence, and the poweroff does complete on its own.

## Is it a bug?

Yes — a small but real one. Nothing is gained by waiting 90 s for a debug console,
and the waiting period is indistinguishable from a hang to anyone watching the
screen. It also delays every cold-boot test in this repo by up to a minute and a
half, which is exactly the kind of thing that gets mistaken for a hardware fault.

## Fix (2026-09-26): the unit is removed, not shortened

The interim fix was `TimeoutStopSec=3` in `[Service]`. That is superseded: **the
unit is deleted**, because shortening the wait still cost a visible pause on every
poweroff and the console it served is gone anyway.

Both serial debug consoles were removed on the owner's instruction (see
[the boot console block](BOOT_CONSOLE_BLOCK.md)) and the tablet is reached over
ssh, so an autologin getty on ttyGS0 has no reason to exist. Three things had to
change together, and leaving any one of them out would have kept the delay:

1. `rootfs-overlay/usr/lib/systemd/system/gts9-acm-getty.service` — **deleted**.
2. `rootfs-overlay/usr/libexec/gts9-enable-units` — removes the enable link *and*
   masks the name, so an upgraded rootfs cannot resurrect it. This matters more
   than it looks: `/etc/systemd/system/` wins over `/usr/lib/`, and the section
   below records the two copies having diverged once. That is not hypothetical —
   during the physical test a 2142-byte `/etc/systemd/system/gts9-acm-getty.service`
   was *still running the getty* after the overlay had been replaced, which is why
   the first shutdown measurement after the change was still ~90 s. The helper now
   uses `ln -sfn /dev/null` unconditionally (what `systemctl mask` does) instead of
   a `[ ! -e … ]`-guarded `ln -s`.
3. The unit's enable link is removed, since a dangling link in
   `multi-user.target.wants` is a boot-time failure rather than a no-op.

`getty@tty1.service` is deliberately untouched: tty1 is the panel VT, the only
console left, and the local login on it is how the tablet is used with no cable.

### Measured

```
# before: the 90 s wait is TimeoutStopSec
[   89.403289] systemd[1]: Stopping session-1.scope - Session 1 of User root...
[  179.543765] systemd[1032]: Reached target shutdown.target - Shutdown.
gts9-acm-getty.service: State 'stop-sigterm' timed out. Killing.
gts9-acm-getty.service: Failed with result 'timeout'.

# after: 0.82 s, verified with a one-shot probe on shutdown.target
shutdown_requested_uptime=118.56     (/var/log/gts9-shutdown-probe)
uptime_seconds=119.04                (/var/log/gts9-last-poweroff-stage)
journalctl -b -1 | grep -c 'Stopping timed out'  ->  0
```

### `poweroff` restarts when USB is attached — expected, not a regression

On this board, with the USB cable connected to a host, the tablet powers itself
back on after a `poweroff`. The owner confirmed this is **stock behaviour**; the
original system does the same.

It has to be recorded here because it changes how the fix must be measured:
**"the tablet stayed off" is not a success criterion while the cable is
attached.** Both readings above come from the tablet's own journal timestamps
rather than from watching the USB link, because the gadget is torn down during
shutdown either way — a hung shutdown and a completed-then-restarted one look
identical from the host.

## Provenance of the fix

The unit existed in two places on the tablet, and `/etc/systemd/system/` wins:

```
FragmentPath=/etc/systemd/system/gts9-acm-getty.service
```

while the repo's `rootfs-overlay/` installs to `/usr/lib/systemd/system/`. They had
**diverged** (the `/etc/` copy was an older, larger file). That divergence is why
`gts9-enable-units` now masks the name outright instead of only removing the enable
link, and it is worth remembering when changing any unit here again.
