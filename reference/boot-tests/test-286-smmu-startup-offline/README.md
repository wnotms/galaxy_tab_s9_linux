# Test286 — offline display startup SMMU attribution

Purpose: map Test284's restored Test263 context103 records to the pinned Linux
source and sealed compiled DTB, and qualify a new **diagnostic-only** host profile.
No device commands, physical retry, kernel build or hardware changes in Test286.
Test284's STOP and final journal suspect remain sealed and unchanged.

The compiled DTB maps MDSS `ae00000.display-subsystem` to apps_smmu SID0x1c00.
Its splash reservation is `[0xb8000000,0xbab00000)`. All ten Test284 restored-boot
fault addresses lie there. The triplets occurred at source139044–139722us,
before SM5440 probe147315us and SM5714 charger/TCPC registration. This identifies
the stream/address range and chronology, not a harmlessness or causal proof.
The SMMU reports70 context banks; FSYNR0's S1CBNDX103 is a diagnostic field,
not evidence that context bank103 is a valid programmed hardware bank.
The precise bootloader/display handoff mechanism remains UNKNOWN.

`gate.py` requires current **same-boot full identity and healthy pump-OFF state**,
then preserves shared CPU/fault/QCA gates and Test283's bounded ADC_UPDATED
startup check. All SMMU context/FSR/syndrome records must form complete ordered
triplets, exactFSR402/SID1c00/cb9/lowflags0x21/splash range/priority3,
at most10 triplets in the first200ms, each complete within1ms, one tag per boot.
Only already-observed98/99(shared),102(Test275/283),103(Test284) tags are eligible.
Later/missing/mismatched/mixed/unknown/excess records and any unclassified suspect
STOP. Incremental journals cannot receive this startup classification.
All raw records remain in derived reports: no stability-clean or charging grant.

Sources at pin `a13c140cc289c0b7b3770bce5b3ad42ab35074aa`:

- `arch/arm64/boot/dts/qcom/sm8550.dtsi`: MDSS stream mapping.
- `drivers/iommu/arm/arm-smmu/arm-smmu.h`: FSYNR0_S1CBNDX/PNU/PLVL masks.
- `drivers/iommu/arm/arm-smmu/arm-smmu.c`: context/FSR/FSYNR diagnostic sequence.
- Current X710 DTS + sealed272 DTB: actual splash region and phandle mapping.

Additional read-only symbol audit uses the matching272 ELF in `.work/build/`,
not an invented `out/.../vmlinux` path. `sm5440_passive_request_fresh` begins with
PACIASP. Pinned ARM64 `aarch64_insn_is_steppable_hint()` includes PACIASP and BTI.
This rules out a blanket assertion that these hints are unsupported; it does
not prove device kprobe admission. No alternative offset or symbol is introduced.

Qualification:19 affected offline tests, real284 candidate99/restored103 journal
replays, adversarial fields/pairing/count/time/current-health/CPU tests, syntax
and input/seal verification. Reuse unchanged272/276/279/280/283/285 qualification;
no repeated kernel build/full suite/routing/CI. Next is a separately registered
single passive trace selecting Test285's command I/O adapter, with all essential
rescue/identity/safety gates and unconditional exact263 rollback.
