# Test 178 — minimal initramfs to Debian on real hardware

**Status:** Phase A (Type-C) PASS. Phase B (battery-only) PASS, including a
final repeat with the panel-enabled image set. Debian-side panel recovery and
ttyGS0 root autologin verified. One intermittent DPU hang
found and documented. The Pogo keyboard recovery service was added, tested and
then reverted at the owner's request (the keyboard works; the earlier failure
was physical contact).

Source commits: `4a80b47` (start) through `75121b5`.
Physical runs: 2026-09-23 17:04Z - 18:44Z, device SM-X710 / gts9wifi, serial
R52X10045LT, Type-C attached to the host, microSD = Debian root.

## What was flashed

| Partition | Before | After | Written |
|---|---|---|---|
| `init_boot` (sda22) | `4515b081…` (test 177 candidate) | `9985eeef89844a6018d4664fdf4d52f89d3d7ab7d7dcef7c53d08dba08ce5834` | yes, read back verified |
| `vendor_boot` (sda24) | `740bbd63…` | `1abb4c68b8103020d7935f5057225abe1e6b6b2222f58a6e93e254eb851af27c` | yes, read back verified |
| `boot` (sda21) | `822ca9dcf404de83e79f085a5509ec761bf0234359a5fae166c5d1c849e1df86` | unchanged | no |
| `dtbo` (sda30) | `c17418be…` | unchanged | no |
| `vbmeta` (sde15) | `9844859b…` | unchanged | no |

Intermediate `init_boot` writes during the session (`c22078ad…`, `0da9ebc5…`)
were superseded by `9985eeef…`. `vendor_boot` also went through
`0738bd1f…` (panic=10 cmdline) before `1abb4c68…` (adds
`msm.separate_gpu_kms=1` and `fbcon=` at the front).

Backups on the host staging directory
`/home/ms/Samsung/gts9-flash-tests/test-178-20260923T165658Z/`:
`init_boot-before.img`, `vendor_boot-before.img`,
`vendor_boot-before-panel-fix.img`,
`gts9-debian-config-before.tar.gz` (sha256 `f6198099…`), plus the pulled
boot records. Restore with
`adb shell dd if=<backup> of=/dev/block/by-name/<partition>` from TWRP.

Debian overlay tarball deployed: `de703b89adf92232cc82cd56397e80e13189af43a55401207388df8f37d04bef`
(units, helpers, autologin drop-in, firmware at `usr/lib/firmware/`). Kernel
release `7.2.0-rc3-gts9wifi-dirty` (device kernel unchanged).

## Results

### Phase A — Type-C attached (PASS, `typec-a-result.txt`, `typec-a-console.log`)

```text
uid=0(root)                                  ttyGS0 autologin, no login/password
Linux gts9 7.2.0-rc3-gts9wifi-dirty aarch64  device kernel 822ca9dc boot
/ = /dev/mmcblk1p1 ext4                      Debian root on TF
systemctl --failed: 0 loaded units           no failed units
gts9-usb-acm.service: active, status=0       "bound to a600000.usb"
serial-getty@ttyGS0.service: active          autologin.conf drop-in applied
stage=switch-root-synced                     initramfs handoff complete
debian_stage=multi-user                      Debian chain complete
```

### Phase B — battery-only (PASS, `typec-b-result.txt`, `battery-b-console.log`)

Same flashed images, Type-C unplugged for the boot, long Power press, ~2-3 min
wait, Type-C reattached only to reach the console.

```text
boot_id=a6d6f60c-ff77-4ae4-aa39-5bfc70c3df7d      (distinct from Phase A)
stage_history=…,init-found,switch-root,switch-root-synced
debian_boot_id_match=yes
debian_root_source=/dev/mmcblk1p1  debian_root_fstype=ext4
debian_stage=multi-user
debian_stage_history=systemd-entered,local-fs,basic,usb-acm-ready,
                     panel-unavailable,tty1-getty-active,multi-user
debian_failure=none
```

Type-C/VBUS is not a rootfs handoff dependency. `panel-unavailable` in this
run is the pre-`msm.separate_gpu_kms` cmdline (see below), not a boot failure.

### Panel recovery on hardware (PASS, `panel-fix-result.txt`)

With `msm.separate_gpu_kms=1` at the front of the minimal cmdline:

```text
[0.74 s] ana38407 panel id: 00 00 00            cold-boot zero ID
[0.78 s] panel id 00 00 00, expected 80 00 04   driver warning
[4.63 s] ana38407 panel id: 80 00 04            after gts9-panel-recover
gts9-panel-recover: cycle 1 recovered panel ID 80 00 04
debian_stage_history=…,usb-acm-ready,panel-recovered,tty1-getty-active,multi-user
fb0 fbcon | backlight ae94000.dsi.0 | fb0/blank = 0
```

Before the fix the same image reported `failed to attach to DSI host`
(-EINVAL), no fb0, and `panel-unavailable`.

## Incidents found and fixed in this test

