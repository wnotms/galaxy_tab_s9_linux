# Test 007 — protected tail window (2026-09-21T12:45:38Z)

Source commit `d99744d520b7ce8de5035de4651633d0fc7791bf` (`source.txt`).
Single change against test 006: the SEC_LOG driver mirrors the newest console
output into a 4 KiB window at the **end** of the reservation and writes a
`GTS9-CONSOLE-REGISTERED` milestone there, on the theory that recovery's own
logging (which restarts at `index 0`) overwrites the start of the ring but
would need a full 2 MiB of its own writes to reach the end.

## What was flashed

Only `boot.img` (`flash.log`, `pretest-device.txt`):

| Partition | Before | After |
|---|---|---|
| `boot` | `68845be7…` (test 006) | `3553812581f44b99e847eac64f13a4d75941dd3fd46b1cf5ce0b876a66a5ccc5` |
| `init_boot`, `vendor_boot`, `dtbo`, `vbmeta` | unchanged | unchanged |

Kernel `Image.gz 95a95f4c…`, release `7.2.0-rc3-gts9wifi-dirty`,
`BOOT BUNDLE VALIDATION PASSED`.

## Result: the tail window is bootloader text

Capture `last_kmsg-test007-20260921T124551Z.txt` (2,097,136 bytes, SHA-256
`178c9fd3d07363600a03ab3fb0c9596b35b74a0748fd9ff2308a875e89588802`). The last
4 KiB is `[ ABL ]`/`[ XBL ]` text. Neither `GTS9-TAIL-WINDOW` nor
`GTS9-CONSOLE-REGISTERED` nor any `7.2.0-rc3` string is present anywhere in the
ring.

## The measurement that settles the retention question

Offsets inside the 2 MiB data area:

```text
[ ABL ]                 count=2725  first=0x00003e  last=0x1ffc79  span=2096187
[ XBL ]                 count=2323  first=0x000394  last=0x1fffc6  span=2096178
signal_normal_booting   count=8     first=0x00d6d0  last=0x1ffba9
Linux version           count=1     first=0x025c2d   (recovery kernel's own 5.15.94)
7.2.0-rc3               absent
GTS9-TAIL-WINDOW        absent
GTS9-CONSOLE-REGISTERED absent
```

The bootloader's own logging **spans essentially the entire ring** (2,096,187 of
2,097,136 bytes) across eight recorded boot sessions, and the newest session
ends at the very end of the ring — which is where this test put its protected
window. So the end of the ring is not protected either: the bootloader claims it
on the next boot, before recovery can read anything.

`sec_log_buf` is therefore **not usable as a cross-reset channel in this boot
flow**: writes from the mainline kernel can always be overwritten by the next
boot's bootloader log, whatever offset they use, and the channel is read only
after that bootloader has run.

## Consequences

- Every "empty ring" observation in tests 1–7 is explained without needing to
  know whether the kernel wrote anything. The channel cannot answer the
  question, so no conclusion about kernel entry may be drawn from it.
- The cache fix from test 006 remains correct and necessary (it is why ring
  writes survive at all), but it is not sufficient.
- Persistent RAM evidence needs a region the bootloader does not write; none is
  known yet. `pstore`/`ramoops` in an as-yet-unvalidated reservation would be
  the standard route, but it needs a region proven not to be used by the boot
  chain, and the owner's guidance is explicit about not guessing one.

## Next step

Stop paying for persistence and use a **live** channel instead: the bring-up
initramfs now brings up a USB CDC-ACM gadget (the same port the bootloader
leaves in device mode, which recovery already uses for adb) and streams
`/dev/kmsg` onto it. A live channel cannot be overwritten by a later boot: if
the script runs, the host sees the port; if it does not, nothing appears. That
also happens to be the M2 rescue path in `docs/MAINLINE_PORT_PLAN.md` rather
than another diagnostic detour.
