# Exact absent-rootfs firmware restoration

The first read-only Test400 draft preflight stopped before mutation because its
new integration assumed that52 original ADSP/DTB files existed in Debian.
They do not. The same accepted370 return boot is still1f8302ac…; rootfs
`usr/lib/firmware/qcom/sm8550` itself is absent. Test399's actual installer reports
328 files/328 owned, and its accepted rollback removed those temporary files.
The qualified399 early ramdisk provided the complete boot firmware pair. There
is no evidence of an unexpected firmware deletion or production kernel change.
Raw first-preflight paths/source pins/error and accepted399 ownership evidence
are retained. This was a new host-install premise failure, not a physical
candidate failure; no recovery, firmware/partition write or reboot occurred.

Extend the independent transaction with explicit `--original-presence absent`.
It requires **all52 absent**, rejects even one unexpectedly present original,
and never automatically downgrades a present-original requirement. Default
present mode still requires all52 qualified originals, full backup/fsync and
exact byte/mode/root ownership/nanosecondmtime restoration. A present-original
ledger cannot be restored with absent mode to delete its files.

Schema2 durably records original presence, each before-state (`null` only in
explicit absent mode), complete pinned candidate metadata, pending/write phase,
and creation ownership of the one firmware leaf directory. The existing qcom
parent must exist; no broad directory creation. Before the first replacement,
freeze every before-state and back up every actually present original. Absent
mode has no original bytes to back up or fabricate. Install all52 files from
the complete qualified candidate; reject any unrecognized root state.

Recovery validates every current file against its registered before/after state
before any restoration. Only recognized newly created files are unlinked for
absent originals. Unexpected bytes, symlinks, ownership or unrelated directory
entries stop. Remove the newly created empty firmware leaf with `rmdir`, never
recursive removal. Terminal ledger/qualified cleanup still apply; original
absence is checked again after normal return. Partial creation is recoverable.

33 transaction tests PASS (26 existing +7 absent-state); final dependency run
and exact source pins are in HOST_TESTS/QUALIFICATION. Tests cover absent-mode
creation/removal, rejection of present/absent mismatches, partial write failure,
unknown content before deletion, cross-mode ledger denial and retention of
unrelated directory files. Host ownership/kernel permission seams remain mocked;
this is not a physical recovery proc-bind qualification. Old present-mode and
assets-installer tests remain unchanged in meaning and are not skipped.

The complete candidate firmware/early ramdisk bytes, DTB, headers and AVB artifact
remain unchanged; affected package tests verify that existing output. No kernel
build/full routing regression/Actions. No kernel/config/DT/modules/USB/charging/
input change, PPS/pump/DCC OFF,4.44V float/fail-closed safety unchanged.

Next finish the independent400 registration with the explicit rootfs absence
gate and schema2 helper, fresh read-only preflight, transfer/hash boundaries,
one30s early boot and mandatory exact370/absence/normal-GNOME return. Do not reuse
the failed present-files preflight as a passing admission. Test400 physical
execution is still unperformed; SSC/samples/rotation remain unfinished.
