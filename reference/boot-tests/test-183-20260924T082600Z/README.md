# test-183 — unattended X710 stall → panic → reboot → evidence rounds

Objective for this round: make a stalled X710 recover **without a human**, and
make every round leave its evidence behind, so `boot → reproduce → stall →
watchdog → reboot → collect evidence → next round` runs on its own.

Everything below was measured on the tablet; the raw logs are next to this file.

## Files

| file | what it is |
|---|---|
| `cmdline-watchdog-debug.txt` | the profile's command line: flashed into `vendor_boot` |
| `bootconfig-comments.txt` | unchanged from test-179 |
| `bundle-compare.txt` | proof that the debug bundle differs from the known-good one only in the cmdline (taken from the cmdline strings inside both images) |
| `flash-watchdog-debug.sh` / `flash-write-readback.txt` | verified flash of the debug cmdline into `vendor_boot` |
| `flash-ramoops.sh` / `flash-ramoops-write-readback.txt` | verified flash of the ramoops boot pair |
| `gts9-stall-loop.sh` / `stall-loop.txt` / `rounds/` | the unattended loop and its per-round records |

Device-side pieces live in the repository overlay, not here:
`rootfs-overlay/usr/libexec/gts9-watchdog-debug` (+ unit),
`gts9-prev-boot-evidence` (+ unit), `gts9-kmsg-console` (+ unit); the analysis is
in `docs/WATCHDOG_X710.md`.

## Images

| image | sha256 | note |
|---|---|---|
| boot.img (known-good) | `822ca9dcf404de83e79f085a5509ec761bf0234359a5fae166c5d1c849e1df86` | unchanged, still flashed before the ramoops step |
| boot.img (ramoops) | `dfbe70f4779564948cb8d9ce22049c779a8fb271a64795b8131d96e3b1bf5a7b` | flashed, then superseded (see "ramoops") |
| vendor_boot.img (known-good) | `3c88b36b7b3f1703ccd751b77522fa6d16596650e627893e3131848c96731dec` | reproduces byte-for-byte from the recorded build |
| vendor_boot.img (watchdog cmdline) | `3d65d076bcefdbac8df0bd9e5725616886bc55c92ce4316e67cd82abb13c6095` | flashed |
| vendor_boot.img (ramoops) | `eb8f2b211e7a4c4d33a25b542d6c225ea15965e7a9a40890838b7bc7a4de71fb` | flashed |
| dtb (known-good) | `f49b373462a278fcafb858fa9f59dac174d88b4f14810ad2638509d9c2e9e9be` | |
| dtb (ramoops) | `b3e068e7af401a06c81e8dcae250c2a49d653179e1cb3412eba1e050e6d6d596` | |
| dtbo / init_boot / vbmeta | unchanged | `c17418be…` / `7d934eac…` / `b95e5ef9…` |

## Reproducibility

The known-good `vendor_boot` was rebuilt before anything was flashed, and came
back byte-identical (`3c88b36b…`), so the only difference in the debug image is
the command line:

```
18a19,21
> softlockup_panic=1
> workqueue.panic_on_stall_time=45
> gts9_watchdog_debug=1
```

## Panic → reboot → evidence

| step | result |
|---|---|
| `echo c > /proc/sysrq-trigger` at 08:33:43 | USB gone 08:33:55 (10 s = `panic=10`), back 08:34:13 |
| second panic at 09:26:29 (ramoops flashed) | USB gone 09:26:40, back 09:26:56, 970 console lines captured by the kmsg mirror |
| panic report on the host console | not captured: printk goes to `ttyMSM0`/`tty0`, the gadget is a userspace path |
| `/sys/fs/pstore` after a panic | empty — ramoops registers but its records do not survive a reboot (measured twice, §5 of the doc) |
| previous-boot evidence | `gts9-prev-boot-evidence` archives the previous boot's journal, marker counts, verdict, trace tails and any pstore records at every boot |

## First unattended stall recovery (before the loop existed)

The first boot with the profile armed stalled 14 s in, and the tablet recovered
by itself — the first time on this device:

```
08:41:59  WARNING: .../drivers/soc/qcom/rpmh.c:386 at rpmh_write_batch+0x1b4/0x25c, CPU#6: kworker/6:0/57
08:41:59  Workqueue: events pogo_watch_work
          (console silent from here)
08:42:41  next boot: uptime proves the tablet reset itself ~60-75 s after the stall
```

