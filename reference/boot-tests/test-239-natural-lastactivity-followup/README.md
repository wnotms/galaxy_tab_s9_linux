# Test 239: bounded follow-up natural-failure capture

Prospective continuation of the owner's CPU repair goal. Test 238's one
300-second target observation must finish clean before this begins. A clean
window does not resolve the previously observed intermittent CPU failure.
Keep the exact currently installed, verified 236/238 candidate (0022+0024),
without another flash, manual dump, panic or injection. Restore originals
once this capture session ends; avoiding an intervening rollback/reflash
avoids two unrelated boot observations and four partition writes. This does
not alter test 238's registered single-boot result.

Budget: at most TWO additional ordinary Debian boots, each observed for at
least 180 seconds of its own uptime. This is stop-at-first-failure forensics,
not a rate estimate. Stop on failure, suspect signature, missed identity,
transport loss or unexpected reboot. A non-clean first target prohibits the
second planned target. No further target beyond this fixed budget without
new evidence review. Record immutable boot adjacency and independently read
watchdog 1/1/1/10, ECC64, READY/capture ID each time. Retain boot-list anchor
before each reboot, and confirm the target is its immediate retained successor.

Use the exact same last-positive-activity question and integrity limitations
as test 238. Match runtime symbols/notes rather than assuming nokaslr implies
zero relocation; test 238 measured runtime minus link = 0x8000, but verify the
actual failed target when available. An unresponsive shell is not proof of a
CPU fault. Preserve raw partial output; allow bounded automatic recovery, then
use TWRP or owner-assisted recovery if needed. Compare pstore to independent
live source whenever possible; missing or invalid records are inconclusive.

Restore original boot/vendor_boot through TWRP with full readback and all-five
partition hashes. Final production health is a separate >=150-second check.
No USB gadget changes, kernel/clock/voltage changes or claims of CPU repair
without actual evidence supporting a correction.
