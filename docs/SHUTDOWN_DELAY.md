# The 90-second delay before poweroff completes

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

## Fix

`TimeoutStopSec=3` in `[Service]` of `gts9-acm-getty.service`. The console is a wired
debug port and any shell on it is gone by the time the system stops, so shortening
the wait loses nothing; 3 s is still enough for agetty to exit cleanly when it can.

**Placement matters and was got wrong first:** the directive was initially added
under `[Unit]`, where systemd silently ignores unknown keys, so
`systemctl show -p TimeoutStopUSec` kept reporting `1min 30s`. It must be in
`[Service]`. Verified after the move:

```
$ systemctl show gts9-acm-getty.service -p TimeoutStopUSec
TimeoutStopUSec=3s
```

## Provenance of the fix

The unit exists in two places on the tablet, and `/etc/systemd/system/` wins:

```
FragmentPath=/etc/systemd/system/gts9-acm-getty.service
```

while the repo's `rootfs-overlay/` installs to `/usr/lib/systemd/system/`. They had
**diverged** (the `/etc/` copy was an older, larger file). The fix was applied to the
repo's overlay copy and pushed to `/etc/`, so both now carry it; the divergence is
worth remembering when changing this unit again.

## Not investigated

Whether `Restart=always` also contributes, by scheduling a restart during shutdown.
The unit stops cleanly enough with the shorter timeout that it was not pursued, and
the observed 90 s matches `TimeoutStopSec` exactly, which is the simpler explanation.
