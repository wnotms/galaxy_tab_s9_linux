# Pseudo-NMI: untested route to the missing CPU stack

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
are not a demonstrated pseudo-NMI capability. No pseudo-NMI kernel has been
built or flashed by this review. No production/default change is made.

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
all output and stop on any unexpected stall. This design is not implemented
yet and its exact helper must be reviewed before use.

A successful calibration would justify a bounded natural-capture trial aimed
at obtaining the actual target PC/stack. Failure to deliver still does not
separate firmware, hard masking, GIC state and CPU non-progress. Retained
markers need the same ECC/integrity/boot attribution and per-boot relocation
checks. Restore originals and independently verify final boot after testing.
