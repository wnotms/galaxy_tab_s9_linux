# D drive project staging cleanup — 2026-10-02

Owner requested removal of unused test records/images because D: was full.
Only historical project staging under D:/android/gts9-active was cleaned.
Before:998244352bytes free (~952MiB). After:6786527232bytes free (~6.32GiB).
Observed increase5788282880bytes (~5.39GiB); filesystem/WSL concurrent allocation
means it differs slightly from the sum of removed files.326files removed,
5799199754bytes of staging contents, zero unmatched files deleted.

5480159480bytes were byte-identical SHA-256 duplicates of retained WSL artifacts/
archived evidence. Two old uncompressed modules tar files (316047360bytes) had
the exact181module-file name/content sets already preserved in the original WSL
compressed archives; release-root prefix normalized, archive headers/directories
are not claimed byte-identical. Their original SHA and retained archive SHA,
file counts and correspondence are recorded. Module payloads were not changed.

2992914bytes of small scripts/packets/records were copied and hash-verified under
.work/host-storage-cleanup/2026-10-02/unique-windows before removal. Existing raw
reference evidence was retained; three unique verified packets are additionally
tracked under preserved/. No historical test results/seals were rewritten.
manifest.json lists every removed path/hash/retained counterpart and classification;
validation.json checks absence/preserved hashes and remaining namespaces.

Remaining Windows folders: android/platform-tools (ADB) and gts9-active/
gts9-stock, gts9-test263 (baseline/rescue), gts9-test292 (current candidate/rollback).
No unrelated apps/files/WSL virtual disk were removed or modified. CurrentTest292
rollback was completed before any current files could be considered for cleanup.
The largest D allocation is the approximately187GiB WSL VHD; no online/offline
VHD compaction, WSL shutdown or speculative archive deletion was performed.

Build and host regression executed:false: storage-only operation, no source,
kernel/config/DT/charging/USB/routing change. Actual filesystem/hash/module-payload
validation passed. No Actions/CI. Future rounds should retain only the active
Windows package/rescue files; remove obsolete duplicates after raw evidence is
archived and WSL source/artifact identity is verified.
