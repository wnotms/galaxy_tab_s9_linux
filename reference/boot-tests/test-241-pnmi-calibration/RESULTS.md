# Test 241 — pseudo-NMI calibration passed; CPU repair remains open

The higher-priority backtrace interrupted CPU0 while ordinary IRQs were
PMR-masked and captured the actual interrupted registers/stack. This is a
healthy synthetic calibration, not a reproduced natural failure or CPU fix.

## Candidate and checks

Source commit before flash: `211d9b6` on `test`; upstream pin unchanged.
Patches 0022 (lastactivity), 0024 (ECC64), 0027 (bounded calibration), and the
opt-in PSEUDO_NMI config. BBM patch 0026 and RCU injection 0025 were absent.
Only boot/vendor_boot were written, with full readbacks; defaults/rootfs and
USB coexistence were unchanged. Generated vbmeta was never installed.

The complete kernel build passed. A missing prototype warning was fixed and
only the changed object plus dependent link stages were rebuilt; the final
build had no compiler warnings. Six actual-helper host scenarios and retention
parser checks passed. Config added PSEUDO_NMI and dependent capability symbols;
DTB/release matched the ECC64 baseline. Bundle validation passed. See
validation/ for build logs, config diff, exact artifacts/notes hashes and tests.
The full unrelated host suite was not repeated for this isolated diagnostic.

## Actual masked-IRQ capture

- Source boot: `3bfa876b-be6e-49d3-8029-79e65d0f7ba6`.
- Lastactivity ID: `88779911-973b-4fde-9470-2ba7c753feab`.
- Calibration ID: `1f1240e7-165f-4f07-8e77-1bb5ac2f566a`.
- GIC runtime pseudo-NMI enable, priority masking, ECC64, watchdog 1/1/1/10,
  console threshold 5, exact kernel notes and six relocation anchors passed.
  This target's runtime offset is `+0x20000`; it is not a universal offset.
- Pre-trigger observation reached 158.07 seconds without detected CPU failure.
  Existing display-clock probe warning also appears in test240.
- CPU0 masked interval: **200,000,157 ns**. Callback observed **61,407 ns** after
  start, before restoration; `observed=nmi=saved_irq_disabled=1`, PMR `0xc0`,
  PSTATE `0x83400005` (I bit clear), error=0, both workers done, holding=0.
- Runtime PC `ffffffc081466ed8` resolves against this exact vmlinux to
  `arch_counter_get_cntvct+0x14/0x30` (inlined counter read at arch_timer.h:200).
  Stack includes `arch_counter_read`, `ktime_get_mono_fast_ns`, and
  `gts9_pnmi_masked_region`. The counter read is expected in the calibration
  loop; it is not evidence of a clocksource fault.
- A second trigger was refused. Another **73.01 seconds** passed without a
  detected CPU/RCU/workqueue failure. No forced panic or CPU hotplug was used.

See calibration/verdict.json, raw journal/status and post-calibration/.

## Exact normal-reboot retention

Immediate retained observer: `e72b6d0c-fbf6-4348-bccb-93db1c14e98b`; the
observer's trigger remained unused. Two raw console pulls match each other
and the device-side hash. After stripping only printk timestamp/caller
prefixes, the unique BEGIN-to-END region is identical to the source priority
0..4 journal: **28 lines / 1,583 bytes**, SHA-256
`ebb7223fa2e4822bacef22f6b40ba612d4cceff10b3de6ebe0c9864f4f4f8451`.
Payload indentation and all register/stack bytes were retained. ECC reports
**61 corrected bytes, zero unrecoverable blocks**. Both immutable boot IDs are
adjacent in retained journal history. Source/observer raw files and the verdict
are in retention-source/ and retention-observer/.

This proves this region's warm-reboot retention at console threshold 5. It
is not a whole-log integrity claim, a natural-fault capture, or proof that a
pseudo-NMI can interrupt firmware, raw DAIF masking or true CPU non-progress.
Only CPU0 was calibrated; do not infer measured delivery on every CPU. An
unreferenced future failure log still needs explicit integrity limitations.

## Recovery and next step

BCB helper plus plain reboot reached TWRP. Original boot/vendor_boot were
restored and all five partition hashes matched production. Final production
boot `6a9e0303-fc8c-4c7f-a18a-0a26727a49cd` passed 215.02 seconds
without a detected CPU failure. Original watchdog/soft-watchdog/panic/ECC
settings were independently confirmed zero; the calibration helper is absent.
USB ADB commands and all four SSH/gadget services respond. Windows NCM received
the SSH protocol banner; an authenticated SSH session was not tested. This is
a bounded observation, not a long-term stability or armed-production claim.

Next pre-register one bounded natural-capture attempt using the validated
pseudo-NMI path, with the synthetic trigger disabled. Preserve per-boot symbol
identity and stop at the first failure for attribution/retrieval. Keep BBM
separate and do not repeat healthy boots as a substitute for a causal result.
