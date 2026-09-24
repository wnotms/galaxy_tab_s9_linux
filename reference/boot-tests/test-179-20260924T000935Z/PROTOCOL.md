# test-179 — shutdown vs poweroff A/B on the X710 (protocol)

Goal: decide why `shutdown` is reported to power the tablet off while
`poweroff` is reported to stop at a blinking cursor.  Every test starts from a
fresh boot with its own `boot_id`, and is judged by physical state, not by the
command name.

## Image under test

| Item | Value |
|---|---|
| `boot` (sda21) | `822ca9dcf404de83e79f085a5509ec761bf0234359a5fae166c5d1c849e1df86` (poweroff-trace build, unchanged) |
| `init_boot` (sda22) | `9985eeef89844a6018d4664fdf4d52f89d3d7ab7d7dcef7c53d08dba08ce5834` (unchanged) |
| `vendor_boot` (sda24) | `1abb4c68…` → `3c88b36b7b3f1703ccd751b77522fa6d16596650e627893e3131848c96731dec` (flashed, read back verified) |

The only change is the vendor command line: `console=tty0` (so the panel carries
the kernel + systemd-shutdown messages) and `gts9_poweroff_trace=1` (the kernel
in `boot` already contains the trace patch).  `/proc/consoles` on the device
confirms the sinks:

```text
tty0        -WU (EC     )    4:1     <- /dev/console, visible on the panel
ttyMSM0     -W- (E   p  )  237:0     <- not wired out
sec_log-1   -W- (E   p a)            <- 2 MiB ring, TWRP /proc/last_kmsg
```

## Commands, one per fresh boot

| Test | Command | Notes |
|---|---|---|
| P1 | `shutdown -P now` | explicit poweroff |
| P2 | `shutdown now` | sysv form |
| P3 | `systemctl poweroff` | native verb |
| P4 | `poweroff` | compat symlink |
| P5 | `shutdown` | what the owner reports as working (no time argument) |

All four entry points are the same binary: `/sbin/shutdown`, `/sbin/poweroff`,
`/usr/sbin/*` are symlinks to `/usr/bin/systemctl` (identical md5
`2c2515eeb6b923cbb70bee173180bf3d`), and the systemd `shutdown(8)` man page
documents `-P/--poweroff` as the default action.  A difference in outcome is
therefore a difference in *state or sequencing*, not in the program.

## Per-test record

Before the command: `boot_id`, `uptime`, `/proc/cmdline`, `systemctl
is-system-running`, panel state (`fb0/blank`, backlight), and the host watcher
start timestamp.

After the command: host-side COM17 presence transitions (the watcher samples
both the COM port list and the PnP instance), every line received, panel
behaviour (owner), heat (owner), whether a short power press does anything
(owner), whether a long press is required, and the next `boot_id`.

## PASS criteria (physical power off)

```text
USB ACM disappears and stays gone
panel goes completely dark and stays dark
device cools down (not merely "screen off")
short power press does nothing
long power press is required to cold boot
next boot_id differs and /proc/uptime restarts
```

A blinking cursor, a lit panel or a warm device is a FAIL even if COM17 is gone.

## Kernel-level evidence

With the trace enabled, the kernel prints (level `emerg`, so `loglevel=4` does
not filter it) to every registered console:

```text
GTS9_POWER_OFF: kernel_power_off entered
GTS9_POWER_OFF: shutdown preparation complete
GTS9_POWER_OFF: power-off prepare handlers complete
GTS9_POWER_OFF: dispatch legacy pm_power_off=psci_sys_poweroff
GTS9_POWER_OFF: sys-off priority=… callback=…
GTS9_POWER_OFF: sys-off callback returned …
GTS9_POWER_OFF: PSCI SYSTEM_OFF call
GTS9_POWER_OFF: PSCI SYSTEM_OFF returned 0x…
```

The last line is the decisive one: if it is absent the SMC never returned
(platform should have powered off); if it is present with a value, firmware
returned without powering the platform off.  The same lines are written to the
persistent `sec_log` ring, which TWRP exposes as `/proc/last_kmsg` after a warm
reset, as a second independent copy.

## Safety

`gts9-power-key.service` was stopped before the run (`systemctl stop`, unit
still enabled) and `logind` has `HandlePowerKey=ignore`, so a short power press
cannot toggle `fb0/blank` during the observations.  A long press still reaches
the PMIC's forced-power-off path, which is the recovery action.
