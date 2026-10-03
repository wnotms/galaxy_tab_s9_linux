# Obsolete kernel build cleanup — 2026-10-03

The owner requested cleanup of obsolete kernel build directories, then an
AGENT.md update to reduce future storage use. This removes three superseded
complete Kbuild trees:

- .work/build/linux-out-x710-294-passive
- .work/build/linux-out-x710-295-passive
- .work/build/linux-out-x710-296-passive

These trees held 58,665 file/symlink entries and 13.77 GiB of allocated file data.
8,490 necessary debug/config/symbol/module/generated inputs were compressed into
three local .work/host-storage-cleanup/2026-10-03-build-reclaim/*-debug-inputs.tar.gz
archives, totalling 807.07 MiB. Each archive member was checked against its original
SHA-256 or symlink target before deletion and again afterward. Net removed file
allocation is 12.98 GiB; observed Linux available-space increase during the operation
is 13.00 GiB, including directory metadata and any concurrent filesystem activity.

Boot Image/Image.gz contents from these out-of-window rounds were not re-archived;
their original hashes remain in the manifest. Reproducible .o/.a intermediates were
not saved. Debug archives are not complete build trees or valid module providers:
reconstruct old kernels from the recorded source, config and toolchain if needed.
Formal out/ artifacts, raw reference evidence and old seals remain.

The retained complete build list and current purposes are:

| Directory suffix | Purpose |
| --- | --- |
| linux-out | Default build / DT-provider audit |
| linux-out-x710-263-passive | Registered Test300 rollback baseline |
| linux-out-x710-272-passive | Frozen fresh-observer provider referenced by script |
| linux-out-x710-290-passive | Frozen passive-observer provider referenced by script |
| linux-out-x710-299-passive | Accepted production baseline |
| linux-out-x710-302-passive | Qualified separate TCPM profile / Test308 cache parent |
| linux-out-x710-303-policy | Qualified separate PPS consumer profile |
| linux-out-x710-305-adc-condition | Qualified diagnostic candidate / pending Test306 |
| linux-out-x710-308-passive | Current unfinished ordinary recovery build |

The list records current consumers and does not grant permanent retention.
Source worktrees and ccache remain. 46,417 existing artifact/evidence/provider
files were SHA-256 verified unchanged. In-progress Test308 evidence is outside
this protected snapshot; its current build identity files were included and were
unchanged. Existing uncommitted Test308 source/tests are outside this operation.

Online WSL root-filesystem TRIM completed. Its 815.8 GiB output is a logical discard
range, not extra reclaimed space. Measured D: available space changed from 7.10 GiB
to 17.96 GiB, an observed increase of 10.86 GiB. Windows free-space changes can differ
from Linux file allocation because of sparse VHD allocation and concurrent host
activity; no WSL shutdown or offline VHD compaction was performed.

build-manifest.json.gz records every removed tree entry and retained archive input;
protected-before.json.gz records checked artifact/provider hashes;
manifest-archives.json identifies both manifest files; validation.json records
checks and host-space measurements. cleanup-executed.py is a one-time execution
record, not an instruction to rerun it after its targets have been removed.

AGENT.md now requires reuse of compatible incremental caches, consumer-based
retention of full trees, removal of obsolete temporary copies at each round end,
compressed and deduplicated necessary debug inputs, bounded shared ccache, and
checks of both Linux and Windows space. The existing ten-round image rule remains.
Kernel build, host regression, Actions/CI and device commands executed: false;
validation consists of archive/file hashes, deletion boundaries and the prose diff.
