# Test400 — complete Fedora ADSP pair boots; SSC remains absent

One candidate boot `3ff4d010-adab-48b2-b34d-0bde9a50b472` tested the complete
same-model Fedora ADSP/ADSP-DTB firmware pair after registration commit
`a615b7951089766113f682d5a690b0fa4bae9a77` was pushed to `origin/test`.
All 52 firmware files came from one qualified release; 19 differed in bytes.
The matched vendor image SHA-256 is
`21d289fd4e76ebcf2621267a6259c65449c4e9e262e62e43ad80bc61e3330082`.
Kernel/config/notes/DTB, 181 modules, three PD maps, the other 276 assets,
calibration, daemon/library and sensor→root startup order stayed unchanged.
Only vendor_boot was written; boot and modules were not replaced.

The initial read-only preflight rejected the incorrect assumption that the
original 52 firmware files existed in rootfs. The accepted baseline actually
had all 52 absent, including the sm8550 leaf directory. That failed preflight
is retained; it made no device changes. Explicit absent-rootfs transaction
qualification and a fresh full preflight preceded registration and deployment.
The default present-files/full-backup path was not weakened.

TWRP installation passed the actual kernel/root/PID/machine admission and
temporary read-only proc bind. The schema2 transaction created all 52 files
offline; the unchanged assets installer created the remaining 276 owned files.
No remoteproc or Debian service started during this recovery transaction.
ADSP subsequently ran with the complete Fedora pair, without detected
authentication/crash or new severe kernel faults. This is a physical boot
observation, not an independent cryptographic authentication audit.

Both PDR snapshots returned UP across two standard notifier cycles. The
registered 30-second window lasted 33.986 seconds through final collection.
Both RPC units remained active. All 35 observed config metadata checks and
178 registry-content sessions passed. All 220 directory replies, including
two EOF replies, were initialized. The one known missing oemconfig open
returned acknowledged status69. Whole-reference metadata/content/readdir
coverage was complete. These counts are observed results, not requirements
inherited from the stock-firmware experiment; callback success does not prove
DSP parsing or SSC publication.

The complete native trace contains 22 records: five ADSP SMP2P and 17 ADSP
GLINK records, with agreement across raw/header/host-derived facts and all
eight CPU zero-loss counters. On CPU7, native negotiation with feature1
occurred at 0.567258s; slave-kernel notifications were 0/0, 2/2, 6/6, 6/6 at
0.640132, 0.641181, 0.655328 and 0.701218s. Local timestamps do not establish
cross-CPU causality. No SSR-ack event was captured; its absence is not proof
of failure, and unconfigured remote entries were not inventoried.

**SSC service400 remained absent. No accelerometer sample was obtained and
automatic rotation was not tested. Sensor acceptance failed.** The complete
Fedora firmware substitution did not restore SSC within this bounded window.
It does not prove that firmware can never contribute or establish the root
cause of all earlier failures. No unchanged replay was performed.

Mandatory restoration completed. The 276 owned assets and nine overlay files
were restored/removed; the transaction restored the original absence of all
52 firmware files and removed its owned empty firmware directory. Its terminal
ledger was archived before verified backup/scratch cleanup. Original370 vendor
was restored and read back. Return boot
`9bb51abd-1096-4580-b6be-3844d4b112e8` was uniquely attributed; all five
partitions, 181 module hashes, exact config/notes and full rootfs absence passed.
The 20.186-second return window passed with normal GNOME/GDM, palm handling,
ADB, device NCM and sshd, no failed units or detected new severe kernel fault.
ADSP returned to its baseline offline state. Final recorded battery was 100%,
32.7°C, VBAT4.446V within the registered 4.45V passive observation bound.
The 4.44V float policy was unchanged; PPS, charge pump and DCC stayed OFF.
Install and discovery wrappers both exited0; this means the registered
experiment and restoration completed, not that sensors work.

Before deployment, 46 affected scope/runtime tests passed with zero skips;
94 component tests were reused. Result-only host tests executed:false, with
no kernel rebuild, full regression, routing change or GitHub Actions.
The registration seal is unchanged; new raw journals, trace, callbacks,
transaction/partition transcripts and summaries have a separate result seal.
36 Windows staging files were individually hash-verified and deleted; the
ADB tool folder remains. Retention is Test391–Test400. Current370 runtime,
399 stock-firmware comparison provider and 400 comparison image have explicit
consumers; no expired image was moved into an archive to evade retention.

Next work should compare remaining SSC initialization/publication prerequisites
against the same-model working implementation and the captured callback bytes.
Native negotiation, complete firmware substitution and callback transport are
now observed independently; repeating this unchanged flash is not the next
experiment. Sensor bring-up and automatic rotation remain unfinished.
