# Test 215 — the RTC offset, read from real hardware

**Read-only. Nothing was flashed, and nothing was written to the tablet.**
The persist partition was mounted `-o ro` only to read one file, and
unmounted again; no journal replay was triggered.

TWRP happened to be running (the tablet was in recovery for an unrelated
reason), which gave the first opportunity to read the two values this whole
change rests on. Until this session they had been inferred from recorded
logs; the arithmetic had never been checked against a live device.

## What was confirmed

| claim in `docs/RTC_OFFSET.md` | status |
| --- | --- |
| the offset lives in `/persist/time/ats_2` on the UFS `persist` partition | **confirmed** |
| `persist` is `/dev/block/sda5` | **confirmed** |
| the file is exactly 8 bytes | **confirmed** (all five ats files are) |
| signed little-endian milliseconds, no header | **confirmed** |
| `correct = raw + ats_2/1000` | **confirmed to the second** |
| the helper reproduces it | **confirmed** |
| ats_2 is a live delta, not an absolute epoch | **confirmed** |

## The decisive number

```
raw since_epoch   = 23153
ats_2             = 1790396967618 ms
raw + ats_2/1000  = 1790420120  =  2026-09-26T10:55:20Z
TWRP date -u      = Sat Sep 26 10:55:20 UTC 2026
```

Exact match. `device-reads.txt` has the raw reads and the full working.

## Two things this session changed

**1. The offset is a live delta.** The raw counter had been *reset* since the
last recording, and `ats_2` had grown by the compensating amount: the sum
still tracked real elapsed time (3.2 days over a real 3 days). This is the
strongest evidence yet that only the sum is meaningful - and it retroactively
justifies reading the file at runtime, since a value baked into a kernel or
DTS would have been wrong by 259 days on this very boot.

**2. `date` cannot be the pass/fail reading.** See
`reference/host-tests/rtc-offset/SYSTEMD-EPOCH.md`: systemd advances any
clock below its built-in epoch, so a Debian boot with *no* fix still shows a
plausible 2026-04 date. The initramfs record's `timestamp=` is the witness.

## Still not tested

The fix itself has not been booted. This session read the inputs it depends
on; it did not run `/init` on the tablet. `reference/rtc-offset-test-plan.md`
is still the plan, not a result - in particular the mount is proven only
against TWRP's busybox here, not against this repository's initramfs.
