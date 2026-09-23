# Minimal Debian rootfs boot profile

`gts9_minimal_rootfs=1` selects an isolated path for measuring whether the
microSD root filesystem can boot without the initramfs bring-up work. The
default `boot/cmdline.example.txt` does not enable it. Use
`boot/cmdline.minimal-rootfs.example.txt` for both sides of the Type-C versus
battery-only comparison.

## Execution path

`bringup-init.sh` mounts procfs so it can read `/proc/cmdline`. When the
minimal flag is set, it immediately execs `minimal-rootfs-init`; it does not
mount debugfs or run the normal bring-up path. The minimal script then:

1. Mounts sysfs, devtmpfs and tmpfs on `/run` if they are not already mounted.
2. Prints `GTS9_MINIMAL_STAGE=kernel-userspace` and
   `GTS9_MINIMAL_STAGE=waiting-root` to stdout, `/dev/kmsg`, `/dev/console`,
   and `/dev/tty1` when that device already exists.
3. Waits at most 30 seconds for `gts9_rootfs=` (default
   `/dev/mmcblk1p1`), then prints `root-found` and mounts ext4 read/write.
4. Checks that `/newroot/sbin/init` is executable, stages a static PID 1
   trampoline and BusyBox in the initramfs `/run`, then moves `/dev`, `/proc`,
   `/sys` and `/run` and execs BusyBox `switch_root`. The trampoline execs
   `/sbin/init` after the root switch; if that exec fails, it logs
   `switch-root-returned` and keeps PID 1 alive with a BusyBox rescue shell.
5. On a missing device, mount failure, missing init or failed preparation,
   prints the failure and last stage, shows `/proc/partitions`,
   `/sys/class/block` and `/dev/mmcblk*`, and stays in a BusyBox rescue shell.

The diagnostic markers are `kernel-userspace`, `waiting-root`, `root-found`,
`mounting-root`, `root-mounted`, `init-found` and `switch-root`. Failure codes
include `root-timeout`, `root-mount`, `missing-init` and
`switch-root-returned`. The rescue shell uses `/dev/console`; neither tty1,
DRM nor USB ACM is required.

## Persistent boot-stage record

A black panel and an absent USB console say nothing about how far the boot got,
and Samsung's bootloader overwrites `sec_log`, so the minimal profile records
its stages on the Debian root filesystem itself:

```text
/var/log/gts9-minimal-last-boot          # on the Debian root, /dev/mmcblk1p1
```

The record is written by `boot/minimal-rootfs-state.sh`, which
`boot/minimal-rootfs-init.sh` sources from `/minimal-rootfs-state.sh` in the
initramfs. Nothing can be persisted before the root filesystem is mounted, so
`waiting-root`, `root-found` and `mounting-root` stay in RAM and go to
`/dev/kmsg` and `/dev/console`; immediately after `root-mounted`, the whole
history is written to Debian at once and every later stage updates the same
file. The file is replaced atomically - write `<record>.tmp`, `chmod 0644`,
`sync`, rename - so a reader never sees a half-written record. The
`switch-root` stage is written and synced before `exec switch_root`, which is
what lets TWRP prove that the card mounted, `/sbin/init` was found and the
handoff was about to run even when Debian itself never reports anything.

Format (one `key=value` per line, stable key set of version 1):

```text
format_version=1
origin=initramfs
boot_id=<kernel boot id of the initramfs boot>
kernel_release=<uname -r>
cmdline=<full /proc/cmdline>
timestamp=<UTC time of the first record write>
uptime_seconds=<uptime at the first record write>
root_device=<configured gts9_rootfs device>
stage=<last initramfs stage>
stage_history=<comma-separated stages, in order>
failure=<none or the failure code>
mmc_devices=<every /dev/mmcblk* node seen, or none(found:hosts=...)>
```

Debian appends its own `debian_*` keys to the same file (see
`docs/TWRP_DEBIAN_RECOVERY.md` and the `gts9-debian-*` units in
`rootfs-overlay/`), so one file answers "how far did the last boot get" for the
whole chain. The initramfs block is never rewritten by Debian.

## Debian stage chain

