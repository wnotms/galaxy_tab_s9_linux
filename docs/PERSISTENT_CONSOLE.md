# Persistent console (Samsung `sec_log_buf`)

The bring-up kernel writes its console into Samsung's `sec_log_buf` ring so a
failed boot can still be read back afterwards. The chain is:

```text
Linux printk
    -> sec_log_buf @ 0x880200000 (2 MiB, board DTS reservation)
    -> warm reset (buttons, panic, or watchdog)
    -> TWRP / recovery
    -> /proc/last_kmsg
```

Driver: `kernel/drivers/samsung-gts9wifi-sec-log.c`
(`CONFIG_SAMSUNG_GTS9WIFI_SEC_LOG=y`, built in, asserted by
`scripts/build-kernel.sh`).

## Why it registers so early

Boot test 1 (`reference/stock/BOOT_TEST_1.md`) boot-looped and left the ring
**empty** of kernel output. The original driver was a `builtin_platform_driver`,
which only registers the console at `device_initcall` time — after clocks,
regulators, SMMU, storage and every other subsystem this bring-up needs to
observe. Anything that dies before that point is invisible.

The console is now registered from an `early_initcall`, the first initcall
level in the kernel. Because it registers with `CON_PRINTBUFFER`, printk
replays everything already in the buffer through it, so the ring receives the
whole log from the first arm64 banner line onward, not just messages printed
after registration.

Registration happens exactly once. Whichever path runs first — the early
initcall or the platform driver — owns the ring; the other leaves it alone so
the boot log is never reset mid-boot.

## Command-line override

The early path reads the region from the device tree node
(`samsung,gts9wifi-sec-kernel-log` -> `memory-region` -> `reg`). It can also be
forced from the kernel command line, which makes capture independent of which
device tree Linux actually ends up with:

```text
gts9_sec_log=0x880200000,0x200000
```

`boot/cmdline.example.txt` carries this parameter, so a bundle built by
`scripts/build-boot-bundle.sh` is covered even if the DTB hand-off is wrong.

## Proof-of-life marker

**Correction (2026-09-21):** absence of this marker is not proof that Linux
was never entered. The current write-back marker neither cleans its cache lines
to RAM nor updates the LOGM indices. Recovery retention is unverified on X710;
see [boot-loop investigation](BOOTLOOP_FIX.md). The conclusions below that infer
an exact failure boundary from absence are superseded by this qualification.


Boot tests 1 and 2 both left the ring empty, which is consistent with two very
different failures: the kernel never started, or it died before any console
existed. The `gts9_sec_log=` handler therefore also writes a short marker
straight into the ring:

```text
GTS9-EARLY-MARKER: arm64 setup_arch reached, early cmdline parsed
```

It is written with `early_memremap()` from `parse_early_param()` inside
`setup_arch()`, which runs after `early_ioremap_init()` but **before**
`paging_init()`, before the device tree is unflattened, and long before any
console or initcall. Reading the ring afterwards therefore answers the
question directly:

| Ring content | Conclusion |
|---|---|
| marker present, no `Linux version` | the image was entered and arm64 setup began; the failure is between `setup_arch` and the console, i.e. still kernel-side |
| marker absent | the kernel never reached `setup_arch`; the fault is in the hand-off (decompression, entry, or the `x0` FDT), not in a driver |
| marker plus `Linux version` and the console line | the kernel boots far enough to log; read the last lines before the reset |

The marker is written at the start of the ring's byte area (the oldest data)
and is deliberately overwritten by the real log once the console registers, so
a successful boot looks exactly as it did before.


## On-memory format

Compatible with the downstream ring the bootloader and recovery use:

| Offset | Field | Meaning |
|---:|---|---|
| 0 | `boot_count` | incremented at every kernel start |
| 4 | `magic` | `0x4d474f4c` ("LOGM"); re-initialises the ring if absent |
| 8 | `index` | monotonically increasing write offset into the byte ring |
| 12 | `previous_index` | kept equal to `index` on every write |
| 16 | `data[]` | byte ring, `reserved size - 16` bytes |

`index` is monotonic and the writes wrap modulo the data size. `previous_index`
is updated on **every** write, not only on a firmware-driven reset: a manual key
reboot out of a panic bypasses the firmware snapshot step, and recovery uses
`previous_index` as the length of `/proc/last_kmsg`.

## Evidence status

- The reservation (address `0x880200000`, size `0x200000`) comes from the
  owner's X710 stock evidence, and boot test 1 confirmed the board DTS node
  wiring in the built DTB.
- The LOGM header layout is **adapted from the physically validated SM-X910
  port**, not re-derived from X710 source. It is a bring-up adaptation from a
  sibling device and is not yet proven on this tablet.
- Whether the ring actually receives the boot log on the X710 is what boot test
  2 decides. Reading it back is the only way to settle it.

## How to read it back

After a failed boot, warm-reboot into TWRP and dump the ring **before doing
anything else**. This is not a formality: boot test 1 showed that TWRP's own
kernel log fills the whole 2 MiB ring within a couple of minutes (the oldest
surviving line in that dump was already 379 s into TWRP's uptime), so a manual
`cat` taken "a moment later" can silently destroy the evidence.

Use the capture tool, which waits for the tablet and pulls the ring the instant
`/proc/last_kmsg` is readable:

```bash
ADB=/mnt/d/android/platform-tools/adb.exe ./scripts/capture-last-kmsg.sh
```

It prints the marker counts and a first verdict. Or do it by hand:

```sh
cat /proc/last_kmsg > /tmp/last_kmsg.txt   # or pull it off the device
grep 'Linux version' /tmp/last_kmsg.txt
grep 'gts9wifi-sec-log:' /tmp/last_kmsg.txt
grep 'GTS9 MAINLINE INITRAMFS REACHED' /tmp/last_kmsg.txt
```

Interpretation:

| What is in the ring | What it means |
|---|---|
| `gts9wifi-sec-log: persistent console ... early_initcall` plus kernel boot lines | the early console works; read the **last** lines before the reset to find the failure |
| `Linux version ...` but no `gts9wifi-sec-log:` line | the kernel booted but the early registration did not run; check the DTB/cmdline |
| nothing at all, still no kernel markers | the kernel is not reaching `early_initcall`; the problem is in the boot image hand-off, not in kernel drivers |
