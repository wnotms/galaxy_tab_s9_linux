# Debian boot and power-off diagnostics

## What current evidence says

The device can boot the current mainline kernel into Debian when Type-C is
connected. In that boot, the Qualcomm SD host appeared at about 0.47 seconds,
the microSD card at about 0.67 seconds, and `/dev/mmcblk1p1` was mounted as the
root filesystem at about 2.13 seconds. The regulator summary showed the SD
controller's 1.8 V `vqmmc` and 3.0 V `vmmc` consumers enabled. This only
describes that successful boot; it does not establish what happens on a
battery-only cold boot.

The reported flashing cursor does not identify a boot stage. The existing
initramfs waits up to 15 seconds for `/dev/mmcblk1p1`, then keeps PID 1 in a
rescue shell if the card, ext4 mount, init binary, or `switch_root` check fails.
The display also has a known cold-boot recovery path. A cursor alone therefore
cannot distinguish an initramfs handoff failure from a display that did not
finish coming up.

The current kernel reports PSCI 1.1 from firmware and has
`CONFIG_ARM_PSCI_FW=y`. Its `psci_sys_poweroff()` invokes PSCI
`SYSTEM_OFF`; arm64 reaches that callback from `machine_power_off()`. The
runtime has no `/sys/firmware/efi`, and the kernel says UEFI services are
unavailable, so EFI runtime power-off and EFI pstore are not active paths.
`CONFIG_POWER_RESET_QCOM_PON=y` populates PMIC power-key children but is not a
system power-off callback. No `qcom,pshold` node or `POWER_RESET_MSM` handler is
present in this build.

The previous boot's persistent journal ends with `systemd-shutdown` syncing
filesystems and sending SIGTERM. That journal boundary does not prove whether
the final shutdown program reached the kernel. The current `/sys/fs/pstore`
is empty and the live device tree has no ramoops node, so there is no confirmed
kernel-persistent trace for the failing attempt. Earlier test 010 recorded an
owner-observed physical power-off from a BusyBox initramfs. That establishes
that an earlier image on this device could power off, but it does not test the
current Debian shutdown path or identify the present cursor state.

The owner also reported that a short power-key press turned the screen off and
a second short press restored the screen and keyboard. The journal for that
boot confirms `PM: suspend entry (deep)` and `PM: suspend exit`, so the
power-key suspend/resume path completed. This does not establish that
`systemctl poweroff` removes PMIC power. See test 166.

## Diagnostic changes

The initramfs now writes `GTS9_BOOT_STAGE=...` and `GTS9_BOOT_FAIL=...` to
`/dev/kmsg` at the userspace, framebuffer-control, microSD, mount, and rootfs
handoff boundaries. If handoff fails and tty1 is available, the rescue screen
shows the failure reason and last completed stage. The framebuffer stage means
the blank-control interface exists; it does not claim the panel is physically
lit.

After the root filesystem mounts, each stage atomically updates
`/var/log/gts9-last-boot-stage` with the boot ID, command line, rootfs state,
MMC devices, SD regulator consumers, and recent MMC log messages. Debian
systemd units then append `systemd-basic` and the tty1 getty result. If a boot
fails before the card can be mounted, that file cannot be updated; compare its
boot ID with the current boot before treating it as evidence for that attempt.

The optional Debian power-off marker is
`/var/log/gts9-last-poweroff-stage`. Its unit runs immediately before
`systemd-poweroff.service`, after `umount.target`, and atomically replaces the
marker file. A matching boot ID proves only that systemd reached that final
service. The subsequent standard systemd shutdown path performs its own
filesystem sync; the marker service adds no extra sync. The record does not
prove that the kernel called PSCI `SYSTEM_OFF` or that PMIC power was removed.

Install the Debian-side units and the existing short-power-key suspend policy
on a mounted Debian root filesystem with:

```sh
sudo scripts/install-rootfs-diagnostics.sh /path/to/debian-rootfs
```

The rootfs copy is separate from the initramfs build. Nothing in this change
alters regulator voltages, charger settings, SM5714/PTN3222 state, the SD
power sequence, display timing, or the kernel power-off handler.

## Next hardware observations

Use a manually flashed diagnostic candidate; this repository change does not
flash the tablet. For the power-off test, record whether the final marker is
written, whether the kernel emits `Power down` on the live serial connection,
and whether the device actually loses power. If power-off completes, test a
cold start with Type-C disconnected and note the visible rescue reason or the
last matching boot ID. Keep the known-good image available for recovery.

Do not change the SD rails, PMIC/charger configuration, USB PHY, or display
sequence based only on the cursor. The next change should follow a stage or
kernel trace that localizes the failing transition.
