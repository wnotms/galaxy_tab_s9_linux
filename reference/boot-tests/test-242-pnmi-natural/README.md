# Test 242: one natural-fault capture with calibrated pseudo-NMI

The previous goal turn made progress: test241 measured a genuine in-window
pseudo-NMI callback and exact warm retention of the target stack. CPU repair
remains unresolved. This trial asks for an actual spontaneously stalled CPU's
PC/stack, not another synthetic success or a failure-rate estimate.

Reuse the exact test241 kernel/config/DTB/symbols (0022+0024+0027, PSEUDO_NMI);
only change the early boot parameter gts9_pnmi_test.enable from 1 to 0. The
helper's init and callback return immediately when disabled, and its run
setter rejects before changing started. Verify enable=N, started=0, no helper
READY, kernel notes/six target relocation anchors, GIC pseudo-NMI enable,
watchdog 1/1/1/10, ECC64 and console threshold 5 live. Do not trigger manual
snapshots, backtraces, calibration, hotplug, workload or panic. No BBM patch.
Pinned RCU stall path calls dump_cpu_task(), whose target backtrace uses the
now-calibrated ARM64 pseudo-NMI route when runtime priority masking is active.

Attempt budget: one candidate boot, observe until 300 seconds of target
uptime. Capture kernel journal continuously to the host by immutable boot ID,
alongside bounded health checks every 15 seconds; fetch the final target
journal and retained boot list. Stream failure, changed boot, incomplete
identity, or DPU/MMC/RPMh timeouts are not clean CPU-stability evidence. Stop
at the first positive CPU/RCU/workqueue failure or other non-clean result;
allow up to 20 seconds for its backtrace output without starting another
trial. Preserve partial stream/timeout outputs and process exit status.

On failure, prioritize the target's live journal and own anchors/capture ID.
If it automatically reboots, retrieve two raw console copies/device hash and
retained adjacent boot IDs before recovery. Attribute only the failed target;
never reuse observer offsets. A retained snapshot without live reference is
not end-to-end integrity proven even with zero ECC unrecoverable blocks.
If fully unresponsive, use the existing recovery path if possible; otherwise
request the owner's TWRP action and continue offline analysis. Do not infer
CPU root cause from non-response, a healthy remote CPU stack or missing events.

If no failure appears, report only the bounded window and stop this attempt.
Do not extend/reboot it repeatedly or claim pseudo-NMI repaired the issue.
Restore original boot/vendor_boot, verify all five partition hashes, and
observe the original system >=150 seconds with ADB/NCM SSH protocol checks.
Keep recovery, init_boot, dtbo, vbmeta, rootfs and the USB gadget unchanged.
All artifacts/backups and the exact bundle must validate before flashing;
only packaging validation is needed for unchanged compiled kernel bytes.
