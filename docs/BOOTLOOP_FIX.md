# SM-X710 boot-loop investigation and repair candidate

## Evidence and scope

Reference: the local `Samsung/ubuntu-galaxy-tab-s9-ultra` checkout, origin
`agcarbajo/ubuntu-galaxy-tab-s9-ultra`, commit
`32273b0a410b3e73b20a3a2451e24260fb2a36bd`. See `kernel/PROVENANCE.md`.
The Linux pin, immutable stock seed and X710 DTB are unchanged.

Boot-test-4's existing log (`.work/boot-logs/last_kmsg-test4-20260921T120336Z.txt`)
shows kernel decompression, selection of the 175387-byte X710 tree, the invalid
DTBO fallback, and ABL's `console=null`. It contains no mainline boot milestone.
That does **not** establish an exact failing instruction or prove kernel entry.

The earlier claim that the compressed file's appended-DTB offset proves a bad
runtime FDT address is unsupported. The [arm64 boot protocol](https://docs.kernel.org/arch/arm64/booting.html)
requires an aligned physical DTB address in x0; the offset in a gzip payload is
not that address. The reference port uses the same unpadded concatenation.
Test 4 removed that concatenation and still failed. APPEND_DTB defaults to the
reference route (1); 0 remains available for controlled comparison.

Likewise an absent early marker cannot conclusively locate the failure: the
existing marker uses a write-back mapping, does not clean its data to persistent
RAM or publish the LOGM ring indices, and its read-back path has not been verified
on X710. Tests 1–3 are historical observations, not proof of a pre-Linux failure.
No MMU-off assembly instrumentation is added by this repair.

## Changes

- Preserve PID 1. The old `exec /bin/sh` exits on EOF or `exit`; exiting PID 1
  causes Linux's `Attempted to kill init!` panic. Reopen `/dev/console` after
  mounting devtmpfs, run the shell as a child and retry with a delay. Emit the
  userspace milestone after /dev/kmsg is available so it survives a missing tty.
- Stop immediate panic reboot. The seed's `CONFIG_PANIC_TIMEOUT=-1` reboots
  immediately on a panic. The bring-up override and cmdline now use zero.
  This retains the failure for inspection; it does not cure a panic or disable
  a firmware watchdog.
- Import the reference's opt-in `ignore_console_null` patch, and request both
  tty0 and the UART. An unavailable panel/UART is still possible; PID 1 survives
  either case. This patch does not add panel support.
- Retain bootloader-enabled clocks, power domains and regulators using the
  reference's `clk_ignore_unused pd_ignore_unused regulator_ignore_unused`.
  Providers not yet claimed by mainline drivers must remain powered during
  bring-up. These are temporary bring-up settings, not a power-management fix.
- Match the reference ramdisk layout: BusyBox `/init` in the generic
  `init_boot.img`, an empty platform ramdisk in `vendor_boot.img`. Limit the
  packed generic archive to 7 MiB and check both archives after unpacking.
  This removes a reference mismatch; the old vendor-only layout was not proven
  to be the cause of the observed resets.
- Complete the pre-existing local early-marker rename by calling
  `gts9_sec_log_early_marker(0, base)`. Preserve that local work; no callers for
  its other diagnostic slots are introduced.
- Require ccache when `USE_CCACHE=1`; fail instead of silently compiling without
  it. Assert LZ4 decompression and the panic timeout in the resolved config.
  Include the kernel release file in the build hash manifest.

## Rebuild

```sh
USE_CCACHE=1 KERNEL_CLEAN=1 BUILD_MODULES=0 JOBS=12 ./scripts/build-kernel.sh
./scripts/build-bringup-initramfs.sh
MKBOOTIMG=$PWD/.work/tools/mkbootimg.py AVBTOOL=$PWD/.work/tools/avbtool.py \
  ./scripts/build-boot-bundle.sh \
  --initramfs out/boot-bundle/initramfs-bringup.img \
  --cmdline boot/cmdline.example.txt --bootconfig boot/bootconfig.example.txt
./scripts/validate-boot-bundle.sh
```

## Local validation (2026-09-21)

- `USE_CCACHE=1 KERNEL_CLEAN=1 BUILD_MODULES=0 JOBS=12` build: passed,
  release `7.2.0-rc3-gts9wifi-dirty`. The compiler command used `ccache clang`
  and the inherited cache directory `/home/ms/.cache/ccache`.
- `bash -n scripts/*.sh`, `sh -n boot/bringup-init.sh`, `git diff --check`: passed.
- `python3 -B -m unittest discover -s tests -v`: 3 tests passed, covering
  shell EOF/missing console and mandatory/invalid ccache selection. These are
  host lifecycle tests, not emulation of PID 1 on the tablet.
- Default appended-DTB bundle and separate `APPEND_DTB=0` bundle: both printed
  `BOOT BUNDLE VALIDATION PASSED` after unpacking their actual contents.
- Negative packaging test: replaced init_boot with an empty generic archive,
  regenerated its AVB footer and SHA manifest, and confirmed validation failed
  specifically on the missing `/init` and BusyBox. Correct hashes alone do not
  allow an unbootable ramdisk through.
- No modules were built for this minimal-initramfs test. Stock-to-mainline
  Kconfig migration warnings and the pre-existing diagnostic function's missing
  prototype warning remain; neither prevented the build.

Build log: `.work/build/bootloop-fix-build.log`. Validation logs:
`.work/tests/{regressions,bundle-validation,no-appended-validation}.log` and
`.work/tests/empty-generic-rejected.log`.

Kernel manifest:

```text
60fe7f832f1a5d36bed84ffd56cb7ab86cd1234840fd573ba3cb198425eac523  Image.gz
1c105090a0c087334435e19fb9f99047ac32865994baf372511846a0a367083c  sm8550-samsung-gts9wifi.dtb
99a48236b320689f25214a007bc9cc0d719a26a91bd9f06efaf733d001952dcb  config
b3f154357931f9e2ddce4bd3b37facae84a69e93a280dbb9bb877f7c824d5658  kernel.release
```

Default bundle manifest (`out/boot-bundle/SHA256SUMS`):

```text
1d11c1f3bc10aade4e60543688e7d2e6a12c073e5d434672c4141750da1679ba  boot.img
c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3  dtbo.img
ab89f78b9eef19292bf07e86868171b1d6d96363b2212303c488ac1902656b9e  init_boot.img
15467d94723539b4f94409199b8f5ee251da1ec5935c747a617bd99013a4058d  initramfs-bringup.img
b95e5ef931fbe588f8574c06331db56ae906b1ac91ed73204704b35cb220b3d4  vbmeta.img
c22ab1a8982af5d5b49b141043c38bcc78bc64bff200f39ad1f34671023888c9  vendor_boot.img
```

## Physical follow-up

Status update (test 010, `reference/boot-tests/test-010-20260921T125507Z/`):
**the repair is physically confirmed.** The owner watched the tablet power
itself off while running this kernel, which only `/init` can do - so PID 1
survived, the initramfs ran, and `ABL -> Linux -> BusyBox /init` is established
on hardware. The reboot loop is gone and the remaining "stuck on the logo" state
is the running initramfs waiting on a console that does not exist.

Original status line, kept for context: repair candidate, **not physically
boot-verified**. The EOF failure is
reproduced locally; there is no hardware trace proving it caused tests 1–4.
Successful compilation/packaging cannot establish that the tablet boots.

Use `docs/FIRST_BOOT_TEST.md` for the manual recovery-backed test. In particular,
**init_boot now changes too**: writing only boot/vendor_boot leaves the old empty
generic ramdisk and loses `/init`. Use the new bundle hashes to identify every
changed image. Nothing here flashes a device or requires changing vbmeta.

Capture last_kmsg immediately after the next attempt. Look for the new kernel
release, `gts9wifi-sec-log`, `GTS9 MAINLINE INITRAMFS REACHED`, the shell-retry
message and any panic. If it still resets without these, further hardware
handoff/persistence diagnostics are required; do not infer success from a black
screen or absence of logs.
