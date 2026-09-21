# First controlled physical boot test — SM-X710 (gts9wifi)

This is the procedure for the **first** time a mainline kernel built by this
repository is written to the tablet. Read it end to end before running any of
it. Every command that writes to the device is manual and deliberate; nothing
in `scripts/` flashes anything.

## 1. What this test does and does not prove

The only chain under test:

```text
Samsung ABL
    |
    v
mainline Linux 7.2-rc3 (this repository)
    |
    v
persistent sec_log console (Samsung sec_log_buf)
    |
    v
BusyBox /init
    |
    v
interactive initramfs shell
```

Success is exactly that chain. The following are **not** success criteria for
this test and must not be used to judge it:

```text
display        touch          GPU            Wi-Fi          Bluetooth
audio          charging       camera         GNOME          systemd
```

They are later milestones. A boot that reaches the initramfs shell with a black
panel is a **success**; a boot that shows a Samsung logo and then resets is not.

Status vocabulary (`AGENT.md`): this test can produce `booted` and
`initramfs reached`. It cannot produce `physically verified` — that needs
repeated, characterised tests. Never upgrade the project status beyond what the
evidence in section 9 shows.

## 2. Prerequisites — verify them, do not assume them

| Prerequisite | How to check (from TWRP or a root shell) | Expected |
|---|---|---|
| unlocked bootloader | `getprop ro.boot.verifiedbootstate` | `orange` |
| TWRP installed and bootable | reboot to recovery | TWRP UI appears |
| AVB verification already disabled | `getprop ro.boot.veritymode` / existing TWRP install | device already boots TWRP |

If TWRP is not installed yet, installing it is out of scope here: it is done
with Odin from Download Mode, and it is what normally brings the AVB-disabled
`vbmeta` with it. **Do not use this repository's `vbmeta.img` on a device that
does not already boot an unsigned boot image.**

## 3. Step 1 — read-only partition layout audit

The partition sizes this repository pads its images to were taken from the
sibling SM-X910 port. They are an assumption about the X710 until checked on
the device.

From TWRP (`Advanced` → `Terminal`), with the repository's
`scripts/check-device-layout.sh` copied to the SD card:

```sh
sh /external_sd/gts9/check-device-layout.sh | tee /external_sd/gts9-layout.txt
```

Compare the reported sizes with section 6. **Do not continue while any
partition reports `MISMATCH` or `MISSING`:** update
`scripts/build-boot-bundle.sh`, `scripts/validate-boot-bundle.sh` and
`scripts/check-device-layout.sh` to the real sizes first, rebuild, re-validate.

Save `gts9-layout.txt` with the test record.

## 4. Step 2 — mandatory backup of the stock boot chain

**Before flashing anything.** This is not optional.

```sh
mkdir -p /external_sd/gts9-stock

for p in boot init_boot vendor_boot dtbo vbmeta; do
    dd if=/dev/block/by-name/$p of=/external_sd/gts9-stock/$p.img bs=4M
done

sha256sum /external_sd/gts9-stock/*.img | tee /external_sd/gts9-stock/SHA256SUMS
```

Then verify the copies are readable and the right size:

```sh
for p in boot init_boot vendor_boot dtbo vbmeta; do
    printf '%-12s backup=%s partition=%s\n' "$p" \
        "$(stat -c %s /external_sd/gts9-stock/$p.img)" \
        "$(blockdev --getsize64 /dev/block/by-name/$p)"
done
```

Record the sizes, the SHA-256 values and the Android build identifier in
`reference/stock/BOOT_CHAIN.md` (template in this repository). Copy the
`.img` files somewhere off the tablet as well: a backup that only exists on the
device being flashed is not a backup.

**Do not commit the stock images to git.** Only the sizes, hashes, build
identifier and acquisition date go into `reference/stock/BOOT_CHAIN.md`.

## 5. Step 3 — recovery plan (write it before you flash)

Keep this section open while flashing. If anything goes wrong, this is the way
back.

### 5.1 Restore the stock boot chain

From TWRP:

```sh
for p in boot init_boot vendor_boot dtbo; do
    dd if=/external_sd/gts9-stock/$p.img of=/dev/block/by-name/$p bs=4M
done

# verify what was written
sha256sum /dev/block/by-name/boot /dev/block/by-name/init_boot \
          /dev/block/by-name/vendor_boot /dev/block/by-name/dtbo
```

The hashes must match `/external_sd/gts9-stock/SHA256SUMS`.

### 5.2 vbmeta is handled separately — by default, not at all

Do not overwrite `vbmeta` as part of this test. If the device already boots
TWRP, its `vbmeta` already has verification disabled; replacing it can make
Android erase its data on the next boot, and it lives on a read-only LUN that
only the bootloader can write anyway. Restore it only if you deliberately
changed it:

```sh
dd if=/external_sd/gts9-stock/vbmeta.img of=/dev/block/by-name/vbmeta bs=4M
```

