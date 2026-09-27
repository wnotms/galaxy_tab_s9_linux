# Test 239: neither bounded follow-up boot reproduced CPU failure

Both allowed target boots completed their registered windows without detected
CPU non-response, RCU stall or workqueue lockup. This is not a CPU fix, a
failure-rate estimate or proof of long-term stability. No fault snapshot was
produced, so there is no new failed-CPU activity to interpret.

| Target | Boot ID | Capture ID | Last observation |
|---|---|---|---|
| 1 | 46133f14-b880-49f8-9ace-4b44fd5791b9 | 73e8d188-2de2-4198-a744-0cdbc322d8c6 | 184.33 s |
| 2 | 13b10508-4691-4cd9-ba4e-d9a8144550df | dd21fb21-1a79-4b34-85dd-66fd7d106651 | 184.36 s |

Each target independently reported ECC64, watchdog/soft_watchdog/
softlockup_panic/panic=1/1/1/10 and the intended cmdline without injection.
Each retained boot list places it immediately after its saved predecessor;
no unexpected recorded restart occurred. Runtime symbols and kernel notes
were saved independently; both match the reused test-236 candidate, but
runtime relocation differs: target 1 +0x100000, target 2 +0xd8000. An initial
check assuming the test-238 +0x8000 offset correctly failed; no fault data was
decoded under that rejected assumption. Always use the actual target offset. No additional target is started under this budget.

Combined with test 238, the unchanged instrumented kernel completed one
305-second and two 184-second windows without reproduction. The recorder can
change timing and there is no uninstrumented concurrent control, so this does
not establish a lower failure rate or eliminate any causal hypothesis.

The CPU repair goal remains open. During these observations a separate source
review found the A715 BBM range defect already corrected in arm64 maintainer
commit 1fef81669147d63eb8c5d3627d54eadc21173a0b. Its local code/hardware
applicability and host regression are established, but its relationship to
CPU non-response is not. Patch 0026 is opt-in and was not used in these boots.
See `reference/offline-reviews/20260927-a715-tlb-range/` for exact provenance.

Original boot/vendor_boot were restored through the BCB helper and TWRP.
Complete readbacks and all five production partition hashes match. Final
production boot `0893538f-26ac-4965-9d76-f57b3b7886c5` stayed responsive through
162.65 seconds with ECC=0, zero failed units and no detected CPU failure in
its final journal. USB ADB works and the unchanged NCM path returns the SSH
protocol banner; no authenticated SSH shell or long-term stability claim.
The same rollback closes the deferred test-238 restoration.
