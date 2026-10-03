# SM5440 active supervisor foundation

Implemented the actual current/fault/ADC monitor chain with native facts/source
PPS identity and budget gates, unchanged100ms deadline, new real one-shot data,
exact625uA current comparison and checked hardware watchdog service. First
anomaly invokes real actuator OFF/readback/owned cleanup before ADC cleanup.
Pump/ADC uncertainty, first operation and both cleanup errors remain separate;
terminal calls cannot retry OFF or re-enable. No local cleanup result authorizes
PPS exit/fixed restoration or SM5714 lease release without new source evidence.

Managed conversion now exposes raw MEASURED before cleanup with valid=false,
so one-LSB IBUS overflow can stop before housekeeping. Managed cleanup returns
immediately on its first error for OFF priority; standalone automatic cleanup
semantics remain. Changed converter source is requalified here, not covered by
its previous frozen foundation build.

76 affected actual-C tests PASS in 1.668s, no failures/errors/skips.
Six real C components are linked into the new faulting-bus harness. It first
performs actual settings/WDT/admitted ON operations on a mock, then tests new
measurements and actual equal-value WDT writes, two cycles, source/mode/APDO
changes, missing facts, software-OCP refusal, stale/native-clock time, exact
current/voltage/VBAT/die trip, settings drift, PM/detach, every bus error,
persistent loss, current-trip cleanup fault and OFF-before-ADC-cleanup order.
Mocks do not qualify device OCP or current cutoff.

Initial24 assertion failures required every single bus error to yield a fully
quiesced converter. Corrected assertions require unknown/failed cleanup to
remain owned and block quiescence, with first error/no retry retained. A foreign
enabled ADC is not adopted or declared OFF. Original failed output retained.

ARM64 two unlinked objects W=1/sparse PASS in 4.898s.
No changed-helper warning; existing upstream vDSO declaration warning retained.
Six current provider hashes,98 Test317 sealed inputs/nine formal artifacts
exact; config/DTB differences empty. No Image/modules relink, Kbuild/probe/worker,
full host run, Actions, hardware pump/PPS/current change or new test number.

Full port remains NOT READY: physical100ms ADC/current calibration/cutoff, native
live facts/adapter/PM scheduling, post-ON acceptance, refresh pause/resume and
owned PPS/fixed fallback still need integration and staged hardware acceptance.
Current Test317 installed diagnostic still needs capture and unconditional exact
accepted311 rollback; unavailable transports do not imply CPU failure or PASS.
See docs/SM5440_ACTIVE_SUPERVISOR.md and raw host/static/source evidence.