### 5.3 Never touch during bring-up

```text
recovery   abl        xbl        xbl_config   tz        hyp
modem      super      userdata   persist      efs       any PIT
```

No repartitioning. No `super`/`userdata` changes. No bootloader writes.

### 5.4 Worst case

If the tablet no longer reaches recovery: Download Mode + Odin with the
matching stock firmware (AP slot) restores the boot chain. Keep the exact
firmware build identifier recorded in `reference/stock/BOOT_CHAIN.md` for this
purpose.

## 6. Step 4 — build and validate the bundle (host side)

```bash
git -C <repo> rev-parse HEAD                  # record this
./scripts/check-build-deps.sh
./scripts/build-kernel.sh                     # Image.gz + DTB (+ modules)
./scripts/stage-android-tools.sh
./scripts/build-bringup-initramfs.sh          # real BusyBox initramfs
./scripts/build-boot-bundle.sh \
  --initramfs out/boot-bundle/initramfs-bringup.img \
  --cmdline boot/cmdline.example.txt \
  --bootconfig boot/bootconfig.example.txt
./scripts/validate-boot-bundle.sh
```

`validate-boot-bundle.sh` must end with `BOOT BUNDLE VALIDATION PASSED` and no
`FAIL` line. It checks, among other things, that the initramfs really contains
an executable `/init` and a BusyBox — a placeholder initramfs is a hard
failure. **Never flash a bundle that did not pass.**

Expected bundle (`out/boot-bundle/`):

