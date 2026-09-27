# Test 240: BBM range candidate passes bounded permission workload

The candidate boots and passes ordinary executable-permission changes on the
two A715 cores. This establishes functional hardware validation for this
workload, not that the TLB range defect caused or fixed the intermittent CPU
non-response. The unmodified recorder also had clean windows in 238/239.
No natural automatic snapshot was produced in this trial.

## Identity and arming

Target `fe1196f2-4464-4c82-b63e-7f875c88223b`, capture
`9a7f258a-6bef-4efa-947c-ccb3d9f0de07`, ran the exact 0022+0024+0026 candidate.
Full partition readbacks matched, kernel notes matched out/test240/vmlinux,
and six symbol anchors independently agreed on runtime relocation +0x1b8000.
Runtime ECC64 and watchdog/soft_watchdog/softlockup_panic/panic=1/1/1/10 were
read. READY at 100,000,000 ns and ARM erratum 2645198 are in the target journal.
Retained history places it directly after the saved production anchor.
The target passed 169.42 seconds before workload setup.

## Setup failure, scoped retry and real execution

The first script invocation stopped at Python text append open of tracefs
kprobe_events, EINVAL, before creating a probe or performing permission
changes. It only allocated/freed private mappings. Raw non-truncating
os.open(O_WRONLY) succeeded in an isolated check while text append failed.
The same boot stayed responsive, no probe/instance remained, and no CPU fault
was logged. Initial code, stderr, hashes and command results are preserved.
The reviewed v2 retry used non-truncating raw writes; no kernel rebuild,
reboot, global probe removal or trial-budget expansion was needed.

CPU3 and CPU4 independently reported MIDR 0x411fd4d0. Private 1/2/16-page
mappings alternated RX and RW, never RWX; a generated ARM64 return-42 function
and its instruction bytes were checked. No global VM, power or USB settings
were changed. A PID-filtered private trace recorded six calls to the actual
modify_prot_start_ptes function at the three mapped addresses. All observed
batches had **nr=1**: this proves the single-present-PTE high-address path was
reached, not low-address or multi-PTE hardware erratum reproduction.

Tracing was disabled before sustained work. CPU3 completed 502,608 iterations
(3,015,648 mprotect calls) in eight seconds; CPU4 completed 505,719 iterations
(3,034,314 calls) in eight seconds. Total **6,049,962** sustained permission
changes returned successfully, with execution/data checks passing. This is
not a comparative benchmark or a failure-rate measurement. The 120-case host
harness separately proves corrected range semantics, not physical stability.

Owned tracing state was removed, the temporary device script was deleted,
and the same target reached uptime 353.10 seconds, 75.75 seconds after the
workload, with zero failed units and no detected CPU/RCU/workqueue failure.
The retained source journal is unchanged apart from normal service messages.

## Rollback and interpretation

Original boot/vendor_boot were restored through BCB/TWRP with complete
readbacks; all five partition hashes match production. Final production boot
`c333bb1b-d09b-4b32-ac4f-d8e166d4cac7` passed a 153.52-second observation with
ECC=0, zero failed units and no detected CPU fault. USB ADB responded and NCM
returned the SSH protocol banner; no authenticated-shell or long-term stability
claim. No production patch/default is adopted based on this trial.
The owner goal remains open: a clean bounded candidate workload cannot prove
repair of an intermittent failure that was not reproduced by its control.
Use this validated patch as a separately identified candidate, preserve the
calibrated recorder, and require natural fault evidence or a discriminating
reproducer before attributing the CPU problem to BBM/TLB handling.
