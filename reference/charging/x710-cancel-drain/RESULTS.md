# Retained X710 cancellation and queue-failure drain

**Offline qualification PASS; complete charging port NOT READY.** This increment
changes only native controller admission/cleanup scheduling, not charging limits
or hardware policy. Design preceded implementation in `docs/X710_CANCEL_DRAIN.md`.

## Reproduced defects and fix

Actual-C threaded mock tests reproduced twelve failing subcases before the fix:
new control revoked cancellation before its immediate callback, and regular job
queue refusal removed monitoring without scheduling exit. Raw failures are in
`before-fix-tests.log.gz`. This does not prove a naturally occurring queue failure
or device CPU fault. Kernel activation/OCP grants remain private and closed;
mock-only grants are excluded from the kernel build.

An active cancelled session now refuses new controls before cancelling its queued
cleanup or clearing cancellation. An active request queue refusal returns EBUSY,
marks cancellation and queues the existing immediate terminal callback. Admission
performs no supplier I/O and introduces no new lock/retry. Cleanup retains the
once-only OFF → fixed physical proof → lease-release sequence. Unknown OFF still
forbids voltage change/release; unresolved ownership blocks new control. PM drains
queued emergency cleanup; resume does not start another session.

## Affected local qualification

**29 controller tests PASS, 0.442s, zero skips.** New cases cover all six
commands during pending cancellation, all four admissible active commands during
regular queue refusal, refusal of a second request, exactly-once terminal cleanup,
failed OFF and suspend draining the queued exit. Existing tests remain intact.
Only this suite consumes the changed workqueue mock. The other fifteen suites
from the prior 351-test qualification are unchanged and reused, not re-executed
or counted as a new full regression. No routing change or GitHub Actions.

ARM64 Image/DTB/modules **PASS 85.446s**, 8 jobs/ccache, existing native
profile cache. W=1/sparse **PASS 7.014s**, only the known upstream vDSO
warning and no changed-driver warning. Strict full-file/diff checkpatch and
whitespace checks pass. An additional host assertion wrongly assumed W=1 would
leave the object byte-identical; the failed assertion and log remain recorded.
Restoring standard compile flags and comparing objects shows only DWARF/debug
changes, no allocated runtime byte/shape change. Sealed formal outputs were not
relinked by the static check. See `static-object-comparison.json`.

Resolved config exactly matches the preceding pack-current native candidate:
`6f70dd31a582efc0464c37b505693f7fe8af3949a9c2a573a1ca116a7e73f42d`.
DTB remains byte-identical to accepted Test311:
`233a9fee91dc725901f0c7c620a38e475d6d6e6880cde660ec85ae34d49e0a8e`.
No new config/DT changes. DCC remains disabled; SM5714/ADC5 and Test254 container
requirements remain enabled. The existing native-profile delta from accepted311
is retained rather than counted as this increment's change.

**56 protected source /36 frozen formal hashes preserved.** All 181 paired module
files match the expected file set. Differences from accepted311 remain recorded
BTF/build-ID/DWARF directory differences; other runtime bytes/shape/relocations
and nondebug symbols are equal. Built-in metadata/index equals the preceding
pack-current candidate. Actual compiled sources, embedded config, kernel notes,
linked controller and supplier/core/hardware references are verified.

Formal output: `out/kernel-x710-cancel-drain/`; full detail in `summary.json` and
`artifact-audit.json.gz`. The same native cache now belongs to this candidate,
not original Test303. No extra full build tree or Windows staging.

## Device and outstanding work

No flash/reboot/partition/module/service/config/charging write or PPS/pump ON.
The retained ADB recheck was empty. The owner now reports current low-battery
shutdown; this is owner attribution, not a new battery measurement, and does not
explain an earlier unaccounted boot change. Recover using the already accepted
18W supply before normal-boot/SOC>=20% physical entry checks. No repeated online
probe or recovery command was sent after that report.

PC charging review separately found that a valid higher 5V TCPM grant can still
be clamped by SDP classification. No change is included here: the actual PC
port/source capability is not known and default SDP is not higher-current
permission. Fixed5V<=1.8A/9V<=1.5A, float4440mV, thermal/fail-closed/suspend,
SM5714/TCPC/DWC3/USB/adbd/rootfs/DTS/config remain unchanged.

The full port still requires physical ADC/gauge freshness/calibration/current/
cutoff qualification, independent PPS-OFF/<=1.8A pump/fault/PM acceptance, then
higher-power steps. Software cancellation tests do not establish physical OFF
response or protection during an I2C hang/CPU stall. Do not repeat an unchanged
failed ADC profile or open private grants based on these host results.
