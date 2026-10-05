# Native SM5440 hardware session — offline qualification

The real bound driver now exposes an explicit kernel-only session, drains the
ordinary poller before hardware takeover, rejects old provider/session tokens,
and serializes actual uncached I2C settings/ADC/WDT/actuator/supervisor calls.
No regmap/supplier pointer escapes. Lifetime pins and PM generation invalidation
cover drain, operations, unpublish and cleanup; WRITE_ONCE publishes ownership
to the lockless old poller. An old poll's late cache is invalidated again.

No native activation flag/lease/OCP grant is installed. START/RESUME/PAUSE/active
monitor calls are refused. Probe/timers/userspace do not invoke the control API.
This does not complete the active controller or justify pump enablement.
Terminal cleanup verifies OFF before restoring controls/converter; uncertain OFF
retains ownership and refuses hidden retry or passive restart. First operation
and cleanup errors remain separate. Resume restarts only old OFF monitoring.

The new profile is separate from historical offline-policy semantics.
`sm5440_quiesce`, ordinary conversion and rearm functions are byte-identical.
The nine existing helper files changed only comments; algorithms/limits remain
identical. Existing tests were neither modified, removed nor skipped.

Validation:

- Related **535 PASS**, 16.673s, zero skips. After final
  WRITE_ONCE publication, **16 native tests PASS**, 0.761s.
  Actual C and real helpers are executed on mocked I2C, including every-call
  failures/uncertain writes, delayed unpublish, PM during drain/conversion,
  stale tokens, timeout, cache republication and idempotent cleanup.
- Final ARM64 standard build **PASS**, 78.340s, jobs8/ccache/modules.
  Source copies, embedded config, kernel notes, linked API/PM/hardware helpers,
  181 exact paired files/archive all verified.
- W=1/sparse on five actual units **PASS**, 6.988s. Only the known
  upstream vDSO `__kernel_getrandom` declaration warning, no changed-driver warning.
  Checkpatch0 errors/0 warnings/0 checks; shell syntax and diff check pass.
- DTB is byte-identical to accepted311. Config vs the preceding native observer
  changes only X710_NATIVE_CONTROL absent→y. Vs accepted311, also POLICY n→y
  and CONDITION n→absent from its existing !POLICY dependency. No other delta;
  DCC n, USER_NS/mqueue/containers, SM5714/ADC5 and fixed/thermal limits remain.
- 51 protected hashes and 27
  previous formal hashes preserved. 167 module binaries differ only in BTF,
  build-ID/debug directory offsets: other runtime bytes/shape/relocations and
  non-debug symbols match. Built-in metadata exactly matches the observer;
  its differences from accepted311 are the three already-added policy/session/
  observer metadata entries, not unexplained drift.

Initial qualification found six historical-profile/frozen-teardown test
conflicts; isolation and the separate PM wrapper corrected them. A malformed
patch hunk was corrected before build. Later formatting moved the native poll
guard across a diagnostic #ifndef boundary; the legacy static check caught it,
and the guard was moved ahead of the unchanged diagnostic branch. Failed raw
reports are retained. Final gates above pass; no test weakening or device replay.

Formal outputs: `out/kernel-sm5440-native-control/` (Image.gz, DTB, exact config,
notes, release and matched module archive). Existing303-named incremental tree
now belongs to this new native-control profile, not old Test303 or the observer
provider. Original formal/accepted rollback outputs remain unchanged. No new
full build tree, duplicate candidate images or Windows staging were created.

No device flash/reboot/config/PPS/ON or GitHub Actions occurred. No fresh full
host run: latest owner change-scoped workflow applies; historical full-run
missing retired artifact failures are not relabelled as passes.

**OFFLINE_NATIVE_HARDWARE_SESSION_QUALIFIED; full charging goal NOT READY.**
Next: bind this executor to a real serialized TCPM/source-bound transaction
worker with fixed-PD restoration and PM/fault cancellation. Physical freshness,
calibration/current/cutoff/OCP and higher-power acceptance remain unproven.
Future physical work needs a separate pushed registration and fresh rescue/
≥20% SOC admission; this offline result is not authorization or evidence to
energize the pump. See docs/SM5440_NATIVE_CONTROL.md.
