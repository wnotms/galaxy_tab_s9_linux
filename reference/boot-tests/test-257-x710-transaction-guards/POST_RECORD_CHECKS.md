# Test257 post-record host infrastructure follow-up

Result commit260133f0 built successfully and passed the full artifact/config/DT/
protected-source audit. Its changed host rerun was interrupted, not passed:
an existing minimal-rootfs fixture's global sync waited over5minutes for a WSL
Windows filesystem reply. Syncing the Linux test filesystem alone completed.
Preserve the interrupted raw run separately; the qualified31ca86ca results and
their original36-file evidence seal must remain unchanged.

Plan: restrict sync ONLY inside the temporary boot-record host fixtures to the
filesystem containing their records, using real sync -f. Keep both pre-rename
and post-rename flushes, all record/atomicity assertions and all retained tests.
Bound subprocess waits so another host fault fails rather than hangs. Do not
change deployed boot/rootfs scripts, drivers, configurations or device state.
Test the wrapper's actual argv/barriers and rejection of unexpected sync args.
The first repair rerun also exposed the panel-recovery fixture's indirect call
to the record writer. Preserve that interrupted run too; include this caller in
the same scoped environment. Original script behavior/assertions remain intact.
The next rerun found the recovery-layout test syncing a regular temporary
misc.img globally. Apply the same real syncfs scope there, preserving its full
byte-for-byte/tail-preservation/readback checks. No partition access occurs.
Run focused/changed/full host checks, commit separately, then repeat the required
immutable build, full host and config/DT/protected-source review before pushing.

This infrastructure repair does not qualify physical durability or charging
protection. Active PPS/direct remains NOT READY. No device access or deployment.

## Repair results

Focused66 tests passed in8.871s. Changed1255 passed in103.162s; full1255
passed in83.983s report wall time, zero failures/errors/skips.
All1253 original Test257 IDs remain;2 barrier/environment tests added. The
device boot/rootfs scripts and all kernel sources/DT/config are unchanged.
Post-record validation/summary and a separate hash seal preserve all three
interrupted infrastructure runs plus the successful repair results. No failed
or interrupted run was reclassified as passed. Original36 evidence hashes
remain unchanged. Post-follow-up immutable build/all-host/config/DT/protected
review uses ignored out/kernel-x710-257-sync and out/x710-257-sync-post-*
before push. This repair does not authorize any device action.
