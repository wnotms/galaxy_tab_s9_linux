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
