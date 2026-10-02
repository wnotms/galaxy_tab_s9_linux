# Additional project storage reclaim — 2026-10-02

Owner requested cleanup of unused test records/images because D: was low.
Started from test HEAD 8fbd3738 with a clean tree. Previous Windows staging
cleanup dacba779 already removed 326 files/~5.39GiB; it was not repeated.

This operation removed 7 enumerated obsolete Kbuild intermediate trees
(129514intermediate files) and 13 clean detached project worktrees, freeing
36.93 GiB of allocated Linux file contents. D: measured free space rose
from6.32GiB to37.28GiB, an observed increase
of 30.95 GiB. Guest allocation totals and Windows free-space change differ;
we report measured Windows space rather than claiming every guest byte reclaimed.

All 43186 files in out/ and pre-existing reference/ were SHA-256 checked before
and after deletion, unchanged. Historical results, raw journals, seals, final
images/config/DTBs/module archives and rollback packages were not deleted.
21,262 build inputs (vmlinux debug symbols, all .ko/.dtb files, configs, generated
headers, symbol/export metadata, System.map, Image/Image.gz) were moved on the
same filesystem into .work/host-storage-cleanup/2026-10-02-reclaim/
retained-build-inputs and hash-verified after relocation. This keeps old debug
information while discarding reproducible .o/.a and other Kbuild intermediates.
Compressed manifests contain every kept file/hash and old/new path; archive
hashes and uncompressed identities are recorded in manifest-archives.json.

Removed intermediate directories:

- linux-out-container
- linux-out-poweroff-trace
- linux-out-sm5714-stage2
- linux-out-x710-charging
- linux-out-x710-265-policy
- linux-out-x710-266-passive
- linux-out-x710-269-policy

Retained .work/build/linux-out (DT-provider audit default), linux-out-x710-263-
passive (installed rollback), linux-out-x710-272-passive and linux-out-x710-290-
passive (qualified observer providers), all mainline source trees, ccache and
final out/ packages. Old removed build directories are no longer complete
incremental-build inputs: reconstruct them with the standard build workflow if
needed; use saved symbols/artifacts for historical analysis. Do not point an
external observer build at a partial retained-input directory.

The 13 source worktrees were clean, removed using git worktree remove without
--force; every corresponding commit object was verified present afterward.
Their historical revisions remain recoverable through Git. No branch, tag or
committed source/history was deleted. Worktree-removals.json identifies them.

Windows android/platform-tools and gts9-active/{gts9-stock,gts9-test263,
gts9-test292} remain. Other Windows apps, personal files, stock firmware and
rescue files were untouched. Ran online fstrim twice using the existing WSL
root account; sparse disk reclamation succeeded without WSL shutdown, offline
VHD compaction or stopping this session. Trim output describes logical discard
ranges, not extra measured Windows free space.

No tablet commands/flash/reboot/partition/module/rootfs changes; no charging
or USB policy change. Storage-only build/host regression executed:false.
Actual syntax, artifact/hash, archive, retained-input and Git revision checks
passed. No Actions/CI. cleanup-executed.py is an archival record of a one-time
operation, not an instruction to rerun it against now-removed directories.
