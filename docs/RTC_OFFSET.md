# The X710 RTC offset: where Samsung keeps the real time

**Question this answers:** why does mainline read 1970 from the PMK8550 RTC when
Android and TWRP show the correct date, and how is mainline made to read the same
thing?

**Answer in one line:** the offset is not in the PMIC at all — it is a plain file,
`/persist/time/ats_2` on the UFS `persist` partition, holding 8-byte signed
little-endian **milliseconds** — and the production initramfs now reads it and
sets `CLOCK_REALTIME` before Debian starts.

All line references, values and log excerpts below come from the current `test`
HEAD (`830eb03`) and the boot tests recorded in `reference/boot-tests/`.

---

## 1. What the raw counter actually is

The PMK8550's RTC is a 32-bit seconds counter that counts from the Unix epoch and
is **never set** on this board. It is not broken and it is not slow: it keeps
good time from an arbitrary origin of 1970-01-01.

| reading | value | source |
| --- | --- | --- |
| `/proc/driver/rtc` (TWRP kernel) | `rtc_date : 1970-09-16`, `rtc_time : 01:44:31` | `reference/boot-tests/test-018-20260921T134149Z/rtc-twrp.txt` |
| `/sys/class/rtc/rtc0/since_epoch` | `22297471` | same test, same session |
| mainline `hctosys` | `setting system clock to 1970-09-20T00:32:38 UTC (22638758)` | `reference/boot-tests/test-198-20260925T1235Z/klog-4.txt:502` |
| mainline `hctosys` (earlier) | `setting system clock to 1970-09-19T23:43:59 UTC (22635839)` | `reference/boot-tests/test-196-20260925T1100Z/klog-2.txt` |

The counter advances at exactly one second per second between those readings, so
mainline is reading the hardware correctly. What it lacks is the offset.

Because the counter is left alone, **no SPMI write is needed to fix the clock** —
see §8. That is the single most important property of this design.

---

## 2. Where the offset lives — the decisive evidence

It is a file, not a register:

```
/persist/time/ats_2
```

on the UFS `persist` partition. TWRP says so itself, in the recovery log from
test 165 (`reference/boot-tests/test-165-20260923T061249Z/recovery.log:136-142`):

```
I:Processing '/persist'
I:Created '/persist' folder.
I:TWFunc::Fixup_Time: Pre-fix date and time: 2022-09-17--18-08-11
I:TWFunc::Fixup_Time: Setting time offset from file /sys/class/rtc/rtc0/since_epoch
I:TWFunc::Fixup_Time: will attempt to use the ats files now.
I:TWFunc::Fixup_Time: Setting time offset from file /persist/time/ats_2, offset 1767701103844
I:TWFunc::Fixup_Time: Date and time corrected: 2026-09-23--06-13-13
```

Three independent facts in that excerpt:

1. the file is `/persist/time/ats_2`;
2. its value is **`1767701103844`**;
3. TWRP calls the result "corrected", and the corrected time matches the real
   date of that test run.

### The partition

`/persist` is UFS `sda5`, ext4. Stock Android's own fstab identifies it
(`android_device_samsung_gts9wifi/out/decrypt-stock/etc/fstab.qcom`):

```
/dev/block/bootdevice/by-name/persist /mnt/vendor/persist ext4 noatime,... wait,check
/dev/block/bootdevice/by-name/misc    /misc                emmc defaults defaults,first_stage_mount
```

and the label is confirmed on the kernel side — the production initramfs looks the
partition up by the **GPT label** `persist` that the kernel's own EFI partition
parser publishes as `PARTNAME=` in sysfs, exactly as it already does for `misc`.
Nothing is guessed from a device number.

### What it is NOT

Established by direct search, so that no future reader repeats it:

| candidate | verdict | why |
| --- | --- | --- |
| PMIC SDAM / NVMEM cell | **no** | no `nvmem-cells` on the RTC node, and no stock DT or live-stock DTS node carries an RTC offset cell |
| PON / `pon_rtc` registers | no | same |
| UEFI variable | **no** | `efi: UEFI not found` and `EFI services will not be available` in `reference/boot-tests/owner-supplied-july-kernel/last_kmsg-owner-july-kernel.txt` |
| kernel hardcoded constant | no | byte-pattern searches for the constants in the prebuilt kernel, `rtc-pm8xxx.ko` and `dtb.img` found nothing |
| vendor kernel driver logic | **no** | the stock 5.15 driver has no offset support at all — see §4 |

