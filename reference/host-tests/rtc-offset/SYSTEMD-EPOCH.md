# The second clock bug: systemd's built-in epoch

Found while preparing the first hardware test, from evidence already in this
repository. It matters because it **masks** the RTC bug: a boot with no fix at all
still shows a plausible-looking date.

## The observation

Every Debian-side timestamp in this project's history reads `2026-04-13` or
`2026-04-14` regardless of the real date of the test. Same constant across
test 172 (2026-09-23), test 178 (2026-09-23) and test 211 (2026-09-26):

```
stage_timestamp=2026-04-13T19:38:06Z
timestamp=2026-04-13T19:40:02Z
```

A timestamp that does not move when days pass is not a clock reading. It is a
constant being installed.

## The cause

`systemd(1)`, SYSTEM CLOCK EPOCH:

> The epoch is set to the highest of: the build time of systemd, the modification
> time ("mtime") of `/usr/lib/clock-epoch`, and the modification time of
> `/var/lib/systemd/timesync/clock`. [...] the local clock is *advanced* to the
> epoch if it was set to a lower value.

The device says so itself, once per boot:

```
systemd[1]: System time advanced to built-in epoch: Tue 2026-04-14 03:38:05 CST
```

`2026-04-14 03:38:05 CST` = `2026-04-13T19:38:05Z`. Neither `/usr/lib/clock-epoch`
nor `/var/lib/systemd/timesync/clock` exists in this Debian tree, so the epoch is
the **rootfs build time** — confirmed by the mtimes on the card:

```
-rw-r--r-- 1 root root  956 2026-04-14 03:38 gts9-last-boot-stage
drwxr-sr-x 3 root root 999 4096 2026-04-14 03:38 journal
```

## Both bugs in one boot

`reference/boot-tests/test-172-20260923T131339Z/com17-diagnostics.txt` captures the
initramfs record and the Debian record in the same session:

```
boot_stage_file=timestamp=1970-09-18T01:22:38Z   <- /init, before systemd: raw RTC
stage_timestamp=2026-04-13T19:38:06Z             <- Debian, after systemd: epoch
```

The initramfs record's own file mtime is still `1970-09-18`, which proves `/init`
wrote it before systemd changed anything:

```
-rw-r--r-- 1 root root 355 1970-09-18 13:02 gts9-minimal-last-boot
```

## Why it matters for the RTC fix

| clock when systemd starts | vs epoch | systemd action |
| --- | --- | --- |
| raw RTC `1970-09-18` (no fix) | far below | advances to 2026-04-13 |
| with the fix, `2026-09-25`+ | above, < 15 years | leaves it alone |

The fix is therefore compatible with systemd rather than fighting it. But the
testing consequence is sharp:

**A boot whose `date` reads `2026-04-13` does not mean the RTC fix failed.** It
means systemd advanced a broken clock — exactly what happens with no fix. Only the
initramfs record's `timestamp=` distinguishes the two states, which is why it is
the pass/fail reading in `reference/rtc-offset-test-plan.md` and not `date`.

## Reproducing the arithmetic

```sh
# The epoch, from the device log (CST = UTC+8):
#   systemd[1]: System time advanced to built-in epoch: Tue 2026-04-14 03:38:05 CST
date -u -d '2026-04-14 03:38:05 +0800' +%s      # 1776109085

# In the same boot, /init's own record still carries the raw counter:
#   boot_stage_file=timestamp=1970-09-18T01:22:38Z
date -u -d '1970-09-18T01:22:38Z' +%s           # 22468958
```
