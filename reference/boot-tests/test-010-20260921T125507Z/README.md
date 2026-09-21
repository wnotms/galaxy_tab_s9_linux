# Test 010 — mainline userspace reached on the SM-X710 (2026-09-21T12:55:07Z)

**Milestone test. The owner observed the tablet power itself off while it was
running the kernel built by this repository.**

That single physical event is the acceptance chain for this phase:

```text
Samsung ABL -> mainline Linux -> /init (BusyBox) -> poweroff
```

A hung or panicking kernel cannot power a tablet off, and `panic=0` removes the
only way the kernel could fake it. Nothing else in the boot path can turn the
device off either — the bootloader is gone by then.

## Artifacts under test

No reflash: these are the images test 009 left on the device, verified again
before the run (`pretest-device.txt`).

| Partition | SHA-256 |
|---|---|
| `boot` | `3553812581f44b99e847eac64f13a4d75941dd3fd46b1cf5ce0b876a66a5ccc5` |
| `init_boot` | `eb11162ff362f77db362bd3c7a6462f72bd36606304686a6f06516886397b85c` |
| `vendor_boot` | `7c1520aaa05e2d1f5583a3d666ffeae3797cefeb0e546a2e34dc7fe955508b1a` |
| `dtbo` | `c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3` |
| `vbmeta` | `9844859b45716a2a098c96cd38b15bb378e784dab34843d1edcd2704236d36e4` (untouched) |

Kernel: `Image.gz 95a95f4c…`, release `7.2.0-rc3-gts9wifi-dirty`, upstream
`a13c140cc289c0b7b3770bce5b3ad42ab35074aa`. `BUNDLE_INFO` records the
`initramfs_location=init_boot` layout; `bundle-validation.log` records
`BOOT BUNDLE VALIDATION PASSED` for exactly these images.

The mechanism under test is `gts9_userspace_proof=<seconds>`: `/init` parses it
from `/proc/cmdline` and, in a background job, logs and then runs
`poweroff -f`, falling back to `reboot -f`.

## Procedure and observation

- 2026-09-21T12:55:11Z: reboot requested, capture not started (the device would
  be off, not in recovery, if the test succeeded).
- Owner was asked to touch nothing and watch for up to 120 s.
- **Owner's observation: the tablet switched itself off** (`observation.txt`).
- No ring capture exists for this test, and by design it could not have helped:
  test 007 showed the bootloader overwrites the whole reservation. The absence
  of a capture is recorded here rather than left unexplained.

## What is now established

- `booted` — Linux runs on the SM-X710 from this port.
- `initramfs reached` — BusyBox `/init` executes, mounts the pseudo-filesystems
  and can act on hardware (it powered the tablet off).
- The "stuck on the Samsung logo" state seen in tests 005–008 is a **running
  initramfs** waiting on a console that does not exist (no panel driver, no
  reachable UART, `console=null` appended by the bootloader), not an early
  kernel failure. This matches the owner-supplied July log, which shows the same
  userspace stage with its own instrumentation.

## What is explicitly *not* established

- The persistent console never worked as an evidence channel on this tablet
  (test 007): `sec_log_buf` is overwritten by the bootloader on every boot.
  Mainline logs are therefore still unavailable after a reboot.
- USB rescue does not work yet: `a600000.usb` defers because the eUSB2 PHY
  (`88e3000.phy`) and `1fc0000.clock-controller` defer (owner-supplied July log,
  and test 008's silence is consistent with it).
- No storage, display, touch, GPU, radio, audio or charging support has been
  validated. Nothing here says any of them works.

## Next steps

1. Stop shipping the proof by default: `gts9_userspace_proof` stays in the
   initramfs as an opt-in, and is removed from `boot/cmdline.example.txt` so
   later tests are not powered off underneath them. Re-adding the parameter
   reproduces this test at any time.
2. Storage next (UFS and microSD), because it is the prerequisite for a root
   filesystem and for module/firmware loading.
3. Then the USB rescue channel, whose blocker list is already known from the
   July log: eUSB2 PHY, then `1fc0000.clock-controller`, then `a600000.usb`.
   That also restores a live evidence channel, which this port still needs
   because the RAM one is unusable.
