# Test288 — offline private I2C phase trace qualification

Purpose: distinguish frozen SM5440 worker I2C envelopes/poll observations from
aggregate worker duration, using existing source-defined tracepoints. No device
commands, tracing, module load, fresh call, transfer, reboot or flash in Test288.
No kernel/config/DTS/ADC/deadline/USB/adbd/rootfs/charging changes.

Read `docs/SM5440_I2C_PHASE_TRACE.md` for source provenance and evidence limits.
New named Session/decoder/analyser/coordinator; frozen279/280/285 modules and
all historical STOPs/seals remain unchanged. Bus0 filter, workerPID/address0x63
transaction pairing, complete source recipe, signed negative/short I2C errors,
full raw/counters/hashes/clock/cleanup checks. No physical ADC duration/grant.

36 affected host tests + syntax qualify only offline behavior. Reuse unchanged
272provider/276observer(full1481/W1/sparse)/27950/28024/28328/28512/28619/28719.
No full rerun/build/routing or GitHub Actions. Test287 raw trace remains aggregate
only; new parser refuses to invent missing I2C fields from it.

Future separate physical registration: one already-qualified272 candidate +276
observer, this private I2C profile, existing285commandIO/286health-journal/283native
waiter, same acquisition budgets/first refusal/owned cleanup, exact263 rollback.
Group existing commands/read-only boundary captures; do not repeat aggregate-only
acquisition. ActiveStage3 NOT READY, full charging port goal remains incomplete.
