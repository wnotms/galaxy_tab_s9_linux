# Pseudo-NMI: calibrated route to the missing CPU stack

The CPU repair goal is unresolved after test 240. The BBM range candidate
passed a bounded permission workload, but no natural failure occurred and no
causal link was established. Higher-priority backtrace delivery is a separate
supported diagnostic option; this review prepares it, not a fix claim.

## Correction to the old exclusion

Existing fault logs prove that a target did not answer an ordinary backtrace
IPI. CONFIG_ARM64_PSEUDO_NMI is unset in both production and tests 236–240.
The old statement that this is stronger than failing an NMI, or excludes an
NMI-only capture mechanism, reverses the implication. It is withdrawn in
CPU_WEDGE_EVIDENCE.md and the Fedora comparison summary. No raw log changed.

Pinned a13c140cc289c0b7b3770bce5b3ad42ab35074aa source establishes:

- arch/arm64/Kconfig: ARM64_PSEUDO_NMI provides GIC-priority NMI-like interrupts;
  it requires explicit irqchip.gicv3_pseudo_nmi=1 as well as the config option.
- arch/arm64/include/asm/irqflags.h: ordinary local IRQ disable uses DAIF without
  priority masking, ICC_PMR_EL1 with it. This changes interrupt-mask behavior
  and can perturb the failure; it is not a passive observer or hardware NMI.
- arch/arm64/kernel/smp.c: ipi_should_be_nmi() selects CPU_BACKTRACE only when
  system_uses_irq_prio_masking(); ipi_setup_sgi() requests a per-CPU NMI then.
- drivers/irqchip/irq-gic-v3.c: gic_enable_nmi_support() can decline support;
  a config/command-line token alone does not prove it is active. It emits a
  positive Pseudo-NMIs enabled message and sets IRQCHIP_SUPPORTS_NMI on success.
- cpufeature.c and GIC platform quirks impose runtime restrictions. Do not
  bypass those or force distributor security changes to make a probe pass.

Test 240 positively reports GICv3, SGIs without active state,
GICD_CTLR.DS=1 / SCR_EL3.FIQ=0. These identify the observed integration; they
are not a demonstrated pseudo-NMI capability. This was the pre-test capability review. Test 241 subsequently built and
flashed the isolated candidate; see the measured result below. No production
or default change is made.

## Next discriminating calibration

Prepare a separate opt-in CONFIG_ARM64_PSEUDO_NMI diagnostic, using the
calibrated lastactivity/ECC64 recorder and original driver/power settings.
Keep the independent BBM candidate separate unless explicitly registering a
combined profile; do not silently change two causal variables. Preserve the
production image and exact symbols.

Before any natural-fault series require runtime support, correct backtrace
IPI setup and a healthy 150-second boot. Test one short bounded normal-IRQ
masked region on a known CPU while a different CPU requests its backtrace.
The test must use normal local_irq_save()/restore(), never raw DAIF masking,
and only run when runtime priority masking is positively active. Give both
worker setup and the masked interval explicit deadlines and once-only/root
controls. Confirm the target stack and NMI context while the region is still
active; a delayed ordinary backtrace after restoration is not a pass. Preserve
all output and stop on any unexpected stall. This design was implemented as opt-in patch 0027 and tested in test 241;
its exact helper, build and host behavior checks are archived there.

A successful calibration would justify a bounded natural-capture trial aimed
at obtaining the actual target PC/stack. Failure to deliver still does not
separate firmware, hard masking, GIC state and CPU non-progress. Retained
markers need the same ECC/integrity/boot attribution and per-boot relocation
checks. Restore originals and independently verify final boot after testing.

## Test 241: bounded IRQ-masked capture and warm retention passed

On source boot `3bfa876b-be6e-49d3-8029-79e65d0f7ba6`, GICv3 positively
enabled pseudo-NMIs. Kernel notes and six runtime symbol anchors matched the
saved vmlinux; this boot's offset was `+0x20000`. After 158 seconds without
detected CPU failure, CPU0 held normal local IRQs masked for 200,000,157 ns.
The real backtrace callback arrived 61,407 ns after the recorded start, with
`in_nmi=1`, saved PMR `0xc0` indicating IRQ masking, and PSTATE.I clear. The
interrupted PC resolves to `arch_counter_get_cntvct+0x14/0x30`, beneath
`ktime_get_mono_fast_ns` and `gts9_pnmi_masked_region` in the target stack. Both
workers completed, setup_error=0, IRQs were restored, and a second trigger
was rejected. Another 73.01 seconds passed without a detected CPU failure.

