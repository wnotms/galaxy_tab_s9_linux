# Test plan: the X710 RTC offset on real hardware

**Status: PARTLY RUN.** Tests 1–3 and 7 have been executed and passed; see
`reference/boot-tests/test-216-rtc-offset-flash/` for the results and
`test-215-rtc-offset-verify/` for the read-only input verification that preceded
them. Tests 4, 5 and 6 are **still outstanding**, and the sections below keep
their original wording so the plan is not rewritten to match the outcome.

Which is which:

| # | claim | status |
| --- | --- | --- |
| 1 | Debian starts with the correct date, offline | **passed** (test 216) |
| 2 | the fix is what moved the clock, not NTP | **passed** — Wi-Fi was disabled first |
| 3 | the raw counter is untouched | **passed** — 95 s of counter over 95 s |
| 4 | `/persist` was not written | **passed** — `ro without journal`, no ext4 error |
| 5 | it survives reboot | **passed** (2 boots; 3 not run) |
| 6 | it survives a long power-off | **not run** |
| 7 | Android/TWRP still work | **not run** — neither has been booted since |
| 8 | nothing else regressed | **passed** — USB NCM, ssh, Wi-Fi, panel, OPP, 0 failed units |

The plan was written before the work so the evidence could not be selected after
the fact; it is kept that way deliberately.

---

## What must be true, and how each is falsified

The change is correct only if **all** of these hold. Each has a measurement that
can show it false, and the measurement is recorded whether it passes or fails.

| # | claim | falsified by |
| --- | --- | --- |
| 1 | Debian starts with the correct date, offline | `date -u` in the first seconds after boot is still 1970/2026-04 |
| 2 | the fix is what moved the clock, not NTP | the same correct date on a boot with **no** network |
| 3 | the raw counter is untouched | `/sys/class/rtc/rtc0/since_epoch` stops advancing at 1 s/s from its 1970 base |
| 4 | `/persist` was not written | `ats_2` mtime/content unchanged; filesystem not left dirty |
| 5 | it survives reboot | 3 consecutive offline boots all correct |
| 6 | it survives a long power-off | after ≥30 min off, still correct (it is a file, so this must hold — but assert it) |
| 7 | Android/TWRP still work | TWRP's `Fixup_Time` reaches the same time it did before |
| 8 | nothing else regressed | USB NCM, ssh, Wi-Fi, panel, rootfs handoff, 3.36 GHz OPP all as before |

Claims 1–3 are the ones that matter most. Claim 8 is not optional: this change
runs before the root handoff, so a bug in it can strand the device.

---

## Preconditions

