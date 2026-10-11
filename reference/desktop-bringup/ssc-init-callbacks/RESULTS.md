# Registry initialization observation — offline qualified

Test401 produced real cache/config work, but its original observer exhausted1MiB
at seq1379. Source-bound error decoding also establishes that the original
“missing buffer header” occurred earlier at seq1026: an exact ro.revision request
to unsupported handle0xffffffff received status20 with **zero encoded output**.
Fedora's unchanged listener returns that error before allocating an output and
continues. Do not invent a200-byte output, remove the status or rewrite401.

The frozen Fedora-derived localctl.c has only the registered apps_remotectl/
apps_std/apps_mem list and explicitly returns-5 for unknown sns_registry. Its
ordinary listener continues with apps_std file callbacks. An actual C/UBSan
harness verifies unknown sns_registry→handle0/error-5/255 zeroed text bytes,
registered apps_std→handle1/success, and unsupported property→status20/nonfatal/
NULL output. The actual listener encoder/ioctl boundary is exercised with a
private stub, verifying zero returned bytes and continued input decoding.
These are protocol negatives, not functioning new interfaces or an SSC claim.

An independent parser recognizes only the exact ro.revision/request shape and
status20/empty error reply. Any other missing output, changed status/name/scalar/
capacity/transport/context, malformed frame, observer limit, missing/restarted
producer or source attribution error still fails. A separate classifier permits
at most the Test401 observed six exact SNS/property adjacent acknowledged pairs
from the sensor process. Unpaired/unexpected replies remain faults. The future
runner must explicitly preserve all negative statuses and still require complete
framing; no arbitrary-5 waiver. Fedora itself lacks sns_registry, so no guessed
implementation or Samsung userspace framework is added.

The independent isolated-cache replay changes only its parser buddy and one
write leaf: **temp.json** inside the copied sensors prefix. Test401 requested
/mnt/vendor/persist/sensors/registry/registry/../temp.json, then writes/closes/
renames it into registry members. The existing exact mapping normalizes this to
sensors/temp.json; a path with only one registry component escapes the mapping
and remains forbidden. Config/identity/library/arbitrary root-temp/outside writes
still fail. All original snapshot/bounds/quiescence/inode/byte/metadata/ownership/
capacity/acknowledgement/mutable-close protections are unchanged.

The new daemon profile changes only its test-only observer header. Default
off/explicitopt-in/default1MiB text output is identical to frozenv2. An additional
exact environment HEXAGONRPC_RETURN_TRACE_BUDGET=8388608 permits8MiB maximum,
without an8MiB allocation or a larger8192-byte frame. Any other budget emits one
explicit LIMIT and stops recording. It never changes protocol/status/buffers/
FDs/filesystem/firmware/kernel/registry/charging/USB or starts a device service.

48 scoped host tests passed, zero skips/errors/failures: actual observer limit
at8MiB/default output equivalence/invalid budgets/transport/frame/input canaries/
UBSan, real localctl and listener boundary, exact negative pairs/count bounds,
actual401 partial replay (still fails budget), exact400 parser equivalence and
28 unchanged replay safety cases against the independent profile. Initial fixture
errors (wrong single-registry temp path and a nonexistent helper name) are saved;
corrected to actual logged double-registry path/source, no historical test change.

Same pinned networkless ARM64 builder completed in3.661s.15 actual listener/
localctl ARM64/QEMU cases and2 upstream tests passed. Daemon SHAaea9072d…;
companion library SHA1be44d2f… remains exact. The pre-existing apps_mem printf
warning is retained; no unrelated cleanup. Repeated synthetic host budget logs
are compressed once with original byte hashes, not duplicated as large raw logs.

Historical parsers/tests/source profiles and Test401 verdict remain unchanged.
No kernel build/full suite/routing/Actions/device command. Next independently
register one short initialization observation with this exact observer/classifier,
complete raw frames and before/after snapshots, then mandatory normal370 return.
No unchanged401 replay or sensor/automatic-rotation acceptance yet.
