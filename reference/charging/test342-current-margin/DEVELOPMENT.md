# Narrow validation

Initial actual-C plus unchanged guardian suites:93 tests PASS in1.526s. Added explicit old1.8A register readback rejection, then reran modified actual-C suite only:58 tests PASS in0.381s; unchanged35 guardian tests retain the preceding qualification. No fullsuite/routing/build integration changes.

Read-only strict WiFi packet confirms same accepted331 boot,77%/4.141V/28.3C/-1.647A, healthGood, USBonline0, direct_charge=N. Packet command exited1 only because331 has no direct_charge_once parameter; raw stderr retained. This expected absence does not invalidate preceding reads and is not a device failure. No write/reboot/deployment/load/active discharge action.

Candidate hardware1.7A register value34 and1.8A PPS request are intentionally separate. Existing host proof requires ibus limit1800 in the start log; a future Test343 runner must explicitly expect1700, retaining its1800 raw safety cap, rather than weakening/rewriting historical338–342 guards. No physical runner created/replayed by this offline preparation.
