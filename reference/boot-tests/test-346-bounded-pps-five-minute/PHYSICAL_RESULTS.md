# Test346 — closed before pump activation, accepted331 restored

**CLOSED_MANUAL_HANDOFF_TIMEOUT_NO_ACTIVATION_RESTORED331.** The five-minute charging acceptance was not performed. This is a workflow stop, not a detected CPU/pump/charging fault or a five-minute pass. Original STOP, failed host trust probe and all raw evidence are preserved.

## Attempt and terminal evidence

Fresh owner authorization covered one300s attempt at unchanged hardware1700mA/PPS+raw1800mA.683bdd12 was owner-attributed manual power-off/restart. Accepted331 PCpreflight passed, followed by one paired deployment. Candidate0ad61ab7 config51/notes10/allfive/181/300000sysfs/roles/rescue/unique history passed. Initial worker was drained; pumpOFF/unbound before cable handoff.

Original guardianPID1717 reached its registered900s manual-handoff limit while OFF/unbound. Terminal finished marker and STOP summary show the timeout, no cleanup error; PID absent, activation_started and activate.json absent,0active frames/no one-shot entry. It was not restarted/rebound. An owner connection reply arrived afterward; sameboot physical read verifiedOFF/unbound/fixed9 ordinary state at68%29.1C. Full kernel journal showed no detected CPU fault/new severe suspect. No PPS/pump test occurred.

## Restoration

Owner reconnected PC. The registered recovery procedure restored exact accepted331boot025ebea4 and original181 modules; allfive partition readbacks matched, normalboot a96de8c0 is uniquely attributed. Final config51ba6a9c/notes03c9c46e, DCCabsence, pumpOFF, ADB/deviceNCM/authenticatedWiFi10.175.236.117, journal and failed-unit/Windows gates passed. Final69%4.101V30.1C, ordinary PCcharging with1.8A input limit. rollback_required=false. Detailed hashes, full journals, command status and source timestamps are retained in rollback-install/final-acceptance/raw guardian evidence.

## Limits and next action

The registered series is terminal and must not be replayed. Full charging port remainsNOT_READY; no300s/20min/highercurrent/45W/calibration/hard-realtime acceptance is inferred. Any new round must have a new registration and fresh authorization/identity; adjust the manual-handoff workflow so an intentional pause cannot consume an already-running guardian wait. Prefer starting the guard after fresh C1 connection confirmation while preparation remains OFF/unbound; review/test that change independently without weakening current/native/cleanup gates. No new candidate or round is created by this closure.

Host tests/build executed:false for evidence-only closure. Reuse the exact existing32affected host tests,79actual-C/kernelbuild/W1+sparse qualification. No Actions, CI, newkernel/config/DTS/SM5714/TCPM/USB/adbd/rootfs changes, higher current or second activation.
