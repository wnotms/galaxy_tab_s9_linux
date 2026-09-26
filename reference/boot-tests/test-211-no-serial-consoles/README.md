# test-211: the serial debug consoles are gone — boot and shutdown no longer stall

Both serial debug consoles were removed from the kernel and the userspace, and
the tablet is now reached over ssh. This is the physical verification. Raw
evidence in `EVIDENCE.txt`.

## What was changed

| | before | after |
|---|---|---|
| kernel command line | `console=ttyMSM0,115200n8 … console=tty0 … console=ttyGS1` + `earlycon` + ABL's `console=null` | **`console=tty0`** and nothing else |
| `/sys/class/tty/console/active` | `tty0 ttyMSM0 ttyGS1` | **`tty0`** |
| kernel consoles enabled | `tty0`, `sec_log`, `ramoops`, `ttyMSM0`, `ttyGS1` | `tty0`, `sec_log`, `ramoops`, **`ttynull0`** |
| `CONFIG_U_SERIAL_CONSOLE` | `=y` | **not set** |
| `CONFIG_SERIAL_QCOM_GENI_CONSOLE` | `=y` | **not set** (`SERIAL_QCOM_GENI` stays `=y`) |
| `CONFIG_NULL_TTY` | not set | **`=y`** |
| `gts9-acm-getty.service` (ttyGS0 autologin) | enabled, active | **removed; masked** |
| serial getty instances | ttyMSM0 masked | **ttyMSM0 and ttyGS0 both masked** |
| the way in | USB ACM serial console (COM19), ~3 KB/s | **ssh over the NCM link, 169.254.42.1** |

## Results

| measurement | before | after |
|---|---|---|
| 60 KB written to `/dev/console` with nothing draining it | **blocked for the full timeout** | **0.006 s** |
| `poweroff` → shutdown complete | **90 s** `TimeoutStopSec` (`Stopping timed out. Killing.`) | **0.82 s**, zero stop timeouts |
| stop timeouts in the shutdown journal | `session-1.scope: Stopping timed out`, `gts9-acm-getty.service: Failed with result 'timeout'` | **0** |
| warm reboot → ssh answering | — | **40 s** |
| `dmesg` ring | 99.98 % one repeated ADSP line (Fedora issue 19) | **1077 lines, 0 occurrences** of it |
| failed units | 2 (after mask change, see below) | **0** |

### The original reproduction, run on the tablet

```
$ time sh -c 'head -c 60000 /dev/zero | tr "\0" "z" > /dev/console'
real    0m0.006s
```

`docs/BOOT_CONSOLE_BLOCK.md` measured this command blocking for the full timeout
and completing only the instant COM19 was opened. It now returns immediately,
because `/dev/console` can no longer resolve to a port that blocks:
`console_device()` walks the console list in order and `tty0` has
`CONFIG_VT`-style `device()` while `ttynull` absorbs ABL's appended
`console=null`. `ttynull_write()` returns `count` without waiting for anything.

### The shutdown measurement, exactly

The decisive numbers, both from the tablet's own journal rather than from the
host, so a lost USB link cannot be mistaken for a completed shutdown:

```
# the boot that still had the getty - 90 s wait
[   89.403289] systemd[1]: Stopping session-1.scope - Session 1 of User root...
[  179.543765] systemd[1032]: Reached target shutdown.target - Shutdown.
session-1.scope: Stopping timed out. Killing.
gts9-acm-getty.service: Failed with result 'timeout'.

# the boot with the getty removed - 0.82 s
/var/log/gts9-shutdown-probe      shutdown_requested_uptime=118.56
/var/log/gts9-last-poweroff-stage uptime_seconds=119.04
journalctl -b -1 | grep -c 'Stopping timed out'  ->  0
```

A one-shot `gts9-shutdown-probe.service` armed on `shutdown.target` recorded the
monotonic uptime when the shutdown path began (118.56 s) and the existing
`gts9-poweroff-stage` recorder the instant systemd reached the poweroff service
(119.04 s). The delta is the shutdown itself. The probe was removed afterwards
and is not part of the shipped overlay.

### `poweroff` looks like a reboot when USB is attached — expected, not a defect

The owner reported this and it is **stock behaviour on this board**: with the USB
cable connected to a host, the tablet powers itself back on after a `poweroff`.
The original system does the same.

This matters for how the measurement above has to be read, so it is recorded
explicitly: **"did the tablet stay off?" is not a success criterion while the
cable is attached.** Every poweroff in this test came back on by itself, which is
why the evidence for the shutdown is the journal's own monotonic timestamps and
`Reached target poweroff.target` — a shutdown that completes and is then
followed by an automatic power-on is still a completed shutdown, and a shutdown
that hangs never reaches `poweroff.target` at all. Judging by whether the link
disappeared would have been ambiguous, because the USB gadget is torn down
during shutdown either way.

## What each removed console was, and why

* **`console=ttyGS1`** (USB ACM, host COM19) — the boot stall.
  `n_tty_write()` sleeps in `wait_woken()` on `tty->write_wait` once the gadget's
  8 KiB `port_write_buf` is full and nothing drains the host side, so *any*
  userspace `write()` to `/dev/console` stopped the boot. `printk` was never the
  blocker: `gs_console_write()` is lossy by design and measured 0.048 s for 5000
  lines with COM19 closed. `CONFIG_U_SERIAL_CONSOLE` is what let
  `gserial_alloc_line()` register a console on the port at all, so unsetting it
  removes the mechanism instead of relying on userspace never writing to
  `/dev/console`.
* **`console=ttyMSM0`** (SoC GENI UART) — the second of the two the owner asked
  to remove. Nothing is wired to it, so it never stalled a boot by itself, but
  each `console=` argument also costs a `systemd-getty-generator` unit and a
  `dev-ttyMSM0.device` dependency that had to be masked by hand.
