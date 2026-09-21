# Reporting bring-up state through the RTC

## The problem

Every channel this board has for getting evidence out is broken:

| channel | status |
| --- | --- |
| `sec_log_buf` ring | the bootloader's own log fills it on every boot (test 007) |
| panel / `simple-framebuffer` | command-mode panel, never refreshes (test 015) |
| USB gadget | no device ever appears on the host (tests 008, 011, 013, 014, 017) |
| internal storage | UFS does not enumerate, so every partition is unreachable (test 017) |
| microSD | not proven; the card is in the slot but no block device appears (tests 012, 017) |
| power-off delay | works, but carries only 3 bits and needs someone to time it |

When UFS is down, *nothing* on the tablet can hold a file.  What is left is the
PMK8550 RTC: battery backed, driven by `rtc-pm8xxx` (built in, matches
`qcom,pmk8350-rtc`), writable by busybox `hwclock`, and readable from recovery
with a single `date` call.  It cannot carry a log, but it can carry one 16-bit
word - enough to say exactly where storage bring-up stops.

## Encoding

`/init` sets the clock to **2031-01-01T00:00:00Z + code** and writes it to the
RTC, where `code` is a 16-bit value.  Since test 020 it writes it **twice**:
once before the report is collected, so the outcome of the write is part of the
dmesg that travels with the report, and once after persistence, so the value
left behind records that the report reached a medium.  The write is verified
through `/sys/class/rtc/rtc0/since_epoch` - the kernel's view of the hardware
clock, not the system clock - and retried with a correction if it was rounded.

```
code = (epoch read back from the RTC) - 1924992000

bits 0-3    microSD stage          bits 4-7   UFS stage
bit  8      USB device controller registered
bit  9      sdhc_2 in /sys/kernel/debug/devices_deferred
bit  10     ufshc in /sys/kernel/debug/devices_deferred
bit  11     the bring-up report was persisted somewhere (second write)
bits 12-15  checksum = nibble sum of bits 0-11
```

`stage` is the highest step that storage bring-up reached:

| stage | meaning |
| --- | --- |
| 0 | no platform device (DT node missing or disabled) |
| 1 | platform device present, no driver bound |
| 2 | driver bound, no host registered |
| 3 | host registered, no device (no card / no LUN) |
| 4 | device present, no block device |
| 5 | block device present |

The marker is the date: the RTC is a real clock and normally shows the real
time, so *any* date inside 2031-01-01 is a state word, and anything else means
nothing was written (no `/init`, no `/dev/rtc0`, or a failed write).  The
checksum makes a rounded or partial write fail closed instead of being read as
a different state.

## Off by default: SPMI writes block this kernel

Writing the RTC is a *write* over SPMI, and on this board an SPMI write blocks
the calling thread uninterruptibly: `timeout` cannot break it, and the same hang
took the SDAM reboot-mode write in test 024.  Tests 021-027 therefore sat at the
logo and never wrote a report.  Every SPMI *read* works - card detect, the RTC
registers, the regulators, the ADC - which is why the card and UFS paths are
fine.

So `gts9_rtc_report=1` is opt-in and **not** in `boot/cmdline.example.txt`; the
storage stages it carries are in the report anyway.  The channel comes back when
the SPMI write path is understood.

## Reading it

```sh
ADB=/mnt/d/android/platform-tools/adb.exe ./scripts/read-rtc-state.sh
```

The tablet only has to be on adb - TWRP is enough, and it does not matter
whether the boot before it ended in a power-off or a reset.  `--epoch` decodes
a value read by hand.

## What it reports now

With storage up (test 020), the card carries the report and the RTC word is the
fallback - it says at a glance whether both storage controllers reached stage 5
(block device present) and whether the gadget registered, which is exactly the
line tests 012-019 could not cross.

## Limits

- One word per boot: the next boot overwrites it.
- It changes the tablet's clock.  Android re-syncs from the network once it
  boots; recovery shows the 2031 date until then.
- It says *where* bring-up stops, not *why*.  The why is in
  `/sys/kernel/debug/devices_deferred`, the regulator summary and `dmesg`,
  which are collected into the report that this channel exists to replace -
  see `docs/FIRST_BOOT_TEST.md` and `scripts/read-bringup-report.sh`.
- The RTC is written only when the kernel command line asks for it
  (`gts9_rtc_report=1`), so a boot without it leaves the clock alone.
