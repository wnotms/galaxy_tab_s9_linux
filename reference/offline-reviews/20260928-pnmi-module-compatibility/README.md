# Pseudo-NMI capture follow-up: module compatibility gate

Test245 supplies new positive evidence: an ordinary CPU2 backtrace request at
30.682872 s is interrupted by another CPU's softlockup panic at36.543400 s.
The ten-second backtrace wait has not finished. The next capture should retain
245's corrected BBM code/lastactivity/ECC64 and use the calibrated pseudo-NMI
route, with warning-level console retention. No deliberate fault or KFENCE
disable is proposed. This is explicitly a combined diagnostic, not a claim
that BBM or pseudo-NMI fixes CPU failure.

Pinned source audit adds a module gate: `cpucap_is_possible()` in
arch/arm64/include/asm/cpucaps.h returns CONFIG_ARM64_PSEUDO_NMI for
ARM64_HAS_GIC_PRIO_MASKING. `alternative_has_cap_unlikely()` returns false
without an alternative site when that capability is compile-time impossible.
`system_uses_irq_prio_masking()` feeds the inline IRQ save/restore functions.
Thus this config *can* affect module code using those inlines; release/vermagic
alone is not a complete compatibility proof. That does not prove any current
driver actually embeds the affected inline, or that prior failures arose from
a module mismatch. Test245 itself uses the non-PNMI kernel.

Read-only current-device evidence records12 loaded module file hashes. Two
pulled files (ath11k_pci and gpio-shared-proxy) have matching before/after hashes
and were inspected without changing device files. Neither contains capability35
(priority masking), but neither contains an IRQ-mask instruction either; the
gpio proxy has no alternatives section. **This is not positive proof of a
DAIF-only module defect.** Their bytes also do not match the available older
poweroff-trace artifacts, so do not assign those artifacts' build configuration
to the installed modules. See module-audit.json for exact scope and failed
local working-copy extraction attempts; fresh copies were verified afterwards.

Build the new kernel and all configured modules together (BUILD_MODULES=1),
then compare actual needed module code/CRCs and preserve installed-module
backups before deciding which files need replacement. Do not silently reuse
an unknown module build, or assert historical in-memory identity from today's
files. Existing test241 CPU0 in-kernel calibration remains measured evidence;
it did not establish this broader module compatibility question.

The restored UPower issue has a separate straightforward configuration
explanation: its PrivateUsers=yes requires user namespaces, while both existing
kernel configs explicitly have CONFIG_USER_NS unset. This is not evidence of
CPU failure. Keep its health failure visible; do not change namespace settings
or service isolation within the CPU capture experiment.
