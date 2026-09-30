# Test261: NCM host connection readiness

Purpose: qualify an explicit bounded Windows/WSL readiness gate and source-bound
SSH entry without flashing or changing the accepted Test255 installation.
Owner instruction: "先修 NCM，暂不刷机".

This is not a kernel/charging candidate or a reboot/reconnect stability series.
Test260 artifacts remain offline and unchanged. PPS and the charge pump remain
disabled. Historical Test258/259 failures remain stopped.

Registration: one read-only connection on the current accepted Test255 boot.
Save ADB boot/uptime; wait at most 30 seconds for the production Windows NCM NIC,
preferred APIPA /16 and matching direct WSL route/address; then make ONE SSH
connection with verified source binding (connect 10 seconds, process 15 seconds).
Require identical ADB/SSH boot IDs. Preserve all raw snapshots and process
metadata. Optional additional Windows bound-banner validation is read-only,
separate from this SSH result, and never retries a failed SSH command.

Stop on Code43, ambiguous identity, failed evidence capture, readiness deadline,
SSH failure or boot mismatch. No reboot, unplug request, network repair command,
rootfs change, partition write, module replacement, PPS or pump activation.
Rollback is unnecessary: this test makes no configuration writes.

Host validation: new readiness tests plus existing passive admission and
production transport tests; syntax checks. No test routing changes, kernel
rebuild or repeated full suite. Existing Test260 kernel qualification is reused;
this does not create a new kernel acceptance.

Limits: an already-running boot cannot reproduce or disprove the Test259 early
startup timeout. A pass only proves this entry can identify and use the current
NCM path. A future startup test needs separate authorization/registration.

See [design](../../../docs/NCM_HOST_READINESS.md) and eventual RESULTS.md.
