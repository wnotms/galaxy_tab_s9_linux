# Initramfs architecture: one image became two

Until 2026-09-26 there was one initramfs, built by one script, and its `/init` was
`boot/bringup-init.sh` — the 1500-line script that 200+ physical bring-up tests had
grown. A normal Debian boot reached the root filesystem through a branch inside it:

```
/init (bringup-init.sh)
  -> parse the command line, mount debugfs, recover the display, set up the USB
     gadget, inspect the GPT, clear the BCB, read the RTC, write a hardware report
  -> see gts9_minimal_rootfs=1
  -> exec /minimal-rootfs-init
       -> mount /proc /sys /dev /run
       -> mount the ext4 root, switch_root
```

Everything before the `exec` was dead weight for a production boot, and worse than
dead weight: it was *reachable*. Creating a configfs gadget here and having
Debian's `gts9-usb-acm` tear it down and rebuild it cost a UDC bind/unbind and a
USB re-enumeration on every single boot. The display recovery, the frame buffer
blank cycle, the RTC reads and the report collection all ran before the root was
even mounted.

There are now two images with one job each, built by two scripts that share one
library.

---

## AFTER — PRODUCTION

`scripts/build-minimal-initramfs.sh` → `out/boot-bundle/initramfs-minimal.img`

Its `/init` **is** `boot/minimal-rootfs-init.sh`. There is no trampoline script, no
branch on a command-line token, and no second stage.

```
/init
  1. set PATH
  2. mount /proc                      <- before anything reads cmdline
  3. parse gts9_rootfs=, gts9_minimal_init=, gts9_initramfs_debug=
  4. mount /sys, /dev, /run
  5. source the state library
  6. wait for the root device (bounded)
     mount it ext4                          -> fail: tty1 rescue
     check /newroot/sbin/init is executable -> fail: tty1 rescue
     record the stage history on the root
     move /dev /proc /sys /run into it      -> fail: tty1 rescue
     switch_root
```

That is the entire responsibility, and `tests/test_initramfs_profiles.py` asserts
it from both sides — that each of those steps is present, and that nothing else is.

| | |
|---|---|
| compressed | **1152170** bytes |
| unpacked | 1936011 bytes |
| regular files | 3 (`/init`, the state library, BusyBox) |
| symlinks | 23 applet links |
| firmware | **none** |
| modules | **none** |

## AFTER — DEBUG

`scripts/build-bringup-initramfs.sh` → `out/boot-bundle/initramfs-bringup.img`

Unchanged in purpose: the hardware diagnostics, the mass-storage evidence channel
for a boot with no network, GPT/BCB inspection, RTC telemetry, panel recovery, the
rescue shells, and the legacy `gts9_minimal_rootfs=1` path for reproducing an old
test. It still builds the reboot-mode helper and can still be asked for modules.

| | |
|---|---|
| compressed | **1181696** bytes |
| unpacked | 2018059 bytes |
| regular files | 8 |
| symlinks | 60 |
| capabilities | gadget, MSC, RTC, BCB, display recovery, hardware report |

