# Test 005 — bootloop-fix candidate (2026-09-21T12:34:10Z)

Source commit `89a6601628d5285f53f1119b72ddd150b1c12c79`, workflow commit
`c426e6803a3092e40eeb6487b6039f1967a47a5a` (`source.txt`). Candidate described
in `docs/BOOTLOOP_FIX.md`: PID 1 survives console EOF, `panic=0`, generic
initramfs moved into `init_boot`, bootloader-enabled clocks/regulators retained.

## What was flashed

`flash.log` is the full transcript. `boot`, `init_boot` and `vendor_boot` were
written and read back; `dtbo` already matched and was not rewritten; `vbmeta`
and `recovery` were not touched.

| Partition | Before (`pretest-device.txt`) | After (bundle, `bundle-sha256.txt`) |
|---|---|---|
| `boot` | `ae496575…` (test 004) | `1d11c1f3bc10aade4e60543688e7d2e6a12c073e5d434672c4141750da1679ba` |
| `init_boot` | `26dd7517…` | `ab89f78b9eef19292bf07e86868171b1d6d96363b2212303c488ac1902656b9e` |
| `vendor_boot` | `b9f0cfd1…` | `c22ab1a8982af5d5b49b141043c38bcc78bc64bff200f39ad1f34671023888c9` |
| `dtbo` | `c17418be…` | unchanged |
| `vbmeta` | `9844859b…` | unchanged |

Kernel manifest in `kernel-sha256.txt` (`Image.gz 60fe7f83…`), layout metadata
in `BUNDLE_INFO`, validator output in `bundle-validation.log`
(`BOOT BUNDLE VALIDATION PASSED`).

## Observation

Boot requested at 2026-09-21T12:35:07Z (`observation.txt`), capture started
before it (`capture.log`).

Owner's report, recorded verbatim in substance: **the endless reboot is gone**;
the tablet now sits on the Samsung logo instead of resetting, and recovery was
re-entered afterwards. The boot attempt was not observed to reach a visible
shell, which is expected: this kernel has no panel driver, so the panel keeps
whatever the bootloader drew.

## Captured ring

`last_kmsg-post.txt` was pulled immediately after recovery came back
(SHA-256 `6c3be33ac8034680a1ef7a721f3a9444b4b2f54f2f9d64fc1aa6c7ba5ca6053d`).
It contains the stock Android kernel log from an earlier boot followed by the
XBL/ABL log of the most recent attempt, ending at `UEFI End`.

No mainline evidence was found in it:

```text
GTS9-EARLY-MARKER   0
Linux version       0
gts9wifi-sec-log    0
GTS9 MAINLINE…      0
```

`ignore_console_null` appears once, in ABL's echo of our command line — so the
new cmdline did reach the bootloader.

## Interpretation and limits

- The behaviour change (reset loop → stable hang on the logo) is real and is
  consistent with the repair: the previous loop is explained by PID 1 exiting
  on console EOF and `CONFIG_PANIC_TIMEOUT=-1` rebooting instantly.
- This test does **not** prove the kernel reached `/init`, and the empty ring
  does **not** prove it did not. `sec_log` writes go through a write-back
  mapping; a reset does not clean the writer's caches, so the newest log lines
  are exactly what disappears. Every capture so far, including this one, ends
  with the bootloader's own (uncached) log.
- `pretest-last_kmsg.txt` is the ring as found before the flash, for comparison.

## Next step

Fix the retention path before drawing conclusions from an empty ring: clean the
ring writes to the point of coherency (`dcache_clean_poc`) in the sec_log
driver, then repeat the test. The bundle for that test changes only `boot.img`
(`init_boot` and `vendor_boot` are byte-identical to what this test left on the
device).
