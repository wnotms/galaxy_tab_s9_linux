# Why the boot appeared to hang, and why opening COM19 fixed it

**Resolved 2026-09-26.** Both serial debug consoles were removed and the tablet
is now reached over ssh; the reproduction below returns in 0.006 s instead of
blocking, and `poweroff` completes in 0.82 s with zero stop timeouts. See
[test-211](../reference/boot-tests/test-211-no-serial-consoles/README.md) for the
physical verification, and the "Resolution" section at the end of this file for
what changed. Everything above that section is the original investigation, kept
because it is the evidence the fix is based on.

Reported by the operator on 2026-09-25/26, and reproduced here. The symptom is
consistent and the correlation with the console port is absolute:

* after a reboot the panel sits on the boot log for tens of seconds, sometimes
  minutes;
* `getty@tty1` accepts keystrokes **before** logging in; after login the cursor
  freezes, input does nothing, and the power key no longer blanks the screen;
* eventually the screen clears to a lone blinking cursor in the top-left;
* the SoC area gets noticeably warm;
* **opening `COM19` makes it recover immediately** — the login prompt appears.

## The two write paths, and which one blocks

This is the part that is easy to get wrong, and it was got wrong twice during the
investigation, so both paths are recorded with measurements.

| path | mechanism | blocks? |
|---|---|---|
| **kernel printk** → `gs_console_write()` | `kfifo_in()` into an 8 KiB buffer, overflow counted in `cons->missed` and **discarded** | **no** — measured 0.048 s for 5000 lines with COM19 closed |
| **userspace `write()`** → `n_tty_write()` → `gs_write()` | `n_tty_write` waits on `tty->write_wait` via `wait_woken()` until the tty has room | **yes** — 60 KB to `/dev/console` blocked for the full timeout, and completed the instant COM19 was opened |

So `printk` is lossy by design and can never be the blocker; **the blocking writer is
a userspace `write()` to `/dev/console`.** That distinction is the whole diagnosis.

## Why `/dev/console` is COM19

The command line lists four `console=` arguments, and the kernel gives
`/dev/console` to the **last one that registers successfully**:

```
console=ttyMSM0,115200n8 ... console=tty0 ... console=ttyGS1 console=null
/sys/class/tty/console/active:  tty0 ttyMSM0 ttyGS1
```

`ttyGS1` is the second USB ACM interface — **COM19** on the host. `console=null` is
dropped by the `ignore_console_null` patch (kernel patch `0003`), which is why
`ttyGS1` ends up last and wins.

## The writer

`boot/bringup-init.sh` ends PID 1 in an interactive shell bound to that device:

```sh
while :; do
    /bin/sh -i </dev/console >/dev/console 2>&1
    log 'console shell ended or unavailable; PID 1 remains alive, retrying in 5s'
    sleep 5
done
```

Any output from that shell — and any other userspace writer to `/dev/console` —
blocks once the gadget's OUT requests are full and nothing is draining COM19. The
warm SoC is consistent with that: a blocked shell being retried in a loop, not a CPU
spinning in the kernel (load average was **0.05** when measured, and no task was in
`D` state).

## Reproduced, twice, with the causal control

```
# COM19 closed
$ time sh -c 'head -c 60000 /dev/zero | tr "\0" "z" > /dev/console'
  -> blocked for the full timeout

# same command, COM19 opened 5 s later
real 0m5.434s        <- returned the instant the port was opened
```

The operator's shutdown log then showed ~50 KB of `zzzz…` scrolling out **before**
the shutdown messages — that is that same blocked write draining into the port the
moment it was opened, arriving ahead of the queued systemd output. It is a direct
demonstration of the queue, and it is why the log looked so strange.

## What it is not

* **Not printk** — see the table; lossy by design.
* **Not `/dev/kmsg`** — 2000 lines with COM19 closed took 46 ms.
* **Not journald or the journal** — `systemd-journal-flush` is 811 ms and off the
  critical path, even with 839 MB of journal and 93 boots retained.
* **Not the backlight service** — a brightness write with the panel on is 2–3 ms.
* **Not the CPU wedge** — no hung task, no soft lockup, no RCU stall, no panic; the
  detectors are armed on every boot and stay silent.

### Three of my own hypotheses that were wrong

Recorded because each was plausible, cost time, and only measurement disproved it:

1. **"`gts9-prev-boot-evidence.service` with `StandardOutput=journal+console` is the
   blocker."** It contributed — removing it dropped one boot from 101 s to 66 s — but
   it is *one* console writer, not *the* one. The change is kept because its output
   is already in the journal.
