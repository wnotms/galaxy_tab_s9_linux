# RPC stat diagnostic qualification

The exact Fedora-pinned hexagonrpc0.4.0 plus its three accepted patches has a
reproducible `apps_std_stat` error-path defect: a successful open followed by
failed fstat leaves the virtual descriptor allocated. Its diagnostic also uses
`-fd` rather than `-ret`. The same C harness returns23 for the original source's
leak and passes against the isolated patch, including1024 consecutive injected
fstat failures. These are host faults, not failures observed on Test378.

The patch closes the temporary descriptor before handling the fstat result,
reports the actual error, rejects zero/null/unterminated path or short/null
output before access, and adds size/mtime to the already verbose success trace.
The96-byte wire layout and all successful metadata values remain unchanged.
In particular the unusual ctime-nanoseconds encoding is preserved: the
[Qualcomm reference implementation](https://github.com/quic/fastrpc/blob/master/src/apps_std_imp.c)
also uses it, and releases the temporary file after fstat failure. There is no
evidence to justify changing that ABI to POSIX seconds.

The separate source profile verifies the complete accepted source tree and the
base manifest/patch hashes before copying. Only `hexagonrpcd/apps_std.c` may
change, to a pinned resulting hash. It never alters `sources.json`, the accepted
prepared tree, Test378 artifacts, installed packages or the tablet. Build input
and copied output source identities were compared exactly after compilation.

ARM64 compilation succeeded in the existing pinned networkless Debian builder;
both upstream Meson tests passed. There is one format warning in unchanged
`apps_mem.c`; none was introduced in the patched callback. The companion shared
library is byte-identical to Test378. Daemon and every staged file hash are in
BUILD.json. The64 affected host tests passed without failures/errors/skips;
shell syntax and Python compilation also passed. No kernel build/full regression
or GitHub Actions ran because kernel inputs and test routing were unchanged.

An independent archive audit found35 cached config entries; each recorded
mtime1640995200 matches its exact X710 config archive member. Sizes, hashes and
per-entry comparisons are retained in REGISTRY_METADATA.json. This excludes a
timestamp mismatch *inside these archive inputs*, not a device extraction error,
DSP cache miss or incomplete sensor initialization. Do not clear/rebuild the
registry based on the old stat-only trace.

The candidate is **compiled and host-tested, not deployed**. It does not qualify
SSC discovery or rotation. Before a separate registered physical attempt, bind
the exact new daemon/library and rollback hashes to that test. Retain the early
ADSP/text gate, one native mapper and both RPC starts, bounded collection and
baseline GNOME restoration. Compare actual returned config size/mtime with this
archive audit and collect the first failed initialization boundary. Do not retry
the unchanged Test378 profile or late-start ADSP on a live GNOME session.

Current accepted device remains Test370. Kernel/config/DTS/modules, charging
limits, PPS/pump/DCC state, USB lifecycle and default graphical boot are untouched.
