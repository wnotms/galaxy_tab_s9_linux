# Selective Kbuild intermediate cleanup (2026-10-03)

Owner request: continue cleaning `.work/build` after the earlier removal of
obsolete build directories and porting leftovers.

Removed 81,658 files with 28,974,915,584 allocated bytes (26.99 GiB).
`.work/build` decreased from 44.69 GiB to 17.71 GiB. All 330,078 surviving
build/source/artifact/evidence files and symlinks passed the complete before/after
file-set and SHA-256 comparison. The compressed manifests occupy about 19 MiB;
no intermediate contents were archived.

Seven retained output directories were reduced by removing regenerable object
files, static archives, temporary vmlinux link products, `vmlinux.unstripped`,
and the command/dependency records associated with those removed files:

| Directory | Reason to retain final outputs and preparation inputs |
| --- | --- |
| `linux-out` | Default DT-provider audit and default profile |
| `linux-out-x710-263-passive` | Registered Test300 rollback baseline |
| `linux-out-x710-272-passive` | Fresh-observer script's frozen provider inputs |
| `linux-out-x710-290-passive` | Passive-observer script's frozen provider inputs |
| `linux-out-x710-299-passive` | Accepted production baseline |
| `linux-out-x710-303-policy` | Separate qualified PPS consumer profile |
| `linux-out-x710-305-adc-condition` | Diagnostic candidate pending Test306 |

`linux-out-x710-308-passive` (unfinished current recovery work) and
`linux-out-x710-302-passive` (its retained incremental baseline) were left
complete. Both prepared source worktrees and both external observer staging
directories remain.

The reduced directories retain their original resolved configuration, final
`vmlinux` including DWARF debug information and BTF, `System.map`, symbol CRC
tables, kernel release, module metadata, `.ko` files, DTBs, generated headers,
source links, `.module-common.o`, and all files under `scripts/` and `tools/`.
The default DT audit's `modules.builtin.modinfo` remains. The pinned Kbuild
external-module path reads `Module.symvers` and final `vmlinux`; it does not
need the deleted in-tree link objects. No build or observer command was run to
requalify a historical source/profile: the scripts' source identity guards
still apply, and preservation alone is not a new qualification.

These seven directories are no longer complete incremental caches for building
the entire kernel. A future whole-kernel build will regenerate the missing
objects and links. Match the recorded source, configuration, toolchain and
profile before reuse; do not overwrite a frozen provider with current sources
and then continue treating it as an old qualified provider.

No redundant archive of the intermediates was created. The authoritative
deletion manifest records every removed file's path, size, allocated bytes,
SHA-256, inode and modification time. Every candidate was a regular file with
one link, inside the explicit seven-directory allowlist. The operation refused
active build processes, source trees and symlinks, and checked the selection and
metadata again before deletion. The script removed individual files only.

`protected-before.json.gz` records all surviving files and symlinks in
`.work/build`, `out/` and `reference/`, along with current modified/untracked
source and tests. After removal, their complete file set and contents were
compared with the snapshot. Test308's pre-existing changes were retained.

See `validation.json` for actual counts, released bytes and filesystem readings;
`deleted-files.json.gz` for the removed intermediates;
`manifest-archives.json` for the manifests' own SHA-256 values;
and `cleanup-executed.py` for the exact one-time operation. Online TRIM and the
final Linux/Windows space measurements are recorded separately.

After online TRIM and before committing the records, Linux had 119.72 GiB used
and 835.92 GiB available; D: had 53.98 GiB available (81% used). The repository
occupied 31.12 GiB. Compared with the operation's initial readings, available
space increased by about 26.96 GiB on Linux and 20.80 GiB on D:. The 70.2 GiB
reported by `fstrim` describes discarded ranges, not additional recovered space;
the host's actual free-space change is measured separately. No WSL shutdown or
offline VHD compaction was performed.

Kernel build, host regression, Actions/CI and device commands executed: false.
Validation consists of the actual file-set/hash checks, required-input and ELF
section checks, process/deletion guards and documentation review.