---

## 3. The format, and the proof it is correct

`ats_2` is **8 bytes, signed, little-endian, milliseconds**. No header, no magic,
no checksum, no version.

Value on this tablet: `1767701103844` ms = `1767701103` s = **2026-01-06
12:05:03 UTC**, when the offset was last written.

It is a **delta**, applied as:

```
correct_time = raw_counter + ats_2 / 1000
```

### Verified against two independent on-device data points

**Point 1 — TWRP, test 165 (2026-09-23).** TWRP printed the corrected time
`2026-09-23--06-13-13`, so:

```
raw = 1790143993 - 1767701103 = 22442889 s
22442889 s = 1970-09-17 18:08:10
```

and TWRP's own pre-fix line was `2022-09-17--18-08-11` — the same *day-of-month,
hour, minute and second*, 52 years later. Exact match.

**Point 2 — mainline's own reading, test 018 (2026-09-21).**

```
raw (from /sys/class/rtc/rtc0/since_epoch) = 22297471   -> 1970-09-16 01:44:31
date -u in the same session              = 2026-09-21T13:46:10Z
raw + 1767701103                         = 2026-09-21 13:49:34Z
```

The 204-second difference is the gap between the two probes in that session; the
date is right.

**Point 3 — mainline hctosys arithmetic.** The two mainline readings in §1 give
`22635839 + 1767701103 = 2026-09-25 11:49:02` and
`22638758 + 1767701103 = 2026-09-25 12:37:41`, both matching the capture date of
their own logs. The offset is time-invariant, which is what makes it safe to add.

### The 2022 red herring

TWRP's `Pre-fix date and time: 2022-09-17--18-08-11` looks like a 2022 epoch and
is not one. It is the raw counter rendered after a `+1640995200`
(2022-01-01) shift, a cosmetic artefact of `Fixup_Time_On_Boot()`'s first
`settimeofday()` before the ats file is read. The real gap between that line and
the corrected line is 18993 days, i.e. exactly 52 years. No 2022 base is
involved, and the recovery-kernel `setting system clock to
2022-09-16T00:52:31 UTC (1663289551)` lines seen in tests 006/008/012/044 are the
same artefact in the other direction.

---

## 4. Why mainline did not read it

Three independent reasons, any one of which is sufficient:

1. **The file is on a partition mainline never mounted at boot.** The production
   initramfs mounts the microSD root and nothing else; `/persist` is not in its
   path at all.
2. **The upstream offset support points somewhere else.** `rtc-pm8xxx` looks for
   an NVMEM cell or a UEFI variable (§5, §6) — hardware sources that this board
   does not populate.
3. **The stock Samsung kernel does not read it either.** This is the part that
   corrects the original premise. `kernel_platform/common/drivers/rtc/rtc-pm8xxx.c`
   (569 lines) has **no** offset, NVMEM or UEFI support: its only match for
   `nvmem|offset` is the comment `/* RTC Register offsets from RTC CTRL REG */`.
   The genuine stock module shipped in the recovery ramdisk
   (`android_device_samsung_gts9wifi/recovery/root/lib/modules/rtc-pm8xxx.ko`,
   `vermagic=5.15.94-android13-8-27940245-abX710XXU1BWK6`) exports only
   `pm8xxx_rtc_probe`, `pm8xxx_rtc_read_time` and `pm8xxx_rtc_set_time`.

So the offset was **never** a kernel concern on this device. Android and TWRP read
it in **userspace**, from the file. Mainline has no such userspace component, and
that — not a driver deficiency — is the whole gap.

---

## 5. Can upstream's NVMEM offset support be used directly? **No.**

Upstream `drivers/rtc/rtc-pm8xxx.c` supports an offset from an NVMEM cell:

```c
rtc_dd->nvmem_cell = devm_nvmem_cell_get(rtc_dd->dev, "offset");
...
buf = nvmem_cell_read(rtc_dd->nvmem_cell, &len);
if (len != sizeof(u32)) { ...; return -EINVAL; }
rtc_dd->offset = get_unaligned_le32(buf);
```

with the binding (`Documentation/devicetree/bindings/rtc/qcom-pm8xxx-rtc.yaml`)
documenting `nvmem-cells` as "four-byte nvmem cell holding a little-endian offset
from the Unix epoch".

Every mismatched dimension:

