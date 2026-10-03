# Historical image cleanup and ten-round retention — 2026-10-03

The owner requested deletion of image backups for resolved issues and a rolling
limit of ten rounds. AGENT.md now makes that rule authoritative over historical
instructions to keep old image copies indefinitely. The current round is Test308;
the retained historical-test window is Test299–Test308, including rounds without
new images. Rollback images count against the round that registers their use.

This cleanup removes 1,170 superseded image files: 825 in out/, 340 in local
.work/ backup/archive folders, and five ignored images in the old Test182 record.
The removed files total 56.41 GiB apparent length and 27.11 GiB allocated content;
many boot bundles were sparse. These are Linux filesystem figures, not a claim
about Windows D: free space or VHD compaction.

The retained image set includes Test299 production, Test301/302/303/305 artifacts,
and the exact Test263 baseline still referenced by the in-window Test300 rollback
record. The original version remains Test263: this is a Test300 rollback package,
not an extra historical Test263 retention slot. A future cleanup must retire it
when its registered use leaves the window or a replacement is accepted. Current
production and original stock rescue files are operational files. No external
Windows staging files are part of this repository cleanup.

manifest.json.gz records every removed path, SHA-256, size and allocated size;
it also records retained image hashes, retained module-archive hashes and the
identity of each non-image file in the scanned folders. validation.json records
absence and preservation checks and the observed Linux free-space change. The
manifest is written before deletion; only its enumerated ignored image paths are
unlinked. Historical SHA256SUMS and test results remain historical evidence;
they can refer to intentionally removed images. The earlier D-drive migration
README has been annotated accordingly.

Verification passed: all 1,170 removed paths are absent; 13 retained images and
44 retained module archives match their pre-cleanup SHA-256 values; 67,218
non-image files retain their original size, inode and modification time. No
tracked file was deleted. Linux available space increased by 29,108,232,192
bytes (27.11 GiB) during deletion; the small difference from allocated content
also includes filesystem metadata and any concurrent filesystem activity.

Source, configuration, DTBs, module files/archives, raw logs, results and old seals
remain. Active build trees, ccache and third-party source test fixtures are outside
this backup cleanup. The ongoing charging/ADC/PPS work is not declared resolved;
older superseded image copies are removed without rewriting its evidence.

Storage/documentation-only operation: kernel build, host regression, Actions/CI
and device commands executed:false. Existing Test308 source/test edits are outside
this commit. Filesystem checks and the documentation diff are the validation for
this operation; no new hardware or regression qualification is claimed.
