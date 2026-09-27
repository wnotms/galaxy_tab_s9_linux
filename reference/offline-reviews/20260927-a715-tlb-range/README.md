# A715 BBM flush-range defect: present, CPU-stall causality unproven

The pinned `modify_prot_start_ptes()` passes `nr * PAGE_SIZE` as the end of
`__flush_tlb_range(vma, addr, end, ...)`; the API requires `addr + nr * PAGE_SIZE`.
The source excerpt is saved. Runtime test-238 detects ARM erratum 2645198;
CONFIG_ARM64_ERRATUM_2645198=y and CPUs 3/4 have A715 MIDR 0x411fd4d0.
This establishes code/hardware applicability, not that a failed boot executed
this path or that it caused any CPU to stop responding.

The author proposed this one-line correction on 2026-09-23. Catalin Marinas
reviewed it and Will Deacon reported applying it to arm64 for-next/fixes as
1fef81669147 on 2026-09-24. Primary maintainer mail mirrors:
https://lkml.iu.edu/2609.3/00737.html
https://lkml.iu.edu/2609.3/00846.html
A later direct fetch recovered the full kernel.org patch and matching commit
1fef81669147d63eb8c5d3627d54eadc21173a0b. GitHub compare against master reports
diverged, behind_by=1: this fix is not a master ancestor at this check. The
original web-tool fetch failure is not evidence that the commit is absent.
Do not label it merged into the pinned/mainline tree.

For usual high user addresses the unsigned size calculation overflows and
falls back to an ASID-wide flush; some low-address cases underflush. The
reported A715 consequence is corrupted fault-address/syndrome registers after
an execute-permission fault, not demonstrated CPU lockup. The actual primary
failure reports involve several CPU types. An opt-in diagnostic backport is now prepared as patch 0026, with a
range-behavior regression harness using the actual extracted function. Keep
it separate from the unchanged natural-capture trial. No candidate has been
flashed and production defaults remain unchanged. This is a concrete kernel
correctness lead, not proof of the requested CPU-stall repair.
