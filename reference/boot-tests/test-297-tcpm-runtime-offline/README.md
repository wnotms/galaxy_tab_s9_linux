# Test297 — standard TCPM runtime observation (offline)

Add a lifetime-pinned, kernel-only snapshot of source PDOs, successful fixed
current/charge callback mirrors and standard TCPM power_supply properties.
This is a coordinator prerequisite, not a PPS operation or charging grant.
No raw controller/supply pointer escapes. Removal drains active readers before
releasing the supply; faults, pending callbacks, changed generations and
inconsistent observations return zeroed evidence. Optional0400 current-port
calls the actual API. Stock TCPM property reads are lockless; this is bounded
consistent observation, not an atomic TCPM transaction or physical measurement.

No TCPM core/config/DT/USB/ADB/roles/SM5440/current/thermal change. Fixed Request
validator remains PPS-disabled. Existing296 ADC rearm and startup refusal are
inherited, not resolved or waived. Do not repeat delay-only diagnostics.

119 affected SM5714 tests passed in4.546s, including the new actual-C runtime
suite and retained existing tests. ARM64/passive build and changed-object sparse
qualification pending. Reuse unchanged full294 regression; no routing changes
or full-suite repeat. Test297 performs no device mutation. A separately pushed
Test298 will perform one short read-only current-port call and exact263 rollback;
PCUSB need not supply PD capabilities, so a zeroed no-data refusal is evidence,
not permission to invent a contract. See docs/SM5714_TCPM_RUNTIME_SNAPSHOT.md.