Both profiles are recorded by an audit and by a machine-readable manifest; see
[Measured](#measured) below.

---

## REMOVED FROM PRODUCTION

Each of these is now the Debian root filesystem's job, or the debug image's.

| removed | why it is not needed before switch_root |
|---|---|
| USB gadget (NCM, MSC, ACM) | Debian's `gts9-usb-acm.service` creates `ncm.usb0` after switch_root. Building one here only meant Debian tearing it down and rebuilding it — a UDC bind/unbind and a USB re-enumeration per boot. The serial functions no longer exist in the kernel at all. |
| display blank/unblank, panel recovery | The panel is driven by the DRM driver and Debian's `gts9-panel-recover.service`. Doing a framebuffer blank cycle in early userspace delays the root handoff for a screen nobody is reading yet. |
| GPT scan, `misc`/BCB write | Recovery interaction is a deliberate, operator-driven action. A production boot must not write the bootloader control block. |
| RTC telemetry | The RTC has no valid time before NTP anyway (the port's records note early timestamps read 1970), and nothing in the handoff depends on the clock. |
| UFS/mmc diagnostics, hardware report, `regulator_summary`, `devices_deferred`, dmesg dump | All diagnostic. They belong to a bring-up image or to a Debian service, and they are the reason the old script carried `dd`, `od`, `sha256sum`, `awk` and `sed`. |
| kernel modules | Live on the rootfs in `/usr/lib/modules/<release>`. The production builder now *refuses* `--modules`. |
| firmware | Lives on the rootfs in `/usr/lib/firmware`; Wi-Fi works from there (test-208/210). The production builder has no firmware option at all. |
| `gts9-exec-default` | **Dead code.** It resets the SIGINT/SIGQUIT dispositions a shell cannot reset, for the panel shell; the panel shell switched to `set -m`, and nothing has invoked the binary since. The audit found it shipped in every image with no caller. |
| the `gts9_minimal_rootfs=1` branch | The production image *is* the minimal path, so there is nothing to branch on. The token is still accepted for compatibility; see below. |

## KEPT

| kept | why |
|---|---|
| auto-reboot to TWRP on failure | A failed handoff must not need a key combination. Label-addressed, one-shot, read back, plain restart. Measured: TWRP unattended in 77 s. |
| stale-BCB clear on every boot | "One request, one boot". Without it the tablet loops back into TWRP; reproduced on hardware before the fix. |
| bounded root-device wait (30 s) | A card that is slow to enumerate must not be a hang, and a card that never appears must be a diagnosable failure. |
| ext4 root mount | The handoff itself. |
| `/newroot/sbin/init` check | Failing before `switch_root` leaves a rescue shell and a record; failing after it leaves nothing. |
| stage record on the Debian root | `/var/log/gts9-minimal-last-boot`. This is the project's only offline evidence channel: a later TWRP session reads it when the panel is dark and there is no network yet. Ten fields by default; `gts9_initramfs_debug=1` adds `cmdline` and `mmc_devices`. |
| the durability syncs | Measured rather than assumed — see [sync cost](#sync-cost). ~10-20 ms per stage for a record of a few hundred bytes, against a handoff that takes tens of seconds. |
| `switch_root` and the four `mount --move`s | The handoff. |
| tty1 rescue shell | The only console left, and the only thing that can explain a failed handoff on the device itself. |

---

## What the production handoff deliberately does NOT do for a rescue

`/dev/ttyGS*` does not exist and no COM port exists either: the gadget has no
serial function and the kernel is built without `CONFIG_USB_CONFIGFS_ACM`. So the
rescue path is `/dev/tty1` first, `/dev/console` as a fallback, and if neither
exists it says so and waits rather than spinning:

```
no usable console for the rescue shell; waiting
```

It never waits for a ttyGS that cannot appear, never tries to create a gadget
shell, and cannot busy-loop: each branch either enters an interactive shell or
sleeps. That is not an aspirational statement — it is what the earlier rounds
established, and this round did not weaken it.

An important consequence for anyone debugging a boot that does not reach Debian:
**there is no channel at all before `gts9-usb-acm` runs.** The initramfs has no
network. A boot that dies before Debian's userspace is observable only on the
panel and through the stage record; TWRP is the recovery path. This is the cost of
the serial removal, and it is the reason the stage record is kept.

## The `gts9_minimal_rootfs=1` token

It no longer controls anything in the production image: that image's `/init` is
the handoff unconditionally. The token is still **accepted** and still **honoured
by the debug image**, which keeps the legacy path for reproducing an old test.

- Phase 1 (this change): production does not depend on it; the debug image still
  supports it.
- Phase 2 (future): mark it deprecated/compatibility-only in the profiles.

It was not removed from the historical profiles in this round, because those
profiles are test fixtures and rewriting them would invalidate stored bundle
hashes for no functional gain.

---

## Measured

### Sizes, before and after

| metric | before (one image) | production | debug |
|---|---|---|---|
| compressed bytes | 1222311 | **1152170** | 1181696 |
| unpacked bytes | 2067157 | 1936011 | 2018059 |
| regular files | 9 | **3** | 8 |
| symlinks | 60 | **23** | 60 |
| firmware bytes | 52012 | **0** | 0 (allowlist, unused) |
| `/init` size | 69669 (`bringup-init.sh`) | **12689** (the handoff) | 69669 |

The production image is **2.5 % smaller compressed** (29526 bytes). **That is not
the point** and should not be read as the result: BusyBox dominates both images, so
the byte count barely moves either way. The result is what the image can *do* — the
audit reports `contains_usb_gadget=no`, `contains_msc=no`,
`contains_gpt_parser=no`, `contains_rtc_telemetry=no`, `contains_bcb_write=no`,
`contains_display_recovery=no`, `contains_hardware_report=no` for production, and
`yes` for the capabilities the debug image exists to provide.

### What actually executes on a healthy boot

The distinction that matters is not the size of the script but the number of
statements the Debian boot actually runs. `/init` is 521 lines; the healthy path is
**54 statements**, and every one of them is either the handoff or a record of it:

| what | statements |
|---|---|
| stage markers and the state library | `minimal_state_init`, 6 stage writes, `persist_enable` |
| consume a stale recovery request | `minimal_clear_stale_bcb` (one sysfs read when clear) |
| find the root | one bounded `while` with `sleep 1` |
| mount it | `mkdir /newroot`, `mount -t ext4`, the `/newroot/sbin/init` check |
| hand over | `mkdir` the four mountpoints, one `mount --move` per vfs, `switch_root` |
| durability | `sync` before the irreversible step |

Everything else in the file is a failure branch that does not run, a function
definition, or a comment. The trampoline blocks are two `if` statements that are
false by default, and the rescue path is only reached through `minimal_fail`.

Measured, not counted: the whole handoff occupies **~100 µs** of monotonic time on
the tablet, with `/init` entered and the root filesystem mounted 66 µs apart.

### The boot record is gated, not verbose

Measured on the tablet before this change: the record was **1994 bytes**, of which
`cmdline` was **1163** - the vendor_boot command line carries the whole Samsung
option string, and it was being copied into a file whose purpose is to let someone
in TWRP see how far a boot got.

It is now ten fields (~256 bytes): `format_version`, `origin`, `boot_id`,
`kernel_release`, `root_device`, `stage`, `stage_history`, `failure`, `timestamp`,
`uptime_seconds`. `gts9_initramfs_debug=1` adds `cmdline` and `mmc_devices`, which
is exactly when they are worth reading - a handoff that appears to have ignored an
option.

The Debian helper appends only `debian_*` keys and rewrites the rest verbatim, so a
gated record round-trips unchanged; verified by running it against a record written
with the gate off (initramfs block preserved, 11 `debian_*` keys added, `cmdline`
still absent).

### Audits

`scripts/audit-initramfs.sh` prints the contents, the call-graph classification
(`production_required` / `debug_only` / `currently_unreferenced`) and the
capability probes. Records:

- `reference/initramfs-audit/2026-09-26-before.txt`
- `reference/initramfs-audit/2026-09-26-after-production.txt`
- `reference/initramfs-audit/2026-09-26-after-debug.txt`

### Manifests

Each build writes `<image>.manifest`, and `build-boot-bundle.sh` copies it into the
bundle as `initramfs.manifest`. The validator reads the profile from there and
cross-checks it against the content of the extracted `/init` — never from the
filename, because inside a bundle both profiles are called `init_boot.img`.

### Sync cost

Recorded in `reference/initramfs-audit/sync-cost-measurement.txt`. Measured on the
tablet with the root on the microSD:

```
idle:         150 ms for the first sync, then 0 ms
4 MiB dirty:  260 / 130 / 120 ms
4 KiB dirty:   10 /  10 /  20 ms
```

The record is a few hundred bytes, so the realistic cost is ~10-20 ms per stage.
The syncs were **kept**: the flush is proportional to dirty data rather than to the
number of calls, the total is on the order of 0.2-0.3 s against a handoff of tens
of seconds, and the record it protects is the only offline evidence channel. The
measurement is kept so the decision does not have to be re-litigated, and it notes
that the initramfs BusyBox does support `sync -f FILE` if a future change has
evidence that a narrower flush is safe.

### Applet derivation

`reference/initramfs-audit/2026-09-26-production-applets.txt` records how the
production applet list was derived from what the two scripts actually invoke, and
which debug tools it deliberately excludes.

---

## Physical verification

See [test-213](../reference/boot-tests/test-213-production-initramfs/README.md) for
the boot, the timings, the failure test and the hashes.

The production handoff booted Debian with SSH back 45 s after reboot (same as the
baseline), the whole initramfs path taking ~100 µs of monotonic time, and all
acceptance checks passing: `console=tty0`, zero `/dev/ttyGS*`, `ncm.usb0` only,
`ssh.service` active, 0 failed units, 0 AF_VSOCK warnings, and the gadget created
once at 4.5 s by Debian rather than twice.

**Read the two gaps above before treating this as finished.** The failure test
succeeded and left the tablet needing physical recovery, which is a real cost of an
initramfs with no network.

---

## Two gaps the physical failure test found

The brief asked for a deliberate failure test - boot with
`gts9_rootfs=/dev/does-not-exist`, confirm the handoff reaches a tty1 rescue shell
after ~30 s without PID 1 exiting or panicking. The rescue path behaved exactly as
designed. Both of these were found by running it, not by reading the script, and
neither would have been visible from the host.

### 1. The rescue shell was not escapable

This image has no USB gadget and no Wi-Fi, so no network; there is no serial port;
and the applet list had no `reboot` or `poweroff`. Nothing inside the shell could
leave it, so recovering the tablet needed a physical key combination - which cost
the owner a recovery trip. A rescue shell that cannot be left is a trap, not a
rescue.

`reboot` and `poweroff` are now in the applet list (in `/sbin`, already on the
handoff's `PATH`) and the banner says so. They are escape hatches, not diagnostics;
everything that made the old image risky stays out.

### 2. The rescue banner could be invisible

`gts9-panel-recover.service` is a **Debian** service, and it is what cycles the
framebuffer when the panel's cold-boot enable reads a dead DDIC
(`ana38407 panel id: 00 00 00`). It runs at ~3.7 s on a healthy boot. In the
rescue path Debian never starts, so that recovery never runs - and on a cold boot
that hit the zero-ID case the rescue banner would go to a screen nobody can see,
with no network and no serial port to fall back on.

Restoring display recovery unconditionally was rejected for the same reason it was
removed (a DPU modeset on the critical path, where test 178 caught an intermittent
hang). Instead the framebuffer cycle now runs **at the end of the rescue path
only**: a healthy boot pays nothing, and the one boot that needs it is the one with
nothing left to lose. Every wait is bounded, a missing framebuffer is reported and
ignored, and it does not parse dmesg because production has no dmesg applet.

This is the one place where the boundary is a *position* rather than a
prohibition, so it is enforced that way - the validator checks that the call sits
inside `minimal_rescue_shell()`'s body and that nothing between the root mount and
`switch_root` touches the framebuffer. Writing that check had its own bug, listed
below.

## Bugs this work found in its own tooling

Recorded because each produced a confident wrong answer rather than an error, and
each is the kind of thing that would otherwise be rediscovered later.

1. **`[^\n]` is not "not a newline" in POSIX ERE.** It is a bracket expression
   containing a backslash and the letter `n`, so `mkdir[^\n]*usb_gadget` matched
   nothing and the gadget rule was silently inert in five places across the
   validator, the shared library and the audit script. Every one of them was a
   false PASS. Found by injecting a gadget-creating line into a production `/init`
   and re-validating: the validator said PASS.
2. **`cpio -i bin/busybox` does not create the parent directory**, so the busybox
   extraction failed silently and the aarch64 and static-ELF checks never ran.
   "busybox present" passed and the two checks underneath simply did not appear.
3. **The audit's gadget probe had the same `[^\n]` bug**, so it reported
   `contains_usb_gadget_creator=no` for a tree that plainly creates one.
4. **A plain `grep init` classified nearly every file as `production_required`**,
   because it matched `minimal_state_init`, `initialized` and every `init-found`
   stage marker. The classifier now requires a real reference context.
5. **`basename(readlink /init)` can never equal `bringup-init.sh`**, because the
   builders *copy* a source to `/init`. The probe reported "no" for a bringup image
   that plainly was one. It now identifies the script by content.
6. **The debug builder lost its applet-list definitions and its `fail` helper**
   during the refactor into the shared library. That is not a shell syntax error,
   so `bash -n` passed and the build failed with `required_applets: unbound
   variable`. `gts9_fail` now lives in the library.
7. **Two of the new tests matched comments rather than code** — the same mistake as
   the validator's `grep ttyGS` false positive — and failed on files that were
   correct. The whole test file now strips comments before checking anything.
8. **The panel-placement check compared the wrong line.** A shell function must be
   defined before it is called, so the helper's body necessarily sits *above*
   `minimal_rescue_shell()` in the file. The first version compared the framebuffer
   write against the rescue function's start and failed its own correct code. It
   now checks the call site.
9. **The applet scanner reported variables as missing programs.** Lowercase
   locals put in command position by a line-based scan (`panel_fb=/sys/...` then
   `while [ ! -w "$panel_fb" ]`) were reported as missing applets, and a `;` inside
   a quoted message split the string and produced `cannot` as a command. Both are
   fixed by collecting assigned names and stripping quoted strings; the scanner is
   re-verified by injecting `fsck.ext4` and confirming it is caught.

## Invariants this change did not touch

Asserted by `tests/test_initramfs_profiles.py` so a future edit cannot drift them:

- `systemd.ssh_auto=no` on all 11 command-line profiles (the Gunyah/vm-other
  AF_VSOCK fix from the previous round);
- `console=tty0` as the only console, with no `console=ttyGS*`, `console=ttyMSM0`
  or `earlycon` back;
- `CONFIG_USB_CONFIGFS_ACM`, `CONFIG_USB_CONFIGFS_SERIAL` and
  `CONFIG_U_SERIAL_CONSOLE` still off/absent in the kernel fragment;
- `/etc/gts9-usb-net` present and the gadget helper still creating `ncm` only.
