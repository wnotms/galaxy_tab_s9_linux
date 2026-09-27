# Test 230 results

Completed: candidate built, flashed, booted, sampled and rolled back. Live
instrument and byte-bound validation passed. **Persistence through the tested
Debian → TWRP → Debian chain did not pass.** No wedge series was started.
The original README is the immutable preregistration; PLAN-ADDENDUM.md records
the recovery-backend clarification made before flashing.

## Flash and live observation

Only boot and vendor_boot were written, with candidate full-partition hashes:

* boot: 4bd54708b26fd1453af97db19be83bfcc9f5b799225f636f73e0bf4d3191908b
* vendor_boot: 8c5948464cab0ee489c37d7eaca9dfedef7db840c9c031a06ec0980a31a66b33

Read-back matched both. The other three tracked boot-chain partitions remained
byte-identical to preflight. Candidate source was committed as 7fcc618; the
exact vmlinux and System.map were retained under out/kernel-lastactivity with
hashes in symbol-artifacts.txt, before any later build could replace them.

Candidate boot: 0669a95d-6e2f-4885-825f-50763e7136e2. The retained journal boot
list identifies this as the first Debian boot after the preflight anchor.
READY appeared at 0.103705 seconds with capture ID
6356217b-3e25-4876-9942-c6e704b833fe. Runtime watchdog, soft_watchdog,
softlockup_panic and panic were 1/1/1/10; the helper report belongs to this boot.
Systemctl reported zero failed units. No positive RCU/NMI non-response/panic/
soft-lockup/workqueue-lockup signature appears in the retained candidate log.
This is a healthy calibration observation, not a 150-second wedge-run verdict.

The manual snapshot was requested at uptime 69.32 seconds:

* 58 complete marker lines, 48 event cells, eight valid CPU snapshots.
* 6,245 bytes of marker text; 7,811 raw captured bytes including dmesg prefixes
  and ADB CRLF framing. This is well below the corrected 393,204-byte allowance.
* CPU 6/7 reported respectively 4/2 nested writer drops; other CPUs reported 0.
  The counters are explicit evidence loss, not a reason to infer missing IPIs.
* A second write to the dump knob exited 1 with I/O error and emitted no second
  snapshot, as expected for once-per-boot capture.
* Snapshot marker SHA-256:
  b37e1c598bbe5fbb581b9dc3f0b4bff893105f0c6eeac9778f1a03e00e922515.

The real snapshot passed scripts/lastactivity-evidence.py. All positive records
remain last-observed cells; they do not provide a complete execution interval,
prove delivery/non-delivery, identify a root cause, or test the RCU-triggered
dump path. That automatic path remains compiled but unexercised in this trial.

## Persistence outcome

The validated BCB helper entered TWRP. Recovery had no pstore files, so no
matching snapshot could be read there. Recovery dmesg/last_kmsg are archived
under recovery-after-snapshot and are not reclassified as mainline evidence.

Following the preregistered addendum, the first restored Debian boot was also
checked: 8f6fa295-4a50-48fa-9f06-bf7133a93135. Its systemd-pstore service skipped
archival because /sys/fs/pstore was empty. The files under /var/lib/systemd/pstore
were old: the compressed record's full hash matches test-229's preflight copy;
the console text matches its preflight copy after normalizing the old ADB CRLF
transport. Neither is evidence from this trial. The compressed file was not
decoded successfully with a plain zlib wrapper, and is identified as stale by
its exact old hash, not by searching compressed bytes for a marker.

The live and journal copies establish capture, but do not establish reboot
persistence. We have not established whether the snapshot was never stored,
overwritten by a boot stage, or inaccessible on this path. Do not attribute the
failure specifically to TWRP or the bootloader from absence alone.

## Rollback and next test

Production boot/vendor_boot were restored from dedicated, hash-verified backups.
All five full-partition hashes then matched preflight, including unchanged
init_boot, dtbo and vbmeta. The first restored Debian boot answered systemctl
with zero failed units; its retained kernel journal has no positive stall/panic
signature. The diagnostic flag is absent and the production profile is restored.

Next isolate the reboot path: use the same bounded candidate for **one healthy
direct Debian → Debian warm-reboot persistence calibration**, without entering
TWRP between snapshot and retrieval. Preserve the source capture ID and recover
matching pstore by that identity; save subsequent boot IDs to detect unexpected
recovery. This distinguishes the ordinary reboot path from the recovery chain
used here. A fit in bytes is already proven for this small snapshot, but another
wedge trial is premature until the actual recovery path retains the evidence.
Do not change reserved memory or claim the CPU non-response is repaired.
