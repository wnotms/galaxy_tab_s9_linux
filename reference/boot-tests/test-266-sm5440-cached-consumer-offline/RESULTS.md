# Test266 — offline cached SM5440 consumer qualified

Source `6477a094a084885a3730324f02ff1fba0fd34c93`. Added
`sm5440_passive_read_cached()` to expose a coherent copied passive measurement:
VBUS/VBAT in uV, IBUS in uA, die temperature in deciC, online and the original
acquisition-start BOOTTIME. This follows the Fedora same-model physical-telemetry
approach while keeping Samsung X710 ADC decoding and the validated passive path.

The timestamp is captured before the existing converter enable, rather than at
publication. Unknown/future/older-than-100ms, pending, invalid, fault, stopped,
active-mode or unbound data is rejected, with output cleared. The read performs
no I2C, converter operation, scheduling or hardware change. Provider registry
mutex precedes a nonblocking `mutex_trylock(io_lock)`; a busy I2C worker returns
EBUSY immediately. Unpublish drains copied readers before devres teardown, and
no provider pointer escapes. Existing poll, OFF, quiesce and resume functions
retain their hardware behavior.

Final qualification: 44 affected tests and one full 1379-test regression passed
with zero failures/errors/skips (full runner 107.441 seconds). All previous
1369 test IDs are retained, with 10 added tests. Tests compile the actual C
functions and exercise age boundaries, acquisition time, zeroed failure output,
mode/PM/fault gates, busy-worker refusal, units and provider lifetime. Initial
43-test/full1378/build evidence is preserved, but superseded after the lock
review correction; it is not the final qualification.

The isolated Linux 7.2-rc3 ARM64 build passed with clang21, ccache and JOBS=8.
Image.gz, resolved/embedded config, kernel notes and all 181 paired regular module
files match the final committed source; archive membership/hashes match exactly.
W=1/sparse passed with the unchanged driver object and only the already known
upstream VDSO `__kernel_getrandom` missing-declaration warning. See ARTIFACTS.json
and validation/artifact-audit.json for exact hashes and source identities.

Exact Test263-to-Test266 resolved config diff: empty. Exact DTB diff: empty;
config and DTB bytes match accepted Test263. All 85 Docker/UPower configuration
requirements, CONFIG_HVC_DCC=n and 96 protected files remain intact. The audit's
older Test255 comparison shows the previously accepted passive SM5440 node and
profile; these are not new Test266 DTS/config changes. No DTS, SM5714 switching
policy, current/float voltage/thermal, TCPM, DWC3, gadget, adbd or rootfs change.
No new dtbs_check run is claimed because this increment did not alter DTS/DTB.

This is a cached API, not on-demand acquisition: the existing 1-second cadence
and converter wait remain unchanged, so many reads may return ESTALE. It does
not prove physical ADC/current calibration, active 100ms monitoring, OCP cutoff
or a complete live PM/handoff adapter. A future consumer must recheck connection
state, PM and freshness before acting. Active Stage3 remains NOT READY.

No device command, flash, reboot, module replacement, PPS request, pump activation
or current escalation occurred. The device remains on accepted Test263 and keeps
its Test260 rollback. There is no physical Test266 acceptance claim or automatic
next deployment. Result/status-only commits reuse this exact qualification and
record tests/build executed:false rather than repeating the checks.