| Image | Size | Contents |
|---|---:|---|
| `boot.img` | 100663296 | `Image.gz` with the board DTB appended, header v4 |
| `init_boot.img` | 8388608 | generic legacy-LZ4 BusyBox initramfs |
| `vendor_boot.img` | 100663296 | board DTB, cmdline, bootconfig, empty platform ramdisk |
| `dtbo.img` | 16777216 | deliberately non-table image (forces ABL's appended-DTB fallback) |
| `vbmeta.img` | 131072 | AVB flags 2 — **see 5.2, do not flash by default** |

## 7. Step 5 — flash (manual, one partition at a time)

Copy the bundle and `check-device-layout.sh` to `/external_sd/gts9/`. Then pick
one method.

### Option A — TWRP terminal (recommended, matches the backup route)

```sh
cd /external_sd/gts9

for p in boot init_boot vendor_boot dtbo; do
    dd if=$p.img of=/dev/block/by-name/$p bs=4M
done
```

Then read back and compare against the bundle's `SHA256SUMS`:

```sh
sha256sum /dev/block/by-name/boot /dev/block/by-name/init_boot \
          /dev/block/by-name/vendor_boot /dev/block/by-name/dtbo
```

Do **not** write `vbmeta.img` unless you have decided to (section 5.2).

### Option B — Odin from Download Mode

Pack the four images into a tar and select it in the `AP` slot:

```bash
tar -cf gts9-bootchain.tar boot.img init_boot.img vendor_boot.img dtbo.img
```

Leave `vbmeta` out. Odin needs the tablet in Download Mode; the TWRP route
above avoids that round trip.

### Option C — heimdall from a Linux host

Confirm the PIT names on this device before trusting them:

```bash
heimdall print-pit --no-reboot | less
```

Then flash by the names it prints (the usual SM8550 names are shown here):

```bash
heimdall flash --BOOT boot.img --INIT_BOOT init_boot.img \
               --VENDOR_BOOT vendor_boot.img --DTBO dtbo.img --no-reboot
```

## 8. Step 6 — run the test

1. From TWRP, reboot to **system** (cold boot from the user's point of view).
2. Watch the panel: a Samsung logo is expected; a black panel after it is not
   by itself a failure.
3. Give it 60–90 seconds. There is no display driver in this kernel, so the
   only interactive output is the serial console and the initramfs shell.
4. To read the persistent log, reboot to recovery (`Power` + `Volume Up`, or
   TWRP's reboot menu) and read it **immediately** — TWRP's own kernel log
   overwrites the 2 MiB ring within a couple of minutes:

```sh
cat /proc/last_kmsg | tail -200
```

   Run the capture tool on the host *before* the reboot so nothing is lost:

```bash
ADB=/mnt/d/android/platform-tools/adb.exe ./scripts/capture-last-kmsg.sh
```

   It waits for the tablet to reappear and pulls `/proc/last_kmsg` the moment it
   is readable, then prints the marker counts and a first verdict.

5. Because the panel driver is not part of this kernel and the UART is not
   broken out, `/proc/last_kmsg` is the primary evidence channel: the
   initramfs writes its milestone and every diagnostic line to `/dev/kmsg`, so
   they survive the warm reboot into the sec_log ring. See case A below.

## 9. Result classification

### Case A — initramfs shell reached

The log (or the console) shows:

```text
========================================
GTS9 MAINLINE INITRAMFS REACHED
========================================
```

The initramfs has no display and no network, and the SM-X710 UART is not
available without hardware access, so the practical way to detect this case is
the persistent console: `boot/bringup-init.sh` writes every line it prints to
`/dev/kmsg` as well, so after a boot attempt, warm-reboot into TWRP and look
for the milestone and the `gts9-init:` lines:

```sh
grep -c 'GTS9 MAINLINE INITRAMFS REACHED' /proc/last_kmsg
grep 'gts9-init:' /proc/last_kmsg | tail -40
```

Record `booted` and `initramfs reached`. Collect section 10's evidence and stop
there. This test is over.

### Case B — black panel, but `last_kmsg` contains `Linux version ...`

ABL entered Linux, so the boot image, DTB selection and AVB path are fine.
Continue from the **last line** of `last_kmsg` to locate the early-boot failure
(clocks, regulators, SMMU, UFS/SD, panic during driver probe). Attach the log.

### Case C — `last_kmsg` has only ABL output, no `Linux version`

The kernel never started. Investigate, in this order:

```text
boot.img format (header v4, gzip Image + appended DTB)
vendor_boot contents (DTB, cmdline, bootconfig)
DTB selection (qcom,board-id, qcom,msm-id, ABL labels in __symbols__)
dtbo handling
AVB state
```

Do **not** start by suspecting the root filesystem: there is none involved yet.

### Case D — `Linux version ...` present, no `GTS9 MAINLINE INITRAMFS REACHED`

The kernel booted but userspace did not start. The range is now:

```text
kernel late init, initramfs decompression, /init lookup, /init exec,
an early driver crash after console registration
```

Check that `last_kmsg` shows the initramfs being unpacked, and compare the
initramfs hash with the validated bundle.

### Case E — cannot reach recovery at all

Stop the bring-up immediately. Restore the stock boot chain (section 5.1) or
the stock firmware via Download Mode + Odin. Do not try another DTB, kernel or
partition change until the device is back to a known state.

## 10. Evidence to collect for every physical test

Record exactly:

```text
repository branch
repository commit
upstream kernel commit (scripts/fetch-mainline.sh prints it)
kernel.release

Image.gz SHA-256
sm8550-samsung-gts9wifi.dtb SHA-256
initramfs SHA-256
boot.img SHA-256
init_boot.img SHA-256
vendor_boot.img SHA-256
dtbo.img SHA-256
vbmeta.img SHA-256 (record even if not flashed)
```

And observe:

```text
which partitions were actually written
cold boot or warm reboot
Samsung logo seen?
Linux framebuffer seen?
automatic reboot?
TWRP still reachable?
/proc/last_kmsg
/sys/fs/pstore/*
```

If the shell was reached, also save:

```sh
uname -a
cat /proc/cmdline
dmesg
cat /proc/iomem
cat /proc/partitions
cat /sys/firmware/devicetree/base/model
```

Keep `gts9-layout.txt` and the stock `SHA256SUMS` with this record.

## 11. The persistent console: what is verified and what is not

`CONFIG_SAMSUNG_GTS9WIFI_SEC_LOG=y` (driver
`kernel/drivers/samsung-gts9wifi-sec-log.c`) writes the kernel console into
Samsung's `sec_log_buf` ring at `0x880200000`, size `0x200000`, so a failed
boot can be read back through TWRP's `/proc/last_kmsg`.

Evidence status:

- the reserved-memory node and its address/size come from the owner's X710
  stock evidence (`reference/stock/MANIFEST.md`);
- the LOGM header layout (`boot_count`, `magic`, `index`, `previous_index`,
  byte ring) is **adapted from the physically validated SM-X910 port** — no
  X710 stock kernel source was available to re-derive it. It is a bring-up
  adaptation from a sibling device, **not** an X710-verified implementation;
- `index` and `previous_index` are both updated on every write, so a manual key
  reboot from a panic still leaves the mainline stream readable.

What to check on the device, and what each result means:

| Observation | Meaning |
|---|---|
| `last_kmsg` shows `Linux version ...` | the ring, the magic and the write path work |
| `last_kmsg` shows the `gts9-init:` lines | userspace ran; the console mapping is correct |
| `last_kmsg` is empty or has no `Linux version` | either the kernel never reached the driver, or the LOGM layout/magic is wrong for the X710 |
| `boot_count` in the ring increases across two boots | the header is being reused, not re-initialised each boot |

If the layout proves wrong, the driver must be corrected against X710 stock
evidence before it is trusted — do not "fix" it by guessing.

## 12. Deliberately out of scope for this test

Do not add or debug any of the following until the chain in section 1 works:
panel driver, touchscreen, S Pen, GPU userspace/Turnip, ath11k firmware,
Wi-Fi, Bluetooth, ADSP, audio, charging, DisplayPort, cameras, sensors,
fingerprint, any full distribution root filesystem.

The one exception is a subsystem that can be shown to block
`ABL -> Linux -> /init` directly; document that evidence first.
