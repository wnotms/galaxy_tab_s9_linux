# Test 236: exact CPU activity snapshot survives normal reboot with ECC

The manual-snapshot console retention gate passed for this observation.
It does not establish a CPU fix, full event history, long-term stability or
automatic crash-triggered retention. No repeated wedge series is ready yet.

## Source and recovered evidence

Source boot `10f7f83a-d669-4855-8f24-87b5c6568aa6` reported READY at
100,000,000 ns for capture `c8ba1a85-3aef-476c-9498-d3734617f9ee`.
ECC=64 and watchdog/soft_watchdog/softlockup_panic/panic=1/1/1/10 were read
at runtime. Console threshold was 4; the existing pr_emerg snapshot uses
level 0, correcting test-235's probe eligibility mistake.

After more than 150 responsive seconds and no detected CPU stall in the
source journal, a manual dump produced eight valid CPU headers and all 48
event cells: **58 lines / 6,294 canonical marker bytes**. The first journal
fetch was incomplete because ingestion had not finished; it is preserved.
A later fetch captured the complete same snapshot, without another trigger.
The second dump request was correctly refused. Canonical SHA-256:
`91e01680ef6780a8bcfb2d35a142dc6a63cc904d3e00f2a6abf483963e209269`.

A direct ordinary reboot reached observer
`95089f53-9cd4-41d3-a799-85a648485731`, the immediately next retained journal
boot. Raw console bytes were pulled before slower journal queries. Two pulls
and the observer's device-side SHA-256 agree:
`0aba1198d4112cd2200635eda671fe2c070ed23dd03cded679f634ebbd7be361`.
Strict decoding and canonical-source comparison reproduce **every marker
byte exactly**, including the capture ID, CPU validity and event fields.
The recovered console reports:

```
ECC: 135 Corrected bytes, 0 unrecoverable blocks
```

`observer/verdict.json` contains the decoded cells and comparison result;
`observer/attribution.json` records retained-history adjacency. Unrecorded
boots remain outside that history's guarantees. The observer was used to
retrieve the source data, not counted as a 150-second stability trial.

## Build and rollback

Only existing diagnostic patches 0022 and 0024 were combined. Config/release
match production; DTB matches test-235's ECC64 variant. The existing test-230/231
diagnostic cmdline was reused and its arming independently checked. Rootfs,
USB NCM/ADB, CPU frequency, voltage and reserved-memory geometry were unchanged.
Four focused decoder tests passed. The initial incremental build refused a
leftover untracked diagnostic source file; a clean ccache build then passed.
Both build logs, bundle identity and exact symbol-artifact hashes are saved.
No full host suite or CI was run for this isolated diagnostic combination.

Only boot/vendor_boot were flashed; complete readbacks passed, and
init_boot/dtbo/vbmeta matched production. The standard BCB helper successfully
requested TWRP after collection. Original boot/vendor_boot were restored with
full readbacks; all five partition hashes match production. Restored boot
`d5fd2f74-0854-41f4-b8f2-94874d63340f` is responsive with ECC=0, SSH/adbd
services active and the same USB NCM address. The same boot stayed responsive
beyond 151 seconds with zero failed units and no detected CPU non-response,
RCU stall or workqueue lockup in its final journal. USB ADB worked; a Windows
TCP check received the SSH protocol banner over NCM (no authenticated-shell
claim). This closes the observation and rollback, not long-term stability.

## Next gate

Normal-reboot integrity is now demonstrated for the actual bounded CPU
snapshot, following test-235's binary PMSG pass. Validate the automatic
RCU-triggered/crash path separately before using retained snapshots to guide
a causal kernel change. Even a complete snapshot contains last positive
activity only: overwritten/nested events, invalid writers and unsynchronized
cross-CPU timestamps cannot support missing-event conclusions.
