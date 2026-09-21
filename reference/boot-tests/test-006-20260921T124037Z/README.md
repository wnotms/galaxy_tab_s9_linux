# Test 006 — first test with DRAM-cleaned ring writes (2026-09-21T12:40:37Z)

Source commit `b6dd3229b8fb4e2983e3cea27bb2c65c1f07136f` (`source.txt`). Single
change against test 005: the SEC_LOG driver now cleans every ring write to the
point of coherency with `dcache_clean_poc()`, so log bytes cannot be lost in the
writer's cache across a reset.

## What was flashed

Only `boot.img` changed; `init_boot`, `vendor_boot`, `dtbo` and `vbmeta` were
already byte-identical on the device (`pretest-device.txt`, `flash.log`).

| Partition | Before | After (this bundle) |
|---|---|---|
| `boot` | `1d11c1f3…` (test 005) | `68845be7227e56098aa1e141b43e008043740c362091d7d90179924a1d36d321` |
| `init_boot` | `ab89f78b…` | unchanged |
| `vendor_boot` | `c22ab1a8…` | unchanged |
| `dtbo` | `c17418be…` | unchanged |
| `vbmeta` | `9844859b…` | untouched |

Kernel `Image.gz 44e2512f…` (`kernel-sha256.txt`), release
`7.2.0-rc3-gts9wifi-dirty`, layout `image.gz+dtb` in `BUNDLE_INFO`, validator
`BOOT BUNDLE VALIDATION PASSED` (`bundle-validation.log`).

## Observation

Boot requested at 2026-09-21T12:41:06Z (`observation.txt`); capture started
before it and completed the moment recovery returned.

**First kernel evidence ever seen in the ring**: the capture contains exactly one
`Linux version` line — and it is *not* ours:

```text
<5>[    0.000000][    T0] Linux version 5.15.94-Foldiby-+ (alex@Z790-UD) … #1 SMP PREEMPT Wed Jan 31 14:41:24 UTC 2024
```

That is the recovery kernel's own banner (`pretest-device.txt` reports the same
5.15.94 build for the running recovery), i.e. TWRP's kernel, written at
`index 0` when recovery restarted. There is still no `7.2.0-rc3` string, no
`gts9wifi-sec-log` line, no marker and no initramfs milestone.

## What this changed in the diagnosis

The capture file is **2,097,136 bytes every time — exactly the ring's data
area**, so TWRP's `/proc/last_kmsg` exposes the *raw ring*, not a snapshot
bounded by `previous_index`. Combined with the recovery banner sitting at
`index 0`, that gives the real retention problem:

1. the mainline kernel writes its log from `index 0` (the LOGM convention);
2. recovery restarts its own SEC_LOG writer at `index 0` as well, and its
   kernel log runs at roughly 19 KB/s — one to two minutes is enough to
   overwrite everything the mainline kernel wrote;
3. we can only read the ring after recovery exists, which is precisely that
   window.

So an empty mainline log does not distinguish "the kernel never wrote" from "the
kernel wrote and recovery overwrote it". The cache fix was necessary — this test
proves ring *contents* now survive a reset from the writer's side — but not
sufficient, because the next kernel overwrites the same region.

## Next step

Put the evidence where the next kernel cannot reach it: the SEC_LOG driver now
keeps a protected 4 KiB tail window at the end of the reservation (plus a
marker area just before it) holding a rolling copy of the newest console output
and a `GTS9-CONSOLE-REGISTERED` milestone. Recovery would need a full 2 MiB of
its own logging to wrap around into it, which does not happen before a capture
taken immediately after recovery appears.

That is one hypothesis — "the evidence is written but overwritten" — and one
observable consequence: if the tail window shows mainline text in the next
test, the kernel does reach the driver; if it stays empty, the kernel never
reaches `early_initcall` and the fault is earlier.
