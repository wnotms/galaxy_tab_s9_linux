# Test257: offline X710 transaction evidence and monitoring guards

Start test HEAD a3ddd0debd2eb92a98e1ee4174cd476c526cb18c. Purpose: tighten the
existing default-inactive transaction core's source capability, freshness,
current precision and monitor/stop refusal rules. This is not a live adapter or
hardware acceptance. Read docs/SM5440_SOFTWARE_OCP_AUDIT.md before implementation.

No tablet command, flash/reboot/partition/modules/rootfs change, PPS/APDO or pump
activation. No DTS/config/charging-current/float/thermal change. Preserve stock
TCPM, Test253 adbd/Test254 Docker/DCC absence and Stage2 accepted artifacts.
Keep Test256 logs/manifests/results immutable. No GitHub Actions or main merge.

Source design precedes implementation; separate docs/code/results commits.
After each commit build from immutable source, run host checks, compare exact
config/DT/protected files, then push origin/test. Record failures separately.
Final default and policy-offline outputs have embedded config/notes/hashes and
181 paired module-directory files, in distinct ignored out directories.

Host fault tests compile the real core; no deleted/weakened/skipped old tests.
Final all suite with fail-on-skip. Source-offer and temporal safety failures must
refuse ON; active faults must verify OFF before fixed restore, ambiguous OFF
must inhibit fallback. No physical fault injection or dangerous-limit testing.

New images are unaccepted. Software OCP protection latency remains unknown.
Active candidate NOT READY. No rollback is necessary because device state is
not changed; retain stage2-fixed-pd-known-good and accepted Test255 artifact pair.
