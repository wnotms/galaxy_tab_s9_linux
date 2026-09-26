# Test 216 — the RTC offset fix, verified on the tablet

**Result: PASS.** Debian boots with the correct UTC time, **offline**, with the
PMIC RTC left untouched.

## What was flashed

One partition. `boot`, `vendor_boot`, `dtbo` and `vbmeta` were left alone, so the
verified kernel/DTB boot chain is byte-identical to test 214.

| partition | sha256 | changed |
|---|---|---|
| `init_boot.img` | `1a8c71487d30bf39d635ff52893cce22efc0b9a81a6f4788edf47945843f78c0` | **yes** |
| `boot.img` | `71e194a528d373580ee354bea1c0e68c2ff146d014ae34679955577b261d038d` | no |
| `dtbo.img` | `c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3` | no |

The write was read back from the partition and matched before the reboot.

**Backup first.** The previous `init_boot` was dumped and `sha256sum`'d on the
device before anything was written, and the dump was pulled to the host:

```
1e98bea223cf8e6ee58a4a0e8378f9c916d02e3a9c4bde7aa431e5472cbe6175  init_boot-pre-rtc-offset.img
```

That hash matches what the device reported for its own partition, so a revert is a
byte-for-byte restore.

## The decisive evidence: a correct clock with no network

The strongest claim this change makes is that the correct time comes from
Samsung's own offset and **not** from NTP. So Wi-Fi was disabled first, leaving
only the USB link:

```
wlp1s0           DOWN
169.254.0.0/16 dev usb0 proto kernel scope link src 169.254.42.1
```

Then the tablet was rebooted and read back:

```
=== HOST real time  ===  2026-09-26T11:36:47Z
=== device: up 0 minutes, boot_id 136df623   ===
=== device date -u  ===  Sat Sep 26 11:36:46 UTC 2026
System clock synchronized: no
              NTP service: n/a
                 RTC time: Thu 1970-01-01 07:07:20
```

Correct to the second, on a fresh boot, with the clock explicitly **not**
synchronised and no NTP service, while the hardware RTC still reads 1970. NTP
cannot explain this; the offset can.

## The RTC was not written

This was the hard constraint, and it holds measurably. The helper reports the raw
counter it read, so the two boots can be compared:

| boot | raw counter (ms) | record timestamp |
|---|---|---|
| 1 | 25 506 000 | 2026-09-26T11:34:33Z |
| 2 | 25 601 000 | 2026-09-26T11:36:08Z |

The counter advanced **95 s** across **95 s** of real time. It kept counting at one
second per second from its 1970 origin. A write would have jumped it to ~1.79e9
seconds; instead `timedatectl` still shows `RTC time: Thu 1970-01-01`. Android and
TWRP will find the counter exactly as they left it.

## The ordering is what makes the record trustworthy

From the kernel log of the boot, the offset is applied **before** the first
recorded stage:

```
[    0.812059] gts9-minimal: rtc-offset: status=applied source=persist/time/ats_2 \
                  offset_ms=1790396967618 raw_ms=25601000 realtime_epoch=1790422568
[    0.880512] gts9-minimal: GTS9_MINIMAL_STAGE=kernel-userspace
```

and the persisted record consequently carries a real date:

```
stage=switch-root-synced
failure=none
timestamp=2026-09-26T11:36:08Z
uptime_seconds=0.81
```

`timestamp=` is the reading that matters. Before this change the initramfs record
read `1970-09-18`, and Debian's own stage records read `2026-04-13` — not because
the RTC was right, but because systemd advanced the broken clock to its built-in
epoch (`reference/host-tests/rtc-offset/SYSTEMD-EPOCH.md`). That is why a Debian
`date` alone could not have verified this fix, and why `date` reading correctly
*offline* is the stronger statement.

## Nothing regressed

| check | result |
|---|---|
| ssh over USB NCM | works (this evidence was collected over it) |
| Wi-Fi | associates, DHCP lease obtained |
| panel getty (`getty@tty1`) | active |
| failed systemd units | **0** |
| 3.36 GHz Galaxy prime OPP | `3360000` in `scaling_boost_frequencies`, DT node present, 0 warnings |
| `/persist` left mounted | **no** — unmounted before `switch_root` |
| `/persist-ro` left behind | **no** |
| boot reached | `switch-root-synced`, `debian_stage=multi-user`, `failure=none` |

## Files

| file | what |
|---|---|
| `clock.txt` | first boot: `date -u`, `/proc/driver/rtc`, `since_epoch`, `timedatectl` |
| `boot-record.txt` | the persisted record and the helper's kernel-log line |
| `offline-reboot.txt` | **the decisive evidence**: correct time, new boot, offline |
| `regression.txt` | USB, Wi-Fi, panel, failed units, OPP |

## What is still not verified

- **Android and TWRP after the fix.** The raw counter is provably untouched and
  `/persist` is mounted read-only and left clean, so both should be unaffected —
  but neither has been booted since. That is the next test.
- **The failure paths on hardware.** `gts9_rtc_offset=0`, a missing partition, and
  a corrupt offset file were verified on the host against the real `/init` logic
  (`reference/host-tests/rtc-offset/`), not on the tablet.
- **A long power-off.** The offset is a file on UFS, so this must hold, but it has
  not been measured.
