# Porting leftovers cleanup — 2026-10-03

The owner requested continued removal of unused porting files. This operation
removes obsolete prepared sources and redundant expansions, retaining original
evidence and byte-verified reconstruction material. Current Test308 source/tests,
production and rollback artifacts, default install modules, frozen observer
providers and recent candidate module directories remain.

Removed or repacked:

| Category | Count | Preservation / verification |
| --- | ---: | --- |
| Obsolete prepared kernel source worktrees | 3 | Pinned commit, binary tracked diff, all untracked files; reconstructed tracked content verified in an isolated Git index |
| Old expanded module directories | 28 | Complete regular-file sets matched to retained archives; missing packages were compressed and member-verified first |
| adbd mktemp source/build jobs | 5 | Content-identical files map to retained canonical source; every differing file is archived; source tarballs match retained cache |
| Historical ELF symbols and uncompressed module tar files | 17 | Gzip copies restore exact original SHA-256; identical content shares a retained compressed copy |
| Previous uncompressed debug-retention trees | 7 | Every regular file/symlink is preserved and verified in compressed archives |
| Duplicate module tar files in old D-drive migration | 3 | Exact original bytes already available in verified compressed copies |
| Obsolete early image-staging directories | 2 | DTB and release metadata saved; boot-image content retired under the ten-round rule, original SHA-256 recorded |

The three removed prepared worktrees are linux-src-container,
linux-src-poweroff-trace and linux-src-sm5714-stage2. Their upstream commit is
still a13c140cc289c0b7b3770bce5b3ad42ab35074aa. No remaining build's source link
points to them. git worktree remove --force was used only after each prepared
tracked overlay was reproduced from that commit and every untracked file was
archived and verified. All worktree revisions remain in Git; the upstream,
default and current charging source trees remain.

Net file allocation reduced by **15.47 GiB**, after subtracting the
**4.26 GiB** of saved reconstruction material and correcting 473,550,848
bytes of duplicate accounting for shared hard links. The two known inode groups
and their original metadata are in manifest.json.gz. The script's own before/after
Linux available-space increases total **15.61 GiB**; filesystem metadata
and concurrent activity can make this differ from file allocation.

Online TRIM completed. D: available space measured **19.05 GiB** at the initial
inspection and **33.20 GiB** afterward. This is a whole-host observation, including
any intervening activity, not a claim that every change was caused by this script.
TRIM's 49.8 GiB message describes discard ranges and is not extra reclaimed space.

41,364 surviving artifact/evidence/current-source/provider files were hash-checked
unchanged before writing the new status documentation. Reconstruction archives
were verified before deletion and afterward. Historical original paths for old
vmlinux, modules.tar, prepared worktrees and raw retained-build-inputs intentionally
no longer exist; their identities and new compressed locations are in the manifest.
Historical scripts need restoration from that mapping before they can use those
paths. Configuration, DTBs, paired module archives, logs and test seals are retained.
No hard links were introduced between immutable packages and mutable build trees.

Local reconstruction data is under:
.work/host-storage-cleanup/2026-10-03-porting-leftovers/

For a prepared source, start with the recorded upstream commit, apply tracked.patch,
then restore untracked.tar.gz into that source tree. For old expanded modules, the
recorded archive gives the original release/prefix; restore and verify the complete
member set before use. Gzip symbol/tar files restore exact original file contents.
Other debug archives use paths relative to their recorded old directory. They are
historical reconstruction data, not ready-to-use live external-module providers.

manifest.json.gz records content mappings, source overlays, module payload sets,
and hard-link accounting. additional-cleanup.json covers migrated duplicate tars
and early image staging. protected-before.json.gz records preserved-file hashes;
manifest-archives.json identifies these records; validation.json includes results
and host-space measurements. cleanup-executed.py and finalize-executed.py are
one-time execution records, not instructions to rerun against removed targets.

AGENT.md now also requires disposal of finished adbd mktemp jobs, verified archival
and Git removal of obsolete prepared worktrees, and removal of old module expansions
after full archive verification. Kernel build, host regression, Actions/CI and
device commands executed: false. Validation is the actual file/archive checks and
reviewed storage-policy documentation.
