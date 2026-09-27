# Test 238: natural stall not reproduced in one 305-second boot

Target `2271ea0e-37e7-4e73-8ea5-8ff34497b868`, capture
`078ab816-b228-4c31-bd6b-ee289d395df3`, used the exact test-236 0022+0024 image.
Runtime ECC64/watchdog 1/1/1/10 and early READY were verified; no injection
flag or manual snapshot was used. The same target responded through 304.96
seconds and its final journal contains no detected CPU/RCU/workqueue failure.
There is no automatic snapshot and no root-cause conclusion. One clean boot
is not a repair or a failure-rate estimate.

A symbolization precheck caught a nonzero runtime relocation despite nokaslr:
all six checked anchors are linked-address + 0x8000. The device's kernel notes
SHA-256 exactly matches the saved vmlinux's .notes. Unrelocated exploratory
decoding produced nonsensical symbols and was rejected, never used as fault
evidence. Preserve/verify runtime relocation for each later target; do not
assume a different boot has the same offset. The complete raw runtime kallsyms
is stored as lossless gzip; stdout command metadata is unchanged.

The owner goal remains CPU repair. A separately registered test-239 permits
at most two additional natural boots of the same current candidate. Original
image restoration is deferred to that session's end to avoid redundant
rollback/reflash writes, and is recorded there. The initial single-boot plan
and its clean result are retained unchanged. CPU cause and repair remain open.

Test-239 subsequently completed the shared-session rollback: all five hashes
match production and final boot 0893538f-26ac-4965-9d76-f57b3b7886c5 passed
a 162.65-second observation. See its RESULTS.md and production/verdict.json.
