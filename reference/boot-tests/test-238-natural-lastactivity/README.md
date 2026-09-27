# Test 238: first natural-stall capture after retention calibration

Owner continues the CPU-stall repair goal. Tests 236/237 completed manual
retention, real RCU-triggered capture and controlled-panic retention gates.
Reuse the exact hashed 236 candidate (0022+0024), matching its saved vmlinux;
no rebuild, injection patch, trigger write or manual panic. Normal defaults
and rootfs/USB configuration are unchanged. No driver/power/voltage change.

Question: if this single target boot naturally stalls, what positive final
IPI/CSD activity is recorded on the positively identified unresponsive CPU?
Map function/reason pointers against this exact Image's symbols. Do not infer
missing events, causality, DAIF/GIC state or complete history from last cells.
A valid sequence is a consistent copy, not evidence of CPU health.

Verify current source/boot history and all production partition/backup hashes.
Flash only boot/vendor_boot in TWRP, with full readbacks. Save new target
boot ID, capture ID, READY, ECC64, cmdline and independent runtime watchdog
1/1/1/10. Poll for at most 300 seconds of target uptime, stopping at the first
positive stall, suspect condition, lost transport or unexpected boot. Archive
bounded-time identity and raw journal calls. An early failure lacking a live
arming sample remains profile-unverified. A clean window is not a CPU fix.

On natural RCU capture retrieve complete journal markers if possible without
manual snapshot or reset injection. Stop on the first failure, allow the armed
recovery mechanism a bounded interval, then retrieve raw pstore twice and
compare hashes, ECC status, immutable IDs and any independently saved source.
A failed shell alone is not a CPU-wedge verdict. A changed boot needs retained
history attribution. No infinite reboot series; manual recovery may be needed
if the kernel cannot reset. Never unbind the shared USB gadget.

ECC-corrected records without an independent live reference have weaker
integrity evidence than calibration; record that limit explicitly. Invalid,
incomplete, unexplained or uncorrectable fields cannot identify the culprit.
Use TWRP disk journals including .journal~ and original systemd-pstore FILE
bytes if later boots overwrite archives. Restore originals and verify all five
hashes after collection; independently check the final production boot.
