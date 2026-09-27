# Test 231: direct warm-reboot snapshot persistence

Pre-registered after test-230, owner request: “继续”, continuing the explicitly
authorized flash/test work (“完成后刷入进行测试”). Source base acf3b01. The
candidate is exactly test-230's validated 0022 last-activity image; no rebuild,
code/config/DTS/voltage change, or new watchdog threshold is part of this test.
Full candidate and rollback hashes were verified again before preparing it.

Question: does one healthy **Debian → Debian direct warm reboot** preserve the
bounded snapshot in pstore, when no TWRP boot intervenes? Test-230's recovery
chain did not yield matching contents; that does not establish which component
lost or failed to expose the data. This trial changes only the recovery path
between the snapshot and its retrieval. It is not a wedge/reliability series.

## Procedure and verdict rule

1. Record healthy production boot ID/journal/pstore state. Enter TWRP with the
   validated BCB helper, TMPDIR=/tmp and ordinary systemctl reboot. Recheck
   device, sizes and all five partition hashes; preserve recovery evidence.
2. Flash the same boot/vendor_boot candidate as test-230. Read back full hashes.
   Do not write init_boot, dtbo, vbmeta or recovery. Existing dedicated rollback
   files must match current production partition hashes before the writes.
3. Boot once, preserving journal boot history and the new boot ID. Verify
   gts9_lastactivity=1, READY/capture ID, watchdog state 1/1/1/10, responsive
   systemd and no positive stall signature. If a real stall occurs first, stop
   the healthy calibration and preserve it; never count a later boot as clean.
4. At >=60 seconds uptime take a manual once-per-boot snapshot, parse all
   BEGIN/CPU/EVENT/END markers and save exact canonical marker lines. Last-event
   cells and nested-drop counters are not complete execution history.
5. Verify BCB empty using the helper's read-only --check, then issue only
   systemctl reboot, without writing recovery BCB or entering TWRP. Record the
   immutable source boot/capture IDs before the request.
6. In the first subsequent Debian boot collect /sys/fs/pstore and
   /var/lib/systemd/pstore plus systemd-pstore journal and complete boot list.
   Verify the observer is the immediate next retained boot, not an unexpected
   recovery. Save its boot ID separately; its new capture ID is not the source.
   Matching source capture ID plus complete, byte-equal canonical snapshot
   markers in a pstore record is a pass for this **healthy direct-reboot path**.
   A journal copy alone is not a pass. Empty/stale/truncated contents or missing
   attribution fail the gate. No inference about exact loss mechanism follows.
7. Archive the result before rollback. Enter TWRP and restore original
   boot/vendor_boot with read-back verification; confirm all five hashes equal
   preflight and return to production Debian. Record actual final state.

No induced panic or wedge series follows automatically, even if this healthy
test passes. Crash-time RCU-triggered snapshot delivery/persistence remains a
separate validation. Normal shutdown may flush data a stuck machine cannot.
Missing-event/root-cause claims remain unsupported by the bounded instrument.

## Starting state

Production Debian boot 8f6fa295-4a50-48fa-9f06-bf7133a93135 remained responsive
at uptime 414.77 seconds, with zero failed units. Existing pstore files are
retained as baseline; do not clear or attribute them to this trial by filename.
Candidate and backup paths/hashes are recorded in backup-and-staging.json;
candidate image hashes and validation are in test-230. Current default
production profile has watchdog/panic disabled, as previously documented.
