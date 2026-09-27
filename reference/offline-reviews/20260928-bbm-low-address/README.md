# Low-address BBM coverage review (2026-09-28)

Scope: prepare a bounded, **non-faulting** missing-path check for opt-in 0026.
This does not reproduce erratum 2645198 or establish CPU-stall causality.
Pinned source remains a13c140cc289c0b7b3770bce5b3ad42ab35074aa; the exact
maintainer correction and earlier extracted-function regression are in
`../20260927-a715-tlb-range/`. No kernel/default/power change in this review.

## Why this is different from test240

`mm/mprotect.c::change_pte_range()` bounds batching by the requested range.
One aligned 4K page therefore limits `nr` to 1. At address 4096, the old
`modify_prot_start_ptes()` passes start=4096/end=4096. In
`arch/arm64/include/asm/tlbflush.h::__do_flush_tlb_range`, pages=(end-start)>>12
is zero; corrected end=8192 gives one page. Test240's six high-address nr=1
hits do not cover this branch. They also did not record the old PTE.

The proposed entry kprobe reads the original PTE through x2 while the caller
holds the PTE lock. PTE_VALID bit0 guarantees `pte_accessible()` for either
pending-flush state; UXN bit54 clear proves `pte_user_exec()`. Runtime erratum
capability and exact fixed kernel notes must separately pass the host gate.
This observes inputs to the known function, **not an end-to-end hardware TLB
invalidation measurement**. An execute-permission fault would need a separate
design and registration; this helper deliberately never executes an NX page.

## Concrete helper and limits

`low_address.py` has no default action. `--run` requires an exact current boot
ID and notes hash; it checks board, native ARM64, existing mapping permission,
CPU3/4 A715 MIDRs and affinity. Existing CAP_SYS_RAWIO is needed below the
current minimum. The read-only device preflight recorded minimum=32768 and
CapEff=000001ffffffffff (RAWIO present), not proof an eventual mmap succeeds.
Security hooks or address occupation can still reject it.

Child uses MAP_FIXED_NOREPLACE at 0x1000, checks the returned address and never
changes global mmap_min_addr. No fallback address or MAP_FIXED replacement.
It writes/clears I-cache once, alternates RW→RX→call(return42)→RW four times
on each verified A715: **16 mprotect calls total**. It reads code while NX;
no intentional fault, RWX page, stress loop, hotplug or global VM setting.
Child unmaps on normal/error exits; process teardown handles fatal signals.
Core dumps disabled; SIGALRM 8 s, parent timeout 12 s, kill wait 2 s. These
cannot rescue a kernel wedged in uninterruptible work.

Parent owns a uniquely named 16 KiB/CPU trace instance and entry probe, refuses
preexisting names, filters child PID and address4096 before releasing it.
Address filter excludes dynamic-loader RELRO mprotect calls. It requires
exactly alternating NX/exec old PTEs, eight entries/four executable entries per
CPU, valid old PTEs, nr=1 and complete zero-loss stats for all eight CPUs.
Missing/extra/malformed evidence fails closed. Raw trace/stats and child
output/status survive in JSON; cleanup attempts each owned resource even
after failure. No global trace reset or USB/SSH configuration action.

Offline tests replay actual test240 evidence (rejected), valid synthetic
coverage, missing/reordered/extra entries, wrong CPU/PID/address/batch/PTE,
loss/missing statistics and execution guards. They do not exercise real ARM
mappings, tracefs creation, or signal recovery on a wedged kernel; those remain
physical validation limits. Use the already corrected test240 candidate for
the first hardware check; do not deliberately test the erroneous kernel.

## Startup observation budget review

The owner's question exposed an unjustified default: 300 s is conservative,
not a measured prerequisite for startup confirmation. Two concrete failures:
test229 raw dmesg first RCU warning 29.331149 s, CPU6 non-response 39.332517 s;
test235 audited kernel source times CPU2/5 non-response 38.404773/48.405993 s.
These are report times, not onset times or an exhaustive failure distribution.
Hung-task output after 120 s can be a later symptom of an already detected
failure. Neither these examples nor a 300 s clean boot prove long-term health.

For the next focused coverage test use a **120 s total-uptime startup window**,
collect from the first connection, require readiness/profile by 90 s, run the
tiny workload once after 60 s, and retain at least 30 s afterward. If gates
take too long, stop/inconclusive instead of extending the budget. Positive
failure stops the workload immediately, with up to 20 s additional evidence
collection for backtrace completion. No repeated no-fault boot series. Longer
soak tests require a separate late-failure or repair-validation question.
This is a scoped new budget, not retroactive relabelling of earlier trials.
