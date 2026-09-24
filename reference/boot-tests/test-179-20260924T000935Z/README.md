# Test 179 — shutdown vs poweroff A/B on the X710

**Status:** PASS for all five power-off entry points.  One `vendor_boot`
rebuilt and flashed (read-back verified); `boot`, `init_boot`, `dtbo` and
`vbmeta` untouched.  Physical runs 2026-09-24 00:09Z – 00:47Z, device SM-X710 /
gts9wifi, Type-C attached to the host, Debian 13 on `/dev/mmcblk1p1`.

Source revision at the start: `0717dc9` (branch `test`), plus the uncommitted
test tooling added by this run.

## Question

The owner reported that `shutdown` physically powers the tablet off while
`poweroff` stops with the cursor still blinking.  The first job was therefore
not to change anything, but to establish what each entry point actually is and
to reproduce the difference from fresh boots.

## All four entry points are one program

Recorded over COM17 before any change (`host-captures/resolve.log`):

```text
shutdown is /usr/sbin/shutdown
shutdown is /sbin/shutdown
poweroff is /usr/sbin/poweroff
poweroff is /sbin/poweroff
/sbin/poweroff   -> ../bin/systemctl
/sbin/shutdown   -> ../bin/systemctl
/usr/sbin/poweroff -> ../bin/systemctl
/usr/sbin/shutdown -> ../bin/systemctl
2c2515eeb6b923cbb70bee173180bf3d  /sbin/shutdown
2c2515eeb6b923cbb70bee173180bf3d  /sbin/poweroff
```

systemd 257.13-1~deb13u1; the `shutdown(8)` man page on the device documents
`-P/--poweroff` as "the default" action.  So `shutdown`, `shutdown -P now`,
`shutdown now`, `systemctl poweroff` and `poweroff` all select
`poweroff.target` through the same binary: a difference in outcome cannot come
from a different command implementation.

## Image under test

| Partition | Before | After | Written |
|---|---|---|---|
| `boot` (sda21) | `822ca9dcf404de83e79f085a5509ec761bf0234359a5fae166c5d1c849e1df86` | unchanged | no |
| `init_boot` (sda22) | `9985eeef89844a6018d4664fdf4d52f89d3d7ab7d7dcef7c53d08dba08ce5834` | unchanged | no |
| `vendor_boot` (sda24) | `1abb4c68b8103020d7935f5057225abe1e6b6b2222f58a6e93e254eb851af27c` | `3c88b36b7b3f1703ccd751b77522fa6d16596650e627893e3131848c96731dec` | yes, read back verified |
| `dtbo` (sda30) | `c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3` | unchanged | no |
| `vbmeta` (sde15) | unchanged | unchanged | no |

The flashed kernel was already a `GTS9_POWEROFF_TRACE=1` build.  The rebuilt
`vendor_boot` changes only the vendor command line, appending
`console=tty0 gts9_poweroff_trace=1` to the exact minimal cmdline that was in
the partition.  The build is reproducible byte for byte: rebuilding the
*unchanged* cmdline reproduced the flashed `vendor_boot` hash `1abb4c68…`
exactly before the instrumented one was built (`bundle-repro3/SHA256SUMS`).

Flash procedure (`flash-write-readback.txt`), from TWRP entered with
`gts9-debian-to-recovery --yes` over COM17:

```text
host sha256 of pulled backup : 1abb4c68…   (matches the Debian-side read of /dev/sda24)
pushed image sha256 on device: 3c88b36b…
host sha256 of pulled readback: 3c88b36b…  PASS
device sha256 of the partition: 3c88b36b…  PASS
```

Host staging directory:
`/home/ms/Samsung/gts9-flash-tests/test-179-20260924T000935Z/`
(`vendor_boot-before.img`, `vendor_boot-after.img`).

## Console and kernel-message sinks on the image

```text
/proc/consoles
tty0        -WU (EC     )    4:1     <- /dev/console, visible on the panel
ttyMSM0     -W- (E   p  )  237:0     <- not wired out
sec_log-1   -W- (E   p a)            <- 2 MiB reserved ring, TWRP /proc/last_kmsg
```

`gts9-power-key.service` was stopped for the run (unit still enabled) and
logind carries `HandlePowerKey=ignore`, so a stray short power press cannot
toggle the framebuffer while the tablet is being observed.

## Results

Every run starts from a fresh boot, records the `boot_id` before the command,
sends the command with the host watcher armed, and then checks the physical
outcome.