The immediate ordinary-reboot observer `e72b6d0c-fbf6-4348-bccb-93db1c14e98b`
recovered the same 28 lines / 1,583 payload bytes, including registers and
stack, exactly. Two raw pulls and the device hash agree; ECC corrected 61
bytes with zero unrecoverable blocks. Console level 5 admitted priorities
0..4; source comparison used those priorities and preserved payload spaces.
See [test-241 evidence](../reference/boot-tests/test-241-pnmi-calibration/RESULTS.md).

This proves the defined healthy CPU0 PMR-masked calibration and warm retention.
It does not prove delivery to a naturally stuck CPU, all eight CPUs, raw DAIF
masking or firmware execution, nor crash-path retention of this new backtrace.
No CPU-failure cause or repair was found. Next pre-register one bounded natural
failure capture with pseudo-NMI enabled and the calibration trigger disabled,
keeping exact symbols, per-boot offsets, ECC and positive-evidence limitations.
No need to repeat this synthetic calibration or combine the independent BBM
fix merely because the natural fault has not yet appeared.


## Test 242: no natural fault in the registered single boot

With the exact test241 kernel and only calibration enable=0, target
c2f8ec82-d57e-4c42-8dc9-7ab2b3900f08 passed 308.48 seconds without detected
CPU failure. It supplied no natural-fault stack. Its six-anchor offset was
+0xb0000; notes matched. Helper enable=N/started=0, GIC priority masking,
ECC64 and 1/1/1/10 were verified. See test242 RESULTS.md; no repair/rate claim.

A next diagnostic can reduce perturbation by disabling the optional
lastactivity callbacks while keeping standard pseudo-NMI backtrace delivery.
la_init returns before probe registration if gts9_lastactivity is not 1; the
active probes add preemption/atomic/barrier/clock work to IPI/CSD paths. This
is a source-based reason to simplify the observer, not proof of a hidden
race or recorder causality. Test235's recorder-free failures remain relevant
positive evidence, not a controlled comparison. Pre-register any new capture
and preserve source timestamp fields; do not infer kernel-event durations
from rendered journal receipt-time spacing.


## Tests243/244: recorder disabled, standard route retained

Runtime gates confirmed that both optional recorder/calibration were inactive
with unchanged compiled kernel bytes. One TWRP-entry window (306.92 seconds)
and one separately registered direct-reboot window (304.07 seconds) yielded
no natural fault. Exact source-clock JSON, per-boot notes/anchors and unique
priority-0 userspace markers were preserved. Test244 completed the shared
rollback and independent production check. This completes those attempt budgets,
not the CPU repair goal or a rate/observer-effect comparison. See their results.

## Test245 failure and module gate for the next capture

The fixed-BBM ordinary-IRQ target245 naturally stalled: RCU requested CPU2's
backtrace at30.68 s, then CPU1's synchronization waiter panicked at36.54 s,
before the10 s backtrace wait ended. Attributed retained records give the waiter
and last activity but not CPU2's PC. This new positive evidence motivates one
explicit combined246 profile: retain245's BBM/recorder/ECC and add the calibrated
priority-mask route plus warning-level console output, with no injection helper.
Standard show_regs includes saved PMR when runtime priority masking is active.

Do not silently carry unknown modules into that config. Pinned cpucap_is_possible
folds priority masking to false when PSEUDO_NMI was disabled at compile time.
A full167-module comparison now finds affected allocated code/alternative sites
in bluetooth, mac80211 and ath11k, despite equal imported-symbol CRC mappings.
The previous built-in CPU0 calibration did not establish module compatibility;
this does not retrospectively identify historical module bytes or a CPU cause.
246 kernel/modules are built and packaged together, originals backed up and
the swap/restore checked offline. See test246 BUILD_RESULTS.md. Hardware scope
remains one120 s startup and rollback of BOTH images and any replaced modules.

## Test246 closed; earlier CSD capture preparation

Test246's matched kernel/modules ran one120.08 s window with no detected fault,
then both modules and images were restored. It did not supply CPU2's missing PC.
Test247 now targets the existing5 s CSD timeout instead of waiting for RCU.
The pinned path already calls dump_cpu_task -> arm64 backtrace -> pseudo-NMI;
no new local handler is required. The additional CSD debug/default config is
opt-in and its compile/module/runtime gates remain required. This changes
observer timing, including the sender's watchdog touches during NMI collection;
it is not a fix or an automatic-recovery guarantee. See the early-csd-pnmi
source review and test247 registration before hardware.
