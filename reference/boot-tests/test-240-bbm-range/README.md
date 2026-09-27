# Test 240: isolated A715 BBM range candidate hardware validation

Owner's active goal remains CPU-stall repair. The verified one-line arm64
maintainer fix 1fef81669147d63eb8c5d3627d54eadc21173a0b corrects an applicable
TLB end-address error, but no evidence establishes that it caused previous
CPU non-response. Test that candidate separately; do not relabel host range
regression as CPU-stall repair. Baseline tests 238/239 did not reproduce it.

Candidate: already compiled/hashed 0022+0024+0026, same config/DTB/profile as
236/238, no injection patch. Original kernel pin, drivers, power/frequencies,
rootfs and USB NCM/ADB stay unchanged. All build artifacts and exact symbols
are recorded in offline-reviews/20260927-a715-tlb-range/validation/artifacts.json.

One candidate boot only. Validate TWRP/device/backups/five partition hashes;
flash boot/vendor_boot only, full readback. Require independently read target
boot/capture IDs, ECC64, watchdog 1/1/1/10, READY, actual runtime relocation and
kernel notes. Observe >=150 seconds before workload, stopping on any CPU/RCU/
workqueue failure, transport loss, unexpected restart or suspect timeout.

Then run the archived process-private Python/ctypes workload on MIDR-verified
A715 CPU3 and CPU4, normal priority and eight seconds each. Map 1/2/16 pages,
write a tiny ARM64 return-42 function once, clear its I-cache, alternate RX/RW
permissions and check execution/data. Never RWX, no fixed addresses or global
VM settings. A private trace instance and PID-filtered named kprobe record
only three preliminary cycles to prove modify_prot_start_ptes was reached;
disable tracing before sustained work and remove only owned instrumentation
in finally. Host command timeout 45 s, device timeout 40 s, script alarm 35 s;
none guarantees recovery from a genuinely broken kernel. Preserve partial output.

The high-address workload demonstrates ordinary permission-change behavior
and path coverage, not low-address hardware-erratum reproduction or an end-to-end
proof of TLB invalidation scope. The host 120-case harness checks range semantics.
The kprobe adds observer effects; no throughput or failure-rate comparison is
claimed. Check journal, boot ID and trace cleanup after workload, then observe
>=60 further seconds. Stop and collect first failure, no repeated boot series.
If no failure occurs, verdict is candidate functional validation only.

Preserve a natural automatic snapshot and independent source journal if one
occurs, allow bounded configured recovery, and apply calibrated ECC/source
integrity requirements. Never infer missing events or use an observer's symbol
offset. Recovery uses BCB helper + ordinary reboot, not reboot recovery. Restore
original images with all-five hashes and a separate >=150-second production
observation before ending the trial. USB gadget is never reconfigured live.