| | upstream expects | this tablet has |
| --- | --- | --- |
| width | 4 bytes | **8 bytes** |
| encoding | unsigned, seconds | **signed, milliseconds** |
| provider | hardware NVMEM cell (SDAM) | **a file on a UFS partition, in a filesystem** |
| who writes it | the kernel, at NTP sync and shutdown | Samsung's userspace time daemon |

There is no NVMEM provider on this board that could serve the cell, and even if
one were invented, the value would have to be re-encoded and mirrored into it on
every change — a second copy of state that Android owns, kept in a place Android
does not read.

### Why adding an `nvmem-cells` cell to the DTS would be actively harmful

This is the trap in the obvious-looking fix, and it is worth stating plainly
because the DTS is where a future reader will be tempted.

`pm8xxx_rtc_set_time()` branches on `allow-set-time`:

```c
if (rtc_dd->allow_set_time)
        rc = __pm8xxx_rtc_set_time(rtc_dd, secs);   /* writes the counter */
else
        rc = pm8xxx_rtc_update_offset(rtc_dd, secs); /* writes the NVMEM cell */
```

and `pm8xxx_rtc_update_offset()` starts:

```c
if (!rtc_dd->nvmem_cell && !rtc_dd->use_uefi)
        return -ENODEV;
```

**Today the RTC node has neither `nvmem-cells` nor `qcom,uefi-rtc-info`, so that
function returns `-ENODEV` immediately and the write path is unreachable.** This
is why no SPMI write has ever happened on this board from the offset path.

Adding `nvmem-cells` would arm it. From then on every NTP sync would call
`pm8xxx_rtc_write_nvmem_offset()`, and `pm8xxx_shutdown()` would write again if
`offset_dirty` were set. Those are SPMI writes — and an SPMI **write** blocks this
kernel uninterruptibly, which is the documented failure in
[`RTC_REPORT.md`](RTC_REPORT.md) and tests 021–027 (the SDAM reboot-mode write in
test 024 hung the same way). The change that looks most "upstream-compatible"
would introduce a boot-hang class this project already paid four test cycles to
find.

**The fix therefore deliberately touches neither the DTS nor the driver.** The
test suite asserts that no `nvmem-cells`, `allow-set-time` or `qcom,uefi-rtc-info`
appears in the board DTS or in any queued patch, so this trap cannot be
reintroduced by accident.

---

## 6. Does `qcom,uefi-rtc-info` apply to the X710? **No.**

- The property's fallback path requires `efivar_is_available()` and, under
  `CONFIG_EFI`, returns `-EPROBE_DEFER` when it is not. This device logs
  `efi: UEFI not found` and `EFI services will not be available`, so there is no
  UEFI variable store to read at all.
- Every mainline user of the property is a Windows-on-ARM machine
  (`sc8280xp-lenovo-thinkpad-x13s`, `sc7180-ecs-liva-qc710`, `hamoa-pmics`) where
  the offset is written by Windows or UEFI firmware. No Android phone or tablet
  DT in mainline uses it.
- The layout would not match anyway: a 12-byte `RTCInfo` variable holding
  `offset_gps` plus `RTC_TIMESTAMP_EPOCH_GPS` (1980-01-06), not Samsung's
  milliseconds file.

---

## 7. The fix

The production initramfs reads the file and sets the clock, before Debian starts.

```
boot/minimal-rootfs-init.sh     minimal_apply_rtc_offset()
boot/gts9-rtc-offset.c          the freestanding aarch64 helper
scripts/build-minimal-initramfs.sh   compiles and stages it at /sbin/
```

Sequence, in `/init`, after `/sys` and `/dev` exist and **before** the state
library takes its first timestamp:

1. find the partition whose `PARTNAME=` is `persist` (never a device number);
2. `mount -t ext4 -o ro,noload` it at `/persist-ro`, bounded by `timeout 10`;
3. run `/sbin/gts9-rtc-offset`, bounded by `timeout 10`;
4. unmount it;
5. pass the helper's own one-line report through to `/dev/kmsg`, the console and
   the persistent record.

The helper computes `(raw_ms + offset_ms) / 1000` and calls `clock_settime(CLOCK_REALTIME)`
exactly once. It reports one self-describing line:

```
rtc-offset: status=applied source=persist/time/ats_2 offset_ms=1767701103844 raw_ms=22638758000 realtime_epoch=1790339861
```

