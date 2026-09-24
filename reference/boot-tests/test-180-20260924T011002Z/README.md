# Test 180 — X710 power key: backlight-only short press, long press untouched

**Status:** PASS.  `HandlePowerKey=blank` is not a valid logind action and was
recorded as such; the daemon now toggles the panel backlight on a short press,
ignores a long hold, finds the key by capability, keeps its state in `/run`,
and passed an automated 30-cycle stress test plus the owner's physical
short/long presses.  No DPU, vblank, workqueue or RCU error was produced.

Device SM-X710 / gts9wifi, Debian 13 on `/dev/mmcblk1p1`, Type-C attached,
runs 2026-09-24 00:48Z – 01:10Z.

## 1. logind cannot blank the screen

`HandlePowerKey=blank` (the policy the bring-up plan asked for first) is not
accepted by systemd 257.13-1~deb13u1.  The drop-in was installed and
`systemd-logind` restarted; the journal records:

```text
systemd-logind[800]: /etc/systemd/logind.conf.d/60-gts9-power-key.conf:2: Failed to parse HandlePowerKey=blank, ignoring: Invalid argument
```

The man page lists the accepted values: `ignore`, `poweroff`, `reboot`, `halt`,
`kexec`, `suspend`, `hibernate`, `hybrid-sleep`, `suspend-then-hibernate`,
`sleep`, `lock`, `factory-reset`, `secure-attention-key` — there is no `blank`.
Note the failure mode: the *invalid* value is ignored and logind falls back to
its built-in default, which is `poweroff`.  That is why the policy must be
`ignore` and the work must be done by the helper: a typo here would power the
tablet off.

`gts9-logind-blank.log` / `pk-*-*.log` captures: `host-captures/logind-blank.log`,
`host-captures/logind-restore.log`.

## 2. Two daemon bugs found and fixed

Both were latent in the version committed as `4db6969`/`0717dc9` and are fixed
in `usr/libexec/gts9-power-key.c`:

1. **`--toggle` never ran.**  `_start` was a naked function that branched
   straight into `gts9_main`, but the arm64 ELF loader zeroes `x0`
   (`ELF_PLAT_INIT`), so `argc` was 0 and `argv[1]` was never seen: the helper
   silently fell through into the key-watch loop instead of toggling once.
   That also explains the "the toggle hung the tablet" observation in test 178:
   the shell was blocked inside an endless `read()` loop, not a DPU hang.  The
   entry point now loads `argc`/`argv` from the initial stack
   (`ldr x0, [sp]` / `add x1, sp, #8`), verified on hardware:

   ```text
   gts9-power-key: argv1=--toggle
   gts9-power-key: screen off (backlight off, system keeps running)
   ```

2. **`EVIOCGBIT`/`EVIOCGNAME` were malformed.**  The `_IOC` macro had the type
   and nr fields swapped, so every capability ioctl returned `-EINVAL` and the
   capability scan found no key at all:

   ```text
   gts9-power-key: diag /dev/input/event0 ev_rc=-22 ev=0x0 key_rc=-22 keypower=0 sysfs_keypower=1 name=
   ```

   With `_IOC(dir, type, nr, size)` fixed (`type` at bits 8-15, `nr` at bits
   0-7), the same line becomes:

   ```text
   gts9-power-key: diag /dev/input/event0 ev_rc=8 ev=0x3 key_rc=15 keypower=1 sysfs_keypower=1
   ```

   The daemon now cross-checks the same capability through
   `/sys/class/input/eventN/device/capabilities/key`, so neither path is a
   single point of failure.

## 3. Behaviour now

| Action | Result |
|---|---|
| Short press (< 1.2 s) | Backlight off; second short press restores the remembered level |
| Long press (>= 1.2 s) | Ignored by the daemon: the PMIC's forced power-off stays the owner of a hold |
| `systemctl suspend` | Unchanged, still the manual suspend interface |
| Power off | Unchanged (`shutdown`/`poweroff`, test 179) |

