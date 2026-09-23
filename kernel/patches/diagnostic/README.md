# Diagnostic-only kernel patches

These patches are retained for targeted experiments and are not applied by
`scripts/prepare-kernel.sh`. The default patch queue is `kernel/patches/*.patch`;
subdirectories are intentionally ignored except for the explicit
`GTS9_POWEROFF_TRACE=1` opt-in documented below.

## `0008-i2c-qcom-geni-log-bus-lines-on-error.patch` — DIAGNOSTIC ONLY

This temporarily raised Qualcomm GENI I2C NACK/timeout logs and printed FIFO,
IRQ, and `SE_GENI_IOS` state. It helped distinguish a real address NACK from a
bus whose lines were not idle during Pogo bring-up. The default Pogo path no
longer depends on those measurements, and changing log levels in the shared
GENI controller adds noise for every device on the system.

For a one-off measurement, first prepare a disposable kernel worktree, then
apply this patch manually and rebuild:

```sh
scripts/prepare-kernel.sh <worktree>
git -C <worktree> apply <repo>/kernel/patches/diagnostic/0008-i2c-qcom-geni-log-bus-lines-on-error.patch
```

Running `prepare-kernel.sh` again restores the pinned source and reapplies only
the default queue.

## `0020-gts9-poweroff-path-trace.patch` — DIAGNOSTIC ONLY

This patch adds command-line-gated markers around Linux poweroff stages and
the registered sys-off callbacks. With `gts9_poweroff_trace=1`, it identifies
the callback symbol and priority, and prints immediately before PSCI
`SYSTEM_OFF`; if firmware returns, it prints the returned value. The PSCI
marker is flushed before the call, adding up to one second to this diagnostic
poweroff attempt. It does not change the default kernel or the poweroff
handler. The early-boot flag is default-off.

Prepare and build it in a disposable worktree and output directory:

```sh
GTS9_POWEROFF_TRACE=1 \
KERNEL_WORKTREE="$PWD/.work/build/linux-src-poweroff-trace" \
KERNEL_BUILD_DIR="$PWD/.work/build/linux-out-poweroff-trace" \
KERNEL_OUT_DIR="$PWD/out/kernel-poweroff-trace" \
scripts/build-kernel.sh
```

Package with `boot/cmdline.poweroff-trace.example.txt`. It enables the initramfs
report trace, kernel poweroff trace, and framebuffer console while keeping
`ttyMSM0` last as `/dev/console`. Re-running `prepare-kernel.sh` with the
default environment resets the diagnostic changes and restores the ordinary
patch queue.

## `0010-pinctrl-report-pogo-pin-state-at-probe.patch` — DIAGNOSTIC ONLY

This sampled TLMM registers for GPIO10, 12, 13, 62, 72, 75, and 106 at probe,
then logged another sample every 30 seconds forever. It helped inspect pin
ownership while bringing up the board, but the Pogo driver does not consume
these samples: the patch only reads and logs MMIO state. Its periodic worker
also changes generic Qualcomm pinctrl code for every board using that driver,
so it is excluded from the default build.

For a one-off measurement, apply the patch manually to a disposable prepared
kernel worktree and rebuild:

```sh
scripts/prepare-kernel.sh <worktree>
git -C <worktree> apply <repo>/kernel/patches/diagnostic/0010-pinctrl-report-pogo-pin-state-at-probe.patch
```

Running `prepare-kernel.sh` again restores the pinned source and reapplies only
the default queue.
