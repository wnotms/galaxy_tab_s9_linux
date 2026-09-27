# Decode the CPU feature variation before treating the taint as a fault

Test244's startup log has seven strict feature-variation warnings. Exact XOR
and pinned register field definitions identify every difference as SpecSEI:

| Register | CPUs | Boot → secondary field | XOR |
|---|---|---|---|
| ID_AA64MMFR1_EL1, bits 27:24 | 3–7 | 1 → 0 | 0x01000000 |
| ID_MMFR4_EL1, bits 3:0 | 5–6 | 1 → 0 | 0x1 |

No other bit differs within these reported register pairs. raw-warnings.txt
preserves the seven lines from target boot fd1a8ab6-85e9-40fb-b321-207faeaaa525;
analysis.json records all values, source/log hashes and the exact upstream pin.
Each field range was checked in its own register block in arch/arm64/tools/sysreg.

Pinned arch/arm64/kernel/cpufeature.c marks both fields FTR_STRICT and
FTR_HIGHER_SAFE. arm64_ftr_safe_value selects max(new, cur), so that policy
retains 1 for the reported 1/0 mix. This is source-policy inference, not a
direct read of the sanitized runtime register. The accompanying source
comment says 1 allows SError on an external abort from a speculative read;
assuming that possibility is the conservative choice. The strict mismatch
explains the feature-variation taint, not the reason for CPU non-response.

No feature policy, warning, register or kernel artifact was modified. Making
the check non-strict merely to hide the warning would not establish a CPU
fix. The warning alone proves neither defective hardware nor a causal link
to the stalls; this review also does not exclude an SError/firmware role.
The actual failed CPU's PC/stack remains the discriminating missing evidence.