| Test | Command | `boot_id` before | USB gone → back | gap | `boot_id` after | `lpcharge=1` | Result |
|---|---|---|---|---|---|---|---|
| P4 | `poweroff` | `60fb1021-bec…` | 00:32:33.6 → 00:32:43.0 | 9.4 s | `bec55a95-7c69…` | 13 params | PASS |
| P1 | `shutdown -P now` | `bec55a95-7c69…` | 00:35:16.6 → 00:35:24.8 | 8.3 s | `84a628e5-93d9…` | 13 params | PASS |
| P2 | `shutdown now` | `84a628e5-93d9…` | 00:38:14.0 → 00:38:22.4 | 8.4 s | `6ae34442-12cc…` | 13 params | PASS |
| P3 | `systemctl poweroff` | `6ae34442-12cc…` | 00:41:11.9 → 00:41:20.1 | 8.2 s | `a4a65a66-2d85…` | 13 params | PASS |
| P5 | `shutdown` | `a4a65a66-2d85…` | 00:45:09.2 → 00:45:17.4 | 8.2 s | `42efa64f-ef35…` | 13 params | PASS |

Full host captures: `host-captures/ab-p*-watch.log`, `host-captures/ab-p*-probe.log`,
`ab-results.txt`.

### Why this is a real power off

1. **The owner watched it.**  For P4: the panel went completely dark, then the
   charging screen appeared, then the tablet restarted.  A restart with Type-C
   attached is normal Samsung behaviour after a power off, not a failure.
2. **The bootloader says so.**  The next boot's own command line carries
   `lpcharge=1` in 13 parameters — an LPM/charger-triggered start.  Every plain
   reboot in the same session (TWRP `reboot system`, the owner's forced restart)
   carried `lpcharge=0`.
3. **Userspace completed the sequence.**  Each previous boot's persistent
   journal ends with `Reached target poweroff.target`, `Shutting down.` and
   `systemd-shutdown[1]: Syncing filesystems and block devices.`, and
   `/var/log/gts9-last-poweroff-stage` records the matching `boot_id` and
   uptime.
4. **USB was gone for the whole off period** and came back with a new
   `boot_id`.

### The one real difference: plain `shutdown` waits a minute

P5 is the only entry point that does not act immediately:

```text
00:44:05.697 SENT  shutdown
00:44:06.518 RECV  Shutdown scheduled for Tue 2026-04-14 03:41:54 CST, use 'shutdown -c' to cancel.
00:45:09.173 PRESENCE usb0525:a4a7=False
```

63.5 s from the command to power off — the sysvinit-compatible default of one
minute.  `shutdown -P now`, `shutdown now`, `systemctl poweroff` and `poweroff`
all power off within about three seconds.

## Answer to the original question

* Are `shutdown` and `poweroff` different programs?  No: symlinks to
  `/usr/bin/systemctl`, identical md5.
* Do they select different targets?  No: all four select `poweroff.target`.
* Does the platform have a working power-off path?  Yes, and it works from
  every entry point on this image.
* Was any PSCI/PMIC/PON/SPMI/`pshold` change made?  No.  Nothing in this test
  justifies one, and none was made.
* Why did it look different before?  The "poweroff stops at a blinking cursor"
  observation belongs to an older image and session; test 172 is the record of
  that image, and it also contains boots that stopped at a blinking cursor for
  unrelated reasons (a broken usr-merge and the DSI/panel state).  It does not
  reproduce on the current image set.  The only reproducible difference between
  the commands is the one-minute delay of plain `shutdown`.

## Incident during the run

The first boot after the flash needed one forced restart: the panel stayed on a
cursor screen while the system itself was healthy (userspace reached
`multi-user` at 4.6 s, COM17 answered).  With `console=tty0` the panel now
carries the kernel console as well as tty1, so an early-console screen with a
cursor is expected unless something redraws tty1; the second cold boot came up
normally.  The DSI cold-boot zero panel ID and the recovery cycle behaved as in
test 178 (`panel id: 00 00 00` → `gts9-panel-recover` cycle 1 → `80 00 04`).
One `dpu_encoder_helper_wait_for_irq … encoder is disabled id=35` error is
logged in both boots; it is the known display issue and is tracked separately.

## Reproducing

```sh
# build the instrumented vendor_boot (kernel payload unchanged)
KERNEL_OUT_DIR=$PWD/.work/build/kout-power-trace \
MKBOOTIMG=$PWD/.work/tools/mkbootimg.py AVBTOOL=$PWD/.work/tools/avbtool.py \
scripts/build-boot-bundle.sh --initramfs out/boot-poweroff-trace/initramfs-bringup.img \
  --cmdline reference/boot-tests/test-179-20260924T000935Z/cmdline-power-trace.txt \
  --bootconfig reference/boot-tests/test-179-20260924T000935Z/bootconfig-comments.txt \
  --out out/boot-bundle-power-trace-179

# run one entry point with the host watcher
powershell -ExecutionPolicy Bypass -File scripts/console-watch.ps1 \
  -Out C:\gts9-work\p4.log -Seconds 140 -Command 'poweroff' -CommandAtSeconds 15
```

Render it back to the known-good image with
`vendor_boot-before.img` from the host staging directory (or rebuild the
unchanged cmdline, which reproduces `1abb4c68…` byte for byte).
