# Method-28 reply initialization — offline qualified

Test397's attributed, complete return-frame archive has 220 successful method-28
replies. EOF sequence954 contains 15 nonzero bytes beyond the empty name's NUL,
including a fragment of a previous directory name. The mapped filesystem EOF
path writes only name[0]; apps_std previously left the rest of its malloc-backed
264-byte reply untouched. This is a demonstrated reply-initialization defect,
not a demonstrated reason for the missing SSC400 service.

An independent profile over the exact Test397 retained-listener source changes
only hexagonrpcd/apps_std.c. Method28 checks its eight-byte input handle and
264-byte output before accessing them, then zeros the complete reply before
the filesystem callback. Its name, status, EOF, existing inode0 convention,
method definition and filesystem operation remain unchanged. The inode0/native
inode discrepancy is deliberately not mixed into this experiment. Qualcomm
a56e9d4 apps_std implementation/IDL supplies the ABI reference; this patch is
local deterministic initialization, not a claim to reproduce every vendor field.

87 affected host tests PASS,0 skips:14 new callback/evidence/profile tests and
73 retained listener/open-error/return regressions. The harness includes the
actual original/patched C callback, runs with native UBSan, demonstrates old EOF
and padding residue, verifies normal/max names, rejects malformed buffers before
FS calls, checks errors/512 repeated EOFs and output canaries. Strict evidence
checks reject the actual397 residue, incomplete frames, missing EOF, bad lengths,
status, hex, fields, tail and padding. No implementation-copy tests.

Same pinned networkless ARM64 builder, release Meson/four jobs: daemon build and
two upstream tests PASS;16 original/final callback ARM64/QEMU cases PASS. New
daemon SHA78b356c96afb1f7ff75280810d9db88386b7b2d10ad4d71d818ab5f261752299;
companion library remains exactly1be44d2f. One pre-existing apps_mem.c printf
format warning is retained in the complete build log; no unrelated cleanup.

No kernel rebuild/full host run/Actions/device mutation, firmware/registry
rewriting or charging change. PPS/pump/DCC remain OFF. Automatic rotation is
unfinished. A separately registered short startup comparison is required before
deployment; it must verify deterministic replies separately from SSC publication
and restore the accepted Test370 GNOME baseline after the single attempt.