2. **"The 839 MB journal makes the boot slow."** Measured and rejected.
3. **"printk is blocking on the un-drained console."** Wrong by design, and the
   operator was right to push back on it.

## The fix

Nothing that runs during boot may write to `/dev/console` while it may resolve to the
USB gadget port, because the resulting stall is indistinguishable from a hang and
nothing in the system can report it.

1. **Keep the PID 1 fallback shell on a local console** (`/dev/tty0` or
   `/dev/ttyMSM0`) rather than `/dev/console`, so it can never block on the gadget.
2. **`gts9-prev-boot-evidence.service` no longer uses `journal+console`** (already
   applied) — one fewer writer on that path.
3. Decide the policy for `console=ttyGS1`: keeping it gives the kernel log on COM19
   from ~5.6 s, at the cost that *any* userspace console write can stall when COM19
   is unread. Dropping it lets `gts9-kmsg-console` mirror `/dev/kmsg` from userspace
   with explicit error handling that cannot wedge PID 1 — the branch it already
   implements ("ttyGS is already a kernel console; not mirroring" is what currently
   makes it step aside).

Item 3 is a real trade-off rather than an obvious fix, so it is recorded as a
decision to make rather than made unilaterally.

## Resolution (2026-09-26)

The decision above was made: **both serial debug consoles are removed** and the
tablet is reached over ssh on the USB network link. The owner asked for exactly
this — remove the two serial consoles and use ssh, so that boot and shutdown
cannot stall.

What was done, and why each half was necessary:

| change | mechanism it closes |
|---|---|
| `console=ttyGS1` dropped; `CONFIG_U_SERIAL_CONSOLE` **unset** | the userspace `write()` block. `gserial_alloc_line()` can no longer call `gs_console_init()`, so no ttyGS port can become a kernel console at all — the failure mode is removed, not avoided. |
| `console=ttyMSM0,115200n8` and `earlycon` dropped; `CONFIG_SERIAL_QCOM_GENI_CONSOLE` **unset** | the second debug console, plus the getty-generator unit and `dev-ttyMSM0.device` dependency that every `console=` argument costs. `CONFIG_SERIAL_QCOM_GENI` stays `=y` (shared SE IP). |
| `gts9-acm-getty.service` **deleted**, and masked by `gts9-enable-units` | the 90 s poweroff, which is a *different* mechanism — see [shutdown delay](SHUTDOWN_DELAY.md). |
| `CONFIG_NULL_TTY=y`; patch `0003` (`ignore_console_null`) retired to `pending/` | ABL's appended `console=null`, which the patch used to delete outright. `ttynull` now absorbs it, so the argument resolves to a real non-blocking tty and `kernel/printk/printk.c` returns to unmodified upstream. |
| PID 1's fallback shell moved off `/dev/console` to `/dev/tty1`, with a bounded fallback | the same blocking-writer shape in the rescue paths (`boot/bringup-init.sh`, `boot/minimal-rootfs-init.sh`, `boot/gts9-minimal-pid1.c`). |
| `/etc/gts9-usb-net` ships in the overlay | the ssh transport. It used to be created by hand, so once the console was gone a freshly installed rootfs would have had no way in at all. |

`/dev/console` now resolves to `tty0` (and to `ttynull` for ABL's appended
argument), and `ttynull_write()` returns `count` without waiting for anything — so
a write to `/dev/console` can no longer block. Measured: the 60 KB reproduction
below, which used to hang for the full timeout, returns in **0.006 s**. Shutdown
completes in **0.82 s** with zero stop timeouts.

### Path 2 (`tty0` → fbcon → DRM) is now the only console, and is bounded

The investigation above only treats the gadget port as the blocker, and correctly
so: **path 2 does not share the property that makes path 1 unbounded.** `fbcon`
writes into the DRM framebuffer, which cannot "fill up" — there is no
`write_wait` to sleep on and no host that has to drain it, so it always makes
progress.

The ~151 s episode in [watchdog X710](WATCHDOG_X710.md) was the same *class* of
problem (a console backlog) but a different cause: it was `journal+console`
duplication over a display path that was itself under investigation. That unit has
been journal-only since, and this change does not alter it.

Removing the gadget console therefore removes the unbounded case. The panel
console is kept deliberately: it is the only console left, and it is what makes a
boot visible on the tablet itself with no cable attached.

## Workaround until then (historical)

**Keep COM19 open across the boot.** Every clean boot-time measurement in this repo
was taken that way, which is exactly why the unheld boots looked so different.