Failure is never fatal, and each failure has its own status and exit code:

| status | exit | meaning |
| --- | --- | --- |
| `applied` | 0 | clock set |
| `offset-file-missing` | 12 | no partition, no file, or not exactly 8 bytes |
| `offset-out-of-range` | 13 | present but not a plausible delta |
| `rtc-unreadable` | 14 | `/sys/class/rtc/rtc0/since_epoch` unreadable |
| `realtime-out-of-range` | 15 | sum outside 2020-01-01 … 2100-01-01 |
| `helper-missing` / `partition-missing` / `mount-failed` | — | reported by `/init` |

Setting the clock in the initramfs rather than in Debian is deliberate: the wall
clock is **kernel** state and survives `switch_root`, so Debian's first process
already sees the correct time and no service has to run first. A userspace-only
fix in Debian would leave every kernel and early-userspace timestamp wrong — which
is the report this project already had, one boot record reading `2026-04-13` on a
tablet whose real date was `2026-09-26`.

### Ordering is the proof

`minimal_apply_rtc_offset` runs before `minimal_state_init`, so the record's
`timestamp=` field is stamped with the corrected clock. That makes the fix
verifiable from a TWRP session with no network:

```
timestamp=2026-09-26T...      correct
timestamp=2026-04-13T...      the bug is back
```

Two tests assert this ordering, because it is the difference between evidence and
a claim.

---

## 8. Does this write anything? **No.**

This was the hard constraint, and it shaped the design.

| operation | performed? | note |
| --- | --- | --- |
| PMK8550 RTC counter write | **no** | no code path reaches an RTC device node; the helper's only file opens are `O_RDONLY` |
| `hwclock -w` / `--systohc` | **no** | the applet is not in the production image and is forbidden by test |
| `allow-set-time` in DTS | **no** | asserted absent by test |
| NVMEM/SDAM cell write | **no** | no `nvmem-cells`; `pm8xxx_rtc_update_offset()` returns `-ENODEV` |
| UEFI variable write | **no** | no `qcom,uefi-rtc-info`, and no EFI runtime exists |
| `devmem` / regmap debugfs write | **no** | never used |
| write to `/persist` | **no** | mounted `ro,noload`; see below |

### Why `ro,noload` and not just `ro`

`-o ro` alone is **not** read-only in fact. From `fs/ext4/super.c`, when the
journal needs recovery, a read-only mount prints `write access will be enabled
during recovery` and performs it — writing to the owner's `persist` partition to
read one file. `noload` skips `ext4_load_and_init_journal()` entirely, so no
journal is loaded and nothing is written. A test asserts both options are present,
because dropping `noload` would be a silent regression that no ordinary boot would
reveal.

**The only thing this change mutates is the kernel's own wall clock.**

---

## 9. Is the time correct in kernel-early boot with no network?

**Partly — and the boundary should be stated exactly.**

- **Before `/init` runs: no.** The kernel mounts the RTC at ~2.80 s and sets the
  system clock from the raw counter before any userspace exists, so messages from
  `0.000000` to ~2.81 s carry the 1970-derived time. This is upstream `rtc_hctosys`
  behaviour and is unchanged by design: fixing it in-kernel would require exactly
  the NVMEM/UEFI mechanism that §5 rules out, or a driver patch carrying a
  hardcoded offset — which would be wrong the moment Samsung's daemon rewrites the
  file.
- **From `/init` onward: yes, with no network.** The clock is correct before the
  root filesystem is mounted, before `switch_root`, and therefore before systemd,
  ssh, `apt`, or any service that needs a valid date.
- No network is involved at any point, and none is required.

The honest summary: the residual error is roughly the first **2.8 seconds** of
kernel boot rather than 56 years. Every timestamp a user can observe — journal,
`date`, ssh, TLS, package management, and the boot record itself — is correct.

### Debian does not fight it

`CONFIG_RTC_HCTOSYS=y` with `CONFIG_RTC_HCTOSYS_DEVICE="rtc0"` sets the clock
once, at rtc0 registration, and never again. `CONFIG_RTC_SYSTOHC=y` would write
the clock back to the RTC every ~11 minutes once NTP is synchronised — but that
write goes through `pm8xxx_rtc_set_time()` → `pm8xxx_rtc_update_offset()` →
`-ENODEV`, because the DTS has neither offset property (§5). No SPMI write
occurs, and the raw counter is left untouched for Android and TWRP.