Prior stalls (five of them) all needed a 15-30 s power hold.

## The loop

```sh
reference/boot-tests/test-183-*/gts9-stall-loop.sh [rounds] [window-seconds]
```

A round **is** a boot: the harness issues `systemctl reboot` over the same
console at t+8 s and then only listens for `window` seconds, so one capture
covers the shutdown, the boot, the 13-36 s window in which every recorded stall
began, and - with the profile armed - the panic reboot that follows a stall.
Nothing else is ever sent, so a stalled tablet is never touched while it
recovers. Afterwards a probe reads the tablet's own evidence directory and
compares boot_ids.

A round counts as an **unattended recovery** only when the boot_id changed
*and* the capture carries a stall signature *or* the previous boot did not end
in a clean shutdown (`previous_boot_end=hard-reset-or-incomplete|panic`).
Anything else is a clean round that the harness rebooted itself, and is
recorded as such (`auto_recovery=no-clean-kick`); a round that never comes back
is reported as `NO AUTO-REBOOT` and stops the loop, because that is the one
condition only a human can clear.

## Round results

See `stall-loop.txt`, `stall-loop-summary.txt` and `rounds/round-N*.txt`.

* First 5-round run (`window=200`): 5 clean rounds, 0 stall signatures. The
  captures still contain the full boot log of every boot (the kmsg mirror
  forwards the kernel ring), so each round is a recorded boot even when nothing
  went wrong - and a healthy boot contains **zero** `rpmh_write_batch` lines,
  while the stalling boot printed the warning 14.27 s in.
* Long hunt (`window=200`, 10 rounds): see `stall-loop-summary.txt`.

## Controlled stalls (`stall-inject/`, `inject-rounds.sh`)

The real stall is a race, so the recovery chain is also validated with stalls we
control, built as a module against this kernel and loaded over the console
(`stall-inject/gts9_stall_test.ko`, 9.4 KiB, vermagic
`7.2.0-rc3-gts9wifi-dirty`):

| mode | injection | detector that must fire |
|---|---|---|
| `mode=hung seconds=60` | a kernel thread blocks uninterruptibly on a completion that is never completed | hung task, 45 s, `hung_task_panic=1` |
| `mode=spin seconds=25` | one CPU spins with interrupts disabled, then re-enables them | soft lockup, `softlockup_panic=1` |

Both clear themselves, so a profile that failed to panic would leave a working
tablet. What is being validated is the whole chain the real stall needs: the
detector's report reaching the host through `gts9-kmsg-console`, then the panic,
then `panic=10`, then the tablet coming back with its evidence collected.

```sh
reference/boot-tests/test-183-*/inject-rounds.sh 3 hung 60
reference/boot-tests/test-183-*/inject-rounds.sh 2 spin 25
```

Results are in `inject-rounds.txt`, `inject-rounds-summary.txt` and
`rounds-inject/`:

| run | injection | result |
|---|---|---|
| 3 x `hung 60` | 60 s uninterruptible block | **1/3** - the report arrived (`INFO: task gts9-stall:3179 blocked for more than 45 seconds.`), then panic, then reboot. The other two were missed because khungtaskd sweeps on a global interval, so a 60 s block can fall between two sweeps; use 180 s to make it deterministic. |
| 3 x `spin 30` | 30 s with interrupts disabled | **3/3** - every round ended with a new boot_id and a USB gap: detector, panic, `panic=10`, reboot, unattended. |

One measured distinction worth keeping:

* the **hung-task** report reaches the host, because `khungtaskd` is an ordinary
  kthread and the kmsg mirror forwards its message long before the panic;
* the **soft-lockup** report does not. The detector prints it from the same
  timer/panic path that then stops every other CPU, so userspace never gets to
  forward it - exactly like the panic line itself. Its outcome is still
  observable (the USB gap and the new boot_id), and its text is visible on the
  tablet's own screen, which is how the real stall's
  `watchdog: BUG: soft lockup - CPU#5 stuck for 361s!` was recovered.

So for the real DPU stall the host-side evidence is the sequence *before* the
wedge (the RPMh warning and the DPU timeouts, through the mirror) plus the
reboot gap, which is exactly what the 08:41 recovery left behind.

An `owner-observations.md` in this directory records what the owner saw on the
tablet during the rounds; one reboot came up with only a cursor while the
keyboard worked, which the captures show is a console-repaint symptom on top of
a display pipeline that did come up (`panel id: 80 00 04`).
