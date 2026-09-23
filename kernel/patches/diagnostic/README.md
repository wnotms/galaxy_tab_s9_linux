# Diagnostic-only kernel patches

These patches are retained for targeted experiments and are not applied by
`scripts/prepare-kernel.sh`. The default patch queue is `kernel/patches/*.patch`;
subdirectories are intentionally ignored.

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