Implementation points, all verified on the device:

* the key device is chosen by capability (`EV_KEY` + `KEY_POWER`), never by
  event number, and the device is **not** grabbed (`EVIOCGRAB` is absent), so
  logind and a future desktop session still see the key;
* the decision is made on **release**, comparing the event timestamps against
  `LONG_PRESS_MICROSECONDS 1200000`, so a hold cannot blank the screen on the
  way down;
* only `/sys/class/backlight/ae94000.dsi.0/bl_power` and `brightness` are
  written — `fb0/blank` stays 0 through every test, i.e. no DPU modeset;
* state lives in `/run/gts9-power-key/` (`last-brightness`, `display-off`) so
  no microSD write happens per key press;
* if the backlight node is missing the helper logs and does nothing: never
  `fb0/blank`, never suspend.

Installed helper: sha256
`db803a74c5bbc30d74d224a5b33f436b1ab9e00a0a8967931ec16055f77d1296`
(12120 bytes, static freestanding aarch64).  The 30-cycle stress test and the
physical key test were first run on `346467269e3f9c01eb69cfd6ce53138b6bc9d455be1654685266cb9e09603bf4`,
which differs from the installed build only in the wording of the
service-start log line; the stress run was then repeated on the installed build
(`host-captures/pk-stress-final.log`).
The previous (framebuffer-blanking) helper is preserved on the tablet as
`/tmp/gts9-power-key.old`
(sha256 `0981937707ec6491b26b938f1af19a92cd0a24f07f8e093bb3a33ba50e475950`).

## 4. Automated 30-cycle stress test

```text
dmesg -C
/usr/libexec/gts9-power-key --stress 30
```

Result on the installed build (`host-captures/pk-stress-final.log`):

```text
20:05:22 UTC  start
20:06:23 UTC  rc=0                   (61 s, 30 off/on cycles)
dmesg: 30x "screen off", 30x "screen on"
dmesg: 0 dpu / vblank / workqueue / rcu_preempt matches
bl=0 br=2047 fb0=0                   screen ends on, framebuffer untouched
/run/gts9-power-key/last-brightness  display-off removed after the last "on"
systemctl is-system-running: running
```

The earlier run on the previous build gave the same result
(`host-captures/pk-stress30.log`), including `fd 3 -> /dev/input/event0` for
the one daemon process that owns the PMIC key.

## 5. Physical power-key test (owner)

dmesg after the owner pressed the key (`host-captures/pk-physical.log`):

```text
[ 1402.798817] gts9-power-key: screen off (backlight off, system keeps running)
[ 1407.810496] gts9-power-key: screen on (backlight restored)
[ 1412.721496] gts9-power-key: screen off (backlight off, system keeps running)
[ 1415.180495] gts9-power-key: screen on (backlight restored)
[ 1418.245899] gts9-power-key: screen off (backlight off, system keeps running)
[ 1421.359411] gts9-power-key: screen on (backlight restored)
[ 1427.752280] gts9-power-key: long press ignored (PMIC owns it)
```

The long hold produced no toggle.  Final state `bl=0 br=2047 fb0=blank=0`,
`/run/gts9-power-key/` holding only `last-brightness`, `pgrep -c
gts9-power-key` = 1, one process on `/dev/input/event0`, and zero
DPU/vblank/workqueue/RCU errors.  No suspend was entered at any point
(`journalctl -k` has no `PM: suspend entry`).

## 6. Host tests

`tests/test_debian_power_key.py` now also covers the short/long split, the
capability scan, the `/run` state, the stack-based `_start` (regression test
for the bug above), the missing-backlight path and `O_CREAT` for the state
files: 12 tests, all passing.

## Reproducing on the tablet

```sh
/usr/libexec/gts9-power-key --diag      # what the capability scan sees
/usr/libexec/gts9-power-key --toggle    # one off/on transition
/usr/libexec/gts9-power-key --stress 30 # 30 cycles, ~60 s
```