- A bundle built from this branch, with `initramfs-minimal.img` carrying
  `/sbin/gts9-rtc-offset` (`sha256` in the bundle's `initramfs.manifest`).
- `./scripts/validate-boot-bundle.sh` passes on that bundle.
- TWRP available for the offline reads.
- **The owner's explicit authorisation to flash**, recorded in the test README.

Nothing in this plan writes to the PMIC RTC. Every command is a read.

---

## Test 1 — the boot record carries a real date

**The cheapest and most decisive test.** The record is written by `/init` itself,
so its `timestamp=` is produced by the clock this change sets — and it is readable
from TWRP with no network and no working panel.

1. Record the host's real UTC time.
2. Flash the bundle, boot the tablet, let it reach Debian.
3. Read the record from TWRP:

   ```sh
   sed -n 's/^timestamp=//p' /mnt/debian/var/log/gts9-minimal-last-boot
   ```

**Pass:** the timestamp is within a few minutes of step 1.
**Fail:** a 1970 date — that means the offset was not applied at all.

> **Do NOT judge this test by Debian's `date`.** There are two independent clock
> bugs on this device, and the second hides the first:
>
> * the raw RTC, which this change fixes;
> * **systemd's built-in epoch**, which advances any clock below it. On this tablet
>   the epoch is the rootfs build time, measured on the device as
>   `Tue 2026-04-14 03:38:05 CST` = `2026-04-13T19:38:05Z`. systemd says so itself:
>   `systemd[1]: System time advanced to built-in epoch: ...`
>
> So with **no fix at all** Debian still shows `2026-04-13` — 56 years better than
> the truth, and therefore easy to mistake for "roughly right". A `date` of
> `2026-04-13` means systemd advanced a broken clock; it does **not** mean the
> offset was read.
>
> The discriminating reading is the **initramfs** record's `timestamp=`, written by
> `/init` *before* systemd starts. Both stages are visible in one older boot
> (`reference/boot-tests/test-172-20260923T131339Z/com17-diagnostics.txt`):
>
> ```
> boot_stage_file=timestamp=1970-09-18T01:22:38Z   <- /init, pre-systemd
> stage_timestamp=2026-04-13T19:38:06Z             <- Debian, post-systemd
> ```
>
> The corrected time lands *above* the epoch, so systemd leaves it alone — which is
> why the fix holds, and why the initramfs record is the only honest witness to it.
> `docs/RTC_OFFSET.md` §7 has the full analysis.

**Also capture the same record with `grep '^stage='` and `grep '^failure='`**, to
prove the boot reached `switch-root` and did not take a rescue branch.

Save as `reference/boot-tests/test-NNN-rtc-offset/timestamp-proof.txt`.

---

## Test 2 — the clock is correct offline, and it is this code that did it

The point is to exclude NTP, which would make the fix look like it worked.

1. Boot with **no** network: no Wi-Fi credentials, no USB host on the other end,
   so nothing can reach an NTP server.
2. On the tablet, as soon as possible:

   ```sh
   date -u
   timedatectl
   cat /sys/class/rtc/rtc0/since_epoch
   cat /proc/driver/rtc
   dmesg | grep -i rtc
   ```

3. `date -u` must be correct. `since_epoch` must still be the **raw** counter
   (tens of millions, 1970-based) — that is the proof the PMIC was not written.
4. `dmesg | grep rtc-offset` must show
   `rtc-offset: status=applied …` with the device's real `offset_ms`.

Save: `date.txt`, `timedatectl.txt`, `since_epoch.txt`, `proc-driver-rtc.txt`,
`dmesg-rtc.txt`.

**Pass:** correct `date -u`, `status=applied`, raw `since_epoch`.
**Fail:** correct date but `status=` anything else (then something else set the
clock); or `since_epoch` near the real date (the counter was written — stop and
investigate, this is the hazard the design exists to avoid).

---

## Test 3 — offline reboots

Repeat test 2 for 3 consecutive boots with the network still unavailable.

**Pass:** correct on all 3.
**Fail:** correct on the first, wrong later — that would mean the offset is being
consumed from somewhere transient rather than re-read.

---

## Test 4 — long power-off

Power the tablet off for ≥30 minutes, then boot offline and re-run the test 2
reads.

**Pass:** still correct. The offset is a file on UFS, so it must be — but a
failure here would mean the value is being cached in RAM rather than read.

---

## Test 5 — the failure paths do not break the boot

Each of these must produce a reported status **and a normal boot**:

| manipulation | expected status | expected outcome |
| --- | --- | --- |
| rename `/persist/time/ats_2` in TWRP, boot | `offset-file-missing` | boots with the raw 1970 clock, as before |
| overwrite it with 0 bytes | `offset-file-missing` | same |
| truncate it to 3 bytes | `offset-file-missing` | same |
| write `0` into it | `offset-out-of-range` | same |
| add `gts9_rtc_offset=0` to the cmdline | `disabled-by-cmdline` | same |

The first four require writing to `/persist` from **TWRP**, which is the owner's
partition and must be restored afterwards — record the original value first and
put it back byte-for-byte:

```sh
# In TWRP, BEFORE any manipulation:
cp /persist/time/ats_2 /sdcard/ats_2.backup
# ... and after the test:
cp /sdcard/ats_2.backup /persist/time/ats_2
```

Only test 5's cmdline case is non-destructive, so run that one first.

**Pass:** every case boots to Debian.
**Fail:** any case stops at the rescue shell — that would mean an optional
convenience can strand the device, which the design forbids.

---

## Test 6 — Android and TWRP are unaffected

1. Boot TWRP and read `/proc/driver/rtc` and `/sys/class/rtc/rtc0/since_epoch`:
   the raw counter must still be present and 1970-based.
2. Confirm TWRP's `Fixup_Time` still reaches the correct time from the same file
   (`grep Fixup_Time` in its log).
3. If Android is available, boot it and confirm the date is correct there too.

**Pass:** all three unchanged from before this change.
**Fail:** the raw counter has moved to a real date, or TWRP's corrected time
changed materially.

---

## Test 7 — regression sweep

Confirm the things this project has already proven still work, because this code
runs before the root handoff:

- USB NCM enumerates and `169.254.42.1` responds;
- ssh into Debian;
- Wi-Fi associates and passes traffic;
- the panel comes up;
- the root handoff reaches `switch-root` in the boot record;
- the 3.36 GHz OPP is still available;
- the CPU-wedge debug config is unchanged.

---

## Evidence layout

```
reference/boot-tests/test-NNN-rtc-offset/
├── README.md              what was run, bundle sha256s, verdict, what failed
├── timestamp-proof.txt    test 1
├── date.txt               test 2
├── timedatectl.txt
├── since_epoch.txt
├── proc-driver-rtc.txt
├── dmesg-rtc.txt
└── reboots/               test 3, one directory per boot
```

Every README states the bundle hashes, the exact cmdline, and which claims above
are **not** verified by that run. A test that only confirms what was expected is
not evidence, so the failures and the untested claims belong in the same file as
the successes.