`rootfs-overlay/usr/libexec/gts9-record-debian-stage` continues the record from
inside Debian. It replaces only the `debian_*` keys, keeps the initramfs block
byte for byte, and is a successful no-op when the record is absent, so a
regular bring-up boot (which writes `/var/log/gts9-last-boot-stage`) is
unaffected. Four oneshot units feed it, each of them individually disableable
from TWRP:

| Unit | Stage recorded | Ordering |
|---|---|---|
| `gts9-debian-entered.service` | `systemd-entered`, `local-fs` | `DefaultDependencies=no`, `After=local-fs.target`, `Before=basic.target` |
| `gts9-debian-basic-stage.service` | `basic` | `After=basic.target`, `Before=multi-user.target` |
| `gts9-debian-getty-stage.service` | `tty1-getty-active` or `tty1-getty-inactive` | `After=getty.target`, `Before=multi-user.target` |
| `gts9-debian-multi-user-stage.service` | `multi-user` | `After=multi-user.target` |

Every unit carries `ConditionPathExists=/var/log/gts9-minimal-last-boot`, so
they activate only for this profile. Each stage is also printed as
`GTS9_DEBIAN_STAGE=<stage>` on the journal and on `/dev/kmsg`. The helper
additionally records `debian_boot_id` and `debian_boot_id_match` (does the
record belong to the boot Debian is running in?), `debian_kernel_release`,
`debian_root_source` and `debian_root_fstype`, which is how `/ = Debian TF`
is confirmed from the file alone.

A failure recorded by one service is not erased by a later service that
succeeds: `debian_failure=` keeps the most recent reason and
`debian_failure_history=` lists every distinct reason seen in that boot, so a
getty or panel failure stays visible in the final record.

The USB ACM service adds `usb-acm-ready` (or `usb-acm-failed`) and the panel
recovery service adds `panel-recovered`, `panel-ok`, `panel-recovery-failed`
or `panel-unavailable`.

## Deploying the Debian userspace

`scripts/install-debian-rootfs.sh` installs everything named above from
`rootfs-overlay/` in one reproducible step. Both modes build the identical
tree from the identical sources:

```bash
# With the card mounted on the host:
sudo ./scripts/install-debian-rootfs.sh /mnt/debian

# For TWRP (recommended; the tablet has no repository):
./scripts/install-debian-rootfs.sh --tar out/gts9-debian-overlay.tar
adb push out/gts9-debian-overlay.tar /tmp/
# in TWRP:
cd /mnt/debian && tar -xpf /tmp/gts9-debian-overlay.tar
sync
```

Both the archive entries and every enablement symlink it carries are relative.
TWRP's busybox `tar` refuses absolute symlink targets that lie outside the
extraction root (`... not under '/mnt/debian'`, non-zero exit), so absolute
`systemctl enable`-style links would make a re-deployment fail to sync. The
installer therefore writes relative links, which systemd accepts.

The installer copies the overlay (units, helpers, logind and getty
configuration), creates each unit's enablement symlink from its own
`WantedBy=` so no `systemctl` is needed, replaces `lib/modules/<release>`
with the modules built for this kernel, copies firmware to `lib/firmware/`,
and runs `depmod -b <target> <release>`. The module release is taken from the
module tree and must match `kernel.release` written next to `modules-root`;
a mismatch aborts the install instead of deploying modules for a different
kernel. `--skip-modules`, `--skip-firmware`, `--modules DIR` and
`--firmware DIR` override the defaults.

The installer never formats, never runs `fsck`, writes nothing outside the
given target and refuses `/`. It is idempotent: running it twice produces the
same tree, and the tarball carries relative paths only, so TWRP can extract it
with `tar -xpf` into the mounted root.

Kernel modules and firmware live in Debian, not in the minimal initramfs. The
initramfs keeps the built-in providers the root handoff needs (MMC/SDHCI,
ext4, RPMh, PMIC, PDC, clock, pinctrl) and only receives modules when the
builder is called with `--modules` for a dedicated bring-up test.

Reading it from TWRP, after booting recovery with the card still inserted:

```sh
adb shell
# Identify the Debian ext4 partition first; recovery block numbering may differ.
blkid
mkdir -p /mnt/debian
mount -t ext4 -o ro /dev/block/mmcblk1p1 /mnt/debian     # only after blkid confirms it
cat /mnt/debian/var/log/gts9-minimal-last-boot
umount /mnt/debian
```