* **`gts9-acm-getty.service`** (`agetty --autologin root ttyGS0`) — the 90 s
  poweroff. `--autologin` spawns a login shell that agetty does not reap on
  `SIGTERM`, so the unit's cgroup stayed populated and systemd waited out
  `TimeoutStopSec`. It is deleted from the overlay rather than shortened.
* **`earlycon`** and **`ignore_console_null`** — dropped with the consoles they
  belonged to. Patch `0003` (`ignore_console_null`) moved to `pending/`, so
  `kernel/printk/printk.c` is unmodified upstream again; `CONFIG_NULL_TTY=y`
  absorbs the appended `console=null` instead.

## Follow-up, same day: one serial port instead of two

The owner then asked for the two virtual COM ports to be removed, and - asked
whether either could still affect boot or shutdown - the answer measured on the
tablet was **no**, so one port was kept.

Why neither could still stall anything, checked rather than argued:

| path that caused the hangs | state |
|---|---|
| printk → ttyGS | `console=ttyGS` tokens in cmdline: **0**; `console_active=tty0` |
| userspace `write()` → ttyGS | `ttygs_open_fds=0` — nothing has either port open |
| login → ttyGS | both getty names **masked**, `inactive` |

The source-level reason is stronger than the runtime check: with
`CONFIG_U_SERIAL_CONSOLE` unset, `gs_console_init()` in
`drivers/usb/gadget/function/u_serial.c` is compiled to `return -ENOSYS`, so no
ttyGS port can *become* a console on this kernel — the capability is gone, not
merely unused.

So `acm.usb1` was removed and `acm.usb0` kept:

* `acm.usb1` existed for exactly one purpose — to be the port printk registered on
  (it was created second so u_serial handed it line 1). With the gadget console
  gone it was a dead port.
* `acm.usb0` stays as one plain serial port: not a console, no getty, so nothing
  writes to it and nothing can block on it. It is a wired endpoint that does not
  depend on the network function having bound.

Measured after the change: `gadget_functions=acm.usb0 ncm.usb0`, `/dev/ttyGS1`
absent, `/dev/ttyGS0` present, warm reboot → ssh in **45 s**, and
**poweroff 48.02 → 48.69 s = 0.67 s with zero stop timeouts** — unchanged from the
0.82 s measured before, which is the point: removing the port cost nothing and
bought nothing either way.

The migration is not a manual step: `configfs` cannot edit a bound gadget's
function set, so `gts9-usb-acm` unbinds, drops `acm.usb1` and rebuilds. It is a
no-op once the port is gone, so it costs one service restart exactly once.

### A stale autologin drop-in was found and removed

The device-state recorder (below) reported
`autologin_files=/etc/systemd/system/serial-getty@ttyGS0.service.d/autologin.conf`.
That file's entire content is an `agetty --autologin root` override, left by an
earlier install. It was inert only because the instance it decorates is masked —
a live configuration file waiting for anyone who unmasks the name, which is
precisely how this class of leftover returns. `gts9-enable-units` now removes it,
and reports the directory gone:

```
before: autologin_files=/etc/systemd/system/serial-getty@ttyGS0.service.d/autologin.conf
after : autologin_files=none
```

## On-device changes are recorded

Because flashed partitions and hand-written device configuration are invisible to
`git status` on the host and to `git log` on the tablet, the repository now ships
`gts9-device-changes`, which prints what a device actually has. It is read-only
unless asked to write, so a before/after pair can be diffed.

Its value was immediate rather than theoretical: on its first run against the
tablet it reported the stale autologin drop-in and `acm.usb1` in one line each.
Before/after records for this deployment are kept in
[`reference/device-state/`](../../device-state/README.md).

## Also fixed here, found while deploying

Two pre-existing bugs surfaced during the physical test and are fixed:

1. **`gts9-prev-boot-evidence.service` and `gts9-watchdog-debug.service` failed
   with `status=203/EXEC`** after an overlay-tarball deploy: `tar` preserves the
   stored mode, and those helpers (plus `gts9-kmsg-console` and
   `gts9-journal-survey`) were committed mode `0644`. The direct-install path was
   never affected because `install -D -m 0755` set the mode, so this only broke
   the TWRP/tarball route — the one used on the tablet. All four are now
   `100755` in git, and `tests/test_debian_rootfs_installer.py` asserts it.
2. **`gts9-enable-units` skipped the mask when a stale file existed** at the
   target name (`[ ! -e … ]` guard). `/etc/systemd/system/` wins over
   `/usr/lib/`, and this repository's own notes record the two copies having
   diverged once — which is exactly what was found on the tablet: a 2142-byte
   `/etc/systemd/system/gts9-acm-getty.service` was still running the getty
   after the overlay was replaced. The helper now uses `ln -sfn` unconditionally,
   which is what `systemctl mask` does.

## Not proven here

* **The panel console.** `console=tty0` is enabled and `fbcon` binds the DRM
  framebuffer, but this test read the tablet over ssh throughout; nobody has
  confirmed with their eyes that the boot log renders on the panel after this
  change. The panel was verified working in tests 040/191.
* **A true cold boot.** Every power cycle here was followed by the automatic
  power-on described above, so "cold start" below means "USB re-attached and the
  board re-initialised", not "battery removed". `wlp1s0` enumerated and scanned
  (20 BSS) after it, so the WCN6855 cold-handoff path (patch `0008`) still works.
* **Wi-Fi association and traffic.** The scan works and the endpoint enumerates;
  no association or transfer was repeated in this test. Tests 208-210 cover that
  and nothing here touches the wireless stack.