---

## 10. Do Android and TWRP still work?

**Yes, and they are unaffected by construction, because nothing they read is
changed.**

| what they read | changed? |
| --- | --- |
| the PMK8550 RTC counter | no — still the raw 1970-based count |
| `/persist/time/ats_2` | no — read-only mount, never written |
| any other `/persist` content | no — `noload` means the filesystem is not modified at all |

Android's time daemon will keep updating `ats_2` as it always has, on its own
schedule; this change neither depends on that nor interferes with it. TWRP's
`Fixup_Time_On_Boot()` will keep reading the same file and reaching the same
result. If Samsung's daemon rewrites the offset, the next mainline boot picks up
the new value automatically, because it is read at runtime and never cached in the
kernel, the DTB or the initramfs.

Bootloader control block, USB, Wi-Fi, panel and rootfs handoff are untouched.

---

## 11. Risks and unknowns

**Knowns, with evidence:**

- the offset file, its format and its arithmetic are confirmed against three
  independent on-device data points (§3);
- the value is machine-specific and can change, so it is read at runtime;
- no SPMI write is reachable from the new code, and the DTS/driver are unchanged;
- the helper cannot fail the boot, and every failure has a distinct status.

**Unknowns, stated so they are not mistaken for settled:**

1. **`ats_2` versus `ats_5`+.** TWRP prefers `ats_2`, which per Qualcomm's
   `time_genoff.h` enum is `ATS_USER` (index 2 — despite TWRP's own comment
   calling it `ATS_TOD`). Whether Samsung's daemon also maintains other `ats_N`
   files with different deltas, and whether one of them is a better source, is not
   established on this device. This fix reads the same file TWRP reads, so it
   cannot be worse than the current recovery behaviour, but it is one file of
   several in that directory.
2. **No physical verification yet.** The on-device boot has not been run: no
   tablet is currently connected, and flashing was not authorised for this round.
   Everything above is source analysis plus arithmetic against recorded device
   logs. The host tests execute the real helper, but they cannot prove the mount
   works against a real Samsung-formatted `persist` partition; that is what the
   test plan in `reference/rtc-offset-test-plan.md` is for.
3. **Whether `persist` is encrypted or wrapped on a stock device.** It is ext4 per
   stock fstab and TWRP mounts it as such, so this is expected to be fine, but it
   has not been observed under this kernel. A failed mount is reported, not fatal.
4. **The first ~2.8 s of kernel time stays wrong** (§9), which is inherent to
   doing this in userspace.
5. **Clock monotonicity.** Setting `CLOCK_REALTIME` forward by ~56 years is a
   discontinuity. `timeout` and the shell's own timers are safe — `ITIMER_REAL`
   is armed on `CLOCK_MONOTONIC` (`hrtimer_setup(&sig->real_timer, it_real_fn,
   CLOCK_MONOTONIC, HRTIMER_MODE_REL)` in `kernel/fork.c`), so the clock step
   cannot expire them early. Nothing before this point has armed a wall-clock
   timer, because nothing before it has run.
6. **A future mainline or Debian change** could add `systemd-hwclock` to the
   rootfs, which would write the corrected time back to the RTC via
   `RTC_SET_TIME` — the SPMI write that hangs this board. It is not present today
   (no `hwclock`/`adjtime` state is recorded in `reference/device-state/`), and
   §5's `-ENODEV` path means the *driver* cannot write the counter even then; the
   hazard would be a userspace `hwclock`, which is worth watching for.

---

## Reproducing the arithmetic

```sh
# The offset, as the tablet holds it (the file is 8-byte signed LE ms):
#   od -An -tu8 -N8 /persist/time/ats_2   ->  1767701103844

# The raw counter, from the driver's own attribute:
#   cat /sys/class/rtc/rtc0/since_epoch   ->  22638758

# Correct UTC:
date -u -d "@$((22638758 + 1767701103844 / 1000))" '+%Y-%m-%dT%H:%M:%SZ'
# 2026-09-25T12:37:41Z
```

## Verifying on the tablet

`reference/rtc-offset-test-plan.md` carries the on-device plan. The one-line
check, offline, from TWRP:

```sh
sed -n 's/^timestamp=//p' /mnt/debian/var/log/gts9-minimal-last-boot
```

A correct fix prints today's date. The old bug printed `2026-04-13` on
2026-09-26.
