# Test 043 — DDIC sleep/reset retry does not recover first enable

Source ecba066 (panel change aede820), boot only. Validated bundle and
per-partition readback; pretest boot-chain backups verified off-device.
Initial validator attempt exited on a cpio/awk SIGPIPE, before any write;
the validator was fixed and rerun successfully before flashing.
Recovery plan: restore the pretest boot in TWRP; recovery/vbmeta unchanged.

IDs are zero at 5.586 and 5.880 s despite the sleep/reset retry. Only the
full framebuffer blank cycle recovers 80 00 04 at 8.486 s. Retry is ineffective
and increases latency, so it will be removed. This does not isolate which
part of the full modeset teardown is essential. No owner visual verdict yet.
USB console and checksummed SD report worked; final state TWRP through BCB.
Raw recovery last_kmsg/pstore availability recorded, not used as mainline proof.