`scripts/twrp-mount-debian.sh` performs that detection safely (it refuses
non-MMC devices, never formats and never runs a repairing `fsck`); see
`docs/TWRP_DEBIAN_RECOVERY.md`.

## Work skipped before `boot_rootfs()`

In the regular profile, `boot_rootfs()` is reached only after initial debugfs
mounting, panel recovery and its framebuffer/panel-ID polling, the general
boot report, USB configfs gadget setup, UFS GPT lookup for `misc`, stale BCB
inspection/clear, and the optional RTC write. It then attempts the configured
USB host wait and gathers USB/UDC, deferred-probe, SDHC/UFS, regulator, clock,
RTC, interrupt, DWC3, DRM/framebuffer/backlight, Pogo and input reports. It
also scans GPT entries and may mount removable storage or the internal cache
to persist reports before it calls `boot_rootfs()`. `gts9_rootfs=` disables
the proof/recovery timers, but does not skip these other operations.

Some operations have explicit timeouts, including GPT reads and report
mount/copy steps. Other paths still contain unbounded kernel-facing reads or
writes (`dmesg`, debugfs/sysfs diagnostics, configfs gadget operations and
`sync`); a userspace timeout cannot repair a kernel operation stuck in an
uninterruptible state. None of that work belongs on the microSD root handoff
path.

## Boot-critical kernel support

The root filesystem is on the TF card, so the early path depends on CPU,
memory, GIC and timer support; the SM8550 RPMh/PMIC, clock, pinctrl and GPIO
providers; SDHC2 and its MMC/SDHCI drivers; the card-detect GPIO; the L9B/L8B
card supplies; MMC block support; and ext4. These providers must be built in
or available in the initramfs. The current kernel fragment and resolved build
config set `CONFIG_MMC`, `CONFIG_MMC_BLOCK`, `CONFIG_MMC_SDHCI`,
`CONFIG_MMC_SDHCI_MSM`, `CONFIG_EXT4_FS`, `CONFIG_SPMI_MSM_PMIC_ARB`,
`CONFIG_QCOM_PDC`, `CONFIG_QCOM_RPMH`, `CONFIG_REGULATOR_QCOM_RPMH`,
`CONFIG_COMMON_CLK_QCOM` and `CONFIG_PINCTRL_QCOM_SPMI_PMIC` to `y`.

The X710 DTS describes PM8550 GPIO12 as active-low card detect, L9B 2.9 V as
`vmmc`, and L8B 1.8 V as `vqmmc`. This profile changes no DTS or regulator
setting. It does not load modules from the card before mounting that same card.

Display recovery, DRM/backlight reports, tty1 setup, USB gadget and ACM,
SM5714 policy, UFS GPT/misc BCB work, Pogo, Wi-Fi, Bluetooth, GPU, audio,
camera, sensors, full regulator/clock/interrupt dumps, report persistence and
recovery helpers are outside the minimal path. They can run after Debian
starts or in a separately selected diagnostic profile.

## Type-C / battery-only A/B test

Build one candidate bundle, record the git commit and SHA-256 hashes, and use
the same kernel, DTB, initramfs and minimal cmdline for both tests. The only
intended variable is whether Type-C/VBUS is connected. Each run gets its own
`reference/boot-tests/test-NNN-*/` directory; use
`reference/boot-tests/MINIMAL_ROOTFS_TEST_TEMPLATE.md` and do not overwrite
previous evidence.

For each run, record the visible marker sequence from UART or retained kernel
log, whether `/dev/mmcblk1p1` appeared, whether ext4 mounted, whether
`switch-root` ran, and whether Debian/systemd and a login were confirmed over
serial. Record the panel separately: a frozen early-console image is not proof
of a frozen system.

The existing full bring-up baseline is not a result for this profile: test 173
records a Type-C-attached Debian boot. Test 175 records a battery-only attempt
that reached `root-mounted` and `init-found`; no switch-root or systemd state
was captured, and the screen alone cannot settle it. The minimal-profile A/B
result is still pending a physical tablet run.
