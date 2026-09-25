# Why one shutdown took ~3 minutes and the next took ~1 second

Measured 2026-09-25 on the same kernel, same unit set, same USB configuration. The
question came from the operator watching the panel: after
`Broadcast message from root@gts9: The system will reboot now!` the tablet appeared
to sit there for minutes. The next reboot, minutes later, finished in seconds.

## The three timings

| reboot | uptime at shutdown | shutdown (first stop → device gone) | trigger → next boot running |
|---|---|---|---|
| test-188 round 1 (clean reference) | ~300 s | — | **41 s** |
| this one, at 02:35:05 | **2936 s** | ~1 s of systemd, then **~178 s** | **194 s** |
| this one, at 02:39:46 | ~70 s | **1.07 s** | a few seconds (operator) |
| test-188 round 5 (clean reference) | ~400 s | — | 41 s |

The 41 s figure is the normal one and comes from the test-188 round records:
"triggered at 01:14:37", and the post-round probe at 01:20:18 reported
`UP=299.85`, so the new boot began at 01:15:18.

## What the evidence rules out

**It is not the services.** On the fast reboot the whole stop phase is visible with
host timestamps:

```
02:39:46.253  Stopping session-1.scope            <- shutdown begins
02:39:47.029  Stopped gts9-adbd.service            <- 32 ms after it was asked
02:39:47.031  Stopped ssh.service
02:39:47.051  Stopped gts9-usb-acm.service
02:39:47.160  Reached target reboot.target
02:39:47.321  device gone
```

`gts9-adbd.service` — the newest unit, and the obvious suspect — stops in **32 ms**.

**It is not systemd's part of the shutdown.** Comparing the slow boot's journal with
a known-clean one, the systemd phase is the same to within 20 ms:

| | slow boot (`-1`, fd68fa9c) | clean boot (`-2`, 300173a4) |
|---|---|---|
| first `Stopping` → `reboot.target` | 2935.68 → 2936.19 = **0.51 s** | 398.23 → 398.72 = **0.49 s** |
| `systemd-shutdown: Syncing filesystems` | 2936.268 (+0.08 s) | 398.828 (+0.11 s) |
| `systemd-shutdown: Sending SIGTERM` | 2936.549 (+0.36 s) | 399.043 (+0.32 s) |

Both journals end at that same line, because journald is one of the processes being
killed at that point. **The journal cannot see past it in either case**, so the
difference is entirely in what happened after.

**It is not dirty data or a slow card.** Measured on the device immediately after:

```
/dev/mmcblk1p1  ext4  rw,noatime
sync on an idle system                     0.109 s
sequential write, 256 MiB with fsync       41.0 MB/s
Dirty:  848 kB     Writeback: 0 kB
```

Flushing 153 s worth of data at 41 MB/s would need about 6 GB dirty; there was
under 1 MB. The filesystem is not the bottleneck.

**It is not a stuck task or a stalled CPU.** The profile arms the detectors itself
and says so at 4.76 s of every boot —
`gts9-watchdog-debug: armed=1 softlockup=1 hung_task=1 wq=45 panic=10`. So
`hung_task_panic=1` with a **45 s** timeout and `softlockup_panic=1` with a **20 s**
threshold were both live. Neither fired, and the journal of the slow boot contains
no hung task, no `mmc` timeout, no RCU stall, no soft lockup and no OOM. **No task
was blocked for 45 s and no CPU was stuck for 20 s.**

**It is not the boot after the reset.** At 02:38:03, 178 s after the reboot was
issued, the host opened COM19 successfully. That port only exists while Debian is
running, because `gts9-usb-acm` creates the gadget from userspace — it does not
exist in ABL, in the bootloader, or during early kernel init. So the machine was
still in Linux with the gadget up at that moment, and the delay sits **before**
`reboot(2)`, not after it.

## What that leaves

The delay is between `systemd-shutdown`'s `Sending SIGTERM to remaining
processes...` and the actual `reboot(2)`: its remaining-process kill, its unmount
of what is left, or the reset itself. Nothing in the kernel's own detectors
classified it as a stuck task, so it is a **wait**, not a wedge.

And it scales with **uptime**, not with the software:

* 2936 s of uptime → ~178 s of waiting;
* 70 s of uptime → 0.16 s from `reboot.target` to the device disappearing.

That is the one clean correlation in the data, and it is what the next measurement
should attack.

## The next measurement, and why it will answer it

`systemd-shutdown` prints its progress to `/dev/console`, which includes `tty0`
(the panel) and `ttyGS1` (COM19) — `Sending SIGKILL to remaining processes...`,
`Unmounting file systems.`, `All filesystems unmounted.`, and so on. Those lines are
the missing evidence, and they were not captured because the console loglevel was
left at 4.

`reference/boot-tests/test-187-*/shutdown-capture.sh` already does exactly the
right thing: it raises the console loglevel with `echo 8 > /proc/sys/kernel/printk`,
then holds COM19 open across the shutdown. The protocol for the next attempt:

1. let the tablet stay up for **at least 40 minutes** (the slow case had 49);
2. `GTS9_ALLOW_POWER=1 .../shutdown-capture.sh` — it raises the level, watches
   COM19, and issues the reboot itself;
3. read which `systemd-shutdown` line is last, and how long after it the device
   goes away.

Whichever line it stops on names the step: a kill wait if it stops before
`Sending SIGKILL`, an unmount wait if it stops at `Unmounting file systems`, and
neither if it reaches `Rebooting.` — in which case the wait is in `reboot(2)` or the
reset path rather than in systemd.

## What this does not say

* It does not implicate the debug-channel work. That work added adbd, sshd
  traffic, the NCM function and six packages — and the *fast* reboot was taken with
  all of them installed and running, from the same boot of the same kernel.
* It does not connect this to the shutdown stall in
  `docs/STALL_FAILURE_SHAPE.md` §5. That failure never reached `reboot.target` and
  was ended by an external reset; this one passed `reboot.target` normally. They
  are different points in the shutdown, and the relationship is unknown.
* It does not establish the mechanism. Uptime correlation with n=2 (one slow, one
  fast) is a lead, not a result; a third long-uptime reboot is needed before
  anything is claimed about it.