1. **All black, console-less boots (runs 1-4) were a broken Debian usr-merge.**
   The overlay tarball carried `lib/firmware/...`; TWRP's busybox `tar`
   replaced the `/lib -> usr/lib` symlink with a real directory, leaving
   `/sbin/init -> /lib/systemd/systemd` and `/lib/ld-linux-aarch64.so.1`
   dangling. `execve("/sbin/init")` failed, `switch_root` died, PID 1 exited
   and the kernel panicked: with `panic=0` an unrecoverable hang (runs 1-3),
   with `panic=10` a reboot loop (run 4). Fixed in `1cd2c8d` (installer writes
   `usr/lib/...` and refuses a non-usr-merged rootfs); the card was repaired
   offline with `debugfs` and verified from TWRP.
2. **Dark panel in the minimal profile**: the cmdline never carried
   `msm.separate_gpu_kms=1`, which test 035 had already proven necessary for
   the DSI host to accept the panel. Fixed in `affeec9`.
3. **Intermittent freeze (one boot)**: `enc35 frame done timeout` ->
   `vblank wait timed out on crtc 0` in `drm_fb_helper_damage_work` ->
   `workqueue lockup` -> RCU stalls on CPUs 4/5. Screen kept the last image
   with a blinking cursor, keyboard echoed, no getty ever ran, USB console
   silent. Kernel display bug; documented with evidence in
   `docs/MINIMAL_ROOTFS_BOOT.md`, with `gts9_panel_recover=0` as the stable
   escape hatch (`da2f7ec`, `75121b5`). No hardware watchdog exists
   (`nowatchdog`, hard watchdog disabled) so nothing recovers a stall
   automatically.
4. **Serial console silent when Type-C is attached after boot** (Phase B):
   the gadget enumerates but nothing reads the port until the next reboot.
   Observed twice; journal of the affected boot was not captured. Working
   channel: attach Type-C before boot, or reboot to TWRP via the BCB script
   and read the card offline.
5. **Pogo keyboard**: the driver's 0.63 s probe reads the connect line as 0
   before the STM32 answers; a later rearm/hot-reconnect brings it up (input
   device with `sysrq kbd leds event2`). A Debian recovery service was written
   and tested (`15a7c44`, `810f476`) and then **reverted** (`3c7df99`,
   `3afcde7`) at the owner's request: the keyboard works, the failure was
   physical contact.

## Evidence files

`adb-devices-preflash.txt`, `device-identity.txt`, `twrp-layout-audit.txt`,
`current-partition-hashes.txt`, `postwrite-partition-hashes.txt`,
`flash-write-readback.txt`, `backup-hashes.txt`, `twrp-bcb-audit.txt`,
`debian-config-backup-sha256.txt`, `debian-rootfs-state-before.txt`,
`debian-overlay-info.txt`, `debian-overlay-deploy.txt`,
`overlay-deploy-corrected.txt`, `lib-repair-verify.txt`,
`typec-a-console.log`, `typec-a-result.txt`, `battery-b-console.log`,
`typec-b-result.txt`, `panel-fix-check.log`, `panel-fix-result.txt`,
`keyboard-and-udc-check.log`, `pogo-rebind-check.log`,
`keyboard-rollback.txt`, `post-rollback-verify.log`, `journal-prev-boot.log`,
`workqueue-lockup-backtrace.log`, `rcu-stall-backtrace.log`,
`watchdog-check.log`, `final-device-state.log`, `host-actions.txt`,
plus the failed-boot records `record-boot2.bin` / `record-boot3.bin` on the
host staging directory (raw `.bin` are not committed).

## Verified / observed / inferred / not yet tested

- **Verified on hardware**: Phase A and Phase B chains; ttyGS0 root autologin;
  `gts9-usb-acm.service` binding `a600000.usb`; Debian-side panel cold-boot
  recovery; the usr-merge repair; ADB-free recovery entry through the BCB
  script; the correct operation of `scripts/twrp-mount-debian.sh` on TWRP's
  mksh (after `72ebf8d`).
- **Observed**: the DPU hang once; the silent serial after a late cable
  attach twice; the keyboard's early probe giving up.
- **Inferred**: the usr-merge damage was caused by the earlier overlay
  extraction (the log line `... not under '/mnt/debian'` is in
  `debian-overlay-deploy.txt`); the DPU hang is triggered by the panel
  modeset, because no fb0 (i.e. no fbcon damage work) never hung.
- **Not yet tested**: modules installed into Debian (`usr/lib/modules`);
  Wi-Fi, Bluetooth, GPU, audio, camera, sensors; the DPU hang fix itself.

## Final battery-only confirmation (panel-enabled images)

Same `init_boot`/`vendor_boot` as the panel run above, Type-C unplugged for the
boot (see `final-battery-b-result.txt`, `final-battery-b-console.log`):

```text
boot_id=0bf46cc6-031e-4a7d-95ff-81d6c066bd20   (distinct again)
stage=switch-root-synced   failure=none   debian_boot_id_match=yes
debian_root_source=/dev/mmcblk1p1   debian_root_fstype=ext4
debian_stage=multi-user
debian_stage_history=systemd-entered,local-fs,basic,usb-acm-ready,
                     panel-recovered,tty1-getty-active,multi-user
debian_failure=none
systemctl is-system-running: running       systemctl --failed: 0 units
```

`systemctl poweroff` on this tablet does not cut power (the known, separate
poweroff issue: systemd finishes, PSCI SYSTEM_OFF does not power the device
down, the last framebuffer stays with a blinking cursor). The battery-only run
was therefore started with a long Power press after a forced power-off, as
described in the earlier Phase B run.
