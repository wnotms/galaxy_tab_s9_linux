# Test272 — passive fresh-request offline qualification

Implemented a kernel-only, OFF-mode SM5440 acquisition request, with provider
lifetime protection, request serialization and genuine timestamp/sequence checks.
Final source revision: `399eb49786039d8ef654769dd94ef2a439d0af90`.
**Offline qualification PASS; active/high-power charging remains NOT READY.**
Installed Test263 and all earlier physical results are unchanged. This test sent
no device command and performed no flash, reboot, PPS Request or pump activation.

## Actual changes

- `kernel/drivers/sm5440-direct.c`: share existing sample refusal/copy checks;
  add `sm5440_passive_request_fresh()`, atomic user/reservation lifetime, completed
  sample and started-conversion counters, request wait/wake, and PM epoch.
- `kernel/drivers/sm5440-hw.h`: declare the sleepable OFF-mode API and existing
  100ms validity budget. No writable userspace or ON/PPS interface.
- `tests/test_sm5440_fresh_request.py`: 28 actual-C tests, including a real
  concurrent unpublish thread and deterministic converter/clock scenarios.
- Existing cached/passive/snapshot test mocks gain the new types/counters and
  shared helper functions; all prior tests and assertions remain available.
- `docs/SM5440_FRESH_REQUEST.md`: acquisition/locks/lifetime/PM design and limits.
  This registration, future physical plan, source review and evidence complete
  the offline record; `AGENT.md` records the final status.

The request queues the **existing** delayed worker immediately. It accepts only
an eligible OFF-mode new completion whose conversion began after the request,
including same-millisecond cases checked by conversion sequence, and whose oldest
acquisition age and total delivery satisfy the100ms software budget. Cache reads
never restamp data. Only one requester reserves a provider at a time. Busy,
fault/I2C error, pending startup, PM epoch change, unpublish, old/future timestamp,
active mode, timeout or late release clears the destination and fails.

The registry pins a user then releases before wait. The requesting thread does
no I2C and holds neither registry nor io mutex during the converter wait. Unpublish removes the pointer, wakes requesters, drains users
and synchronizes the last wake/unlock before devres free. PM sets stopped/epoch
under io_lock before work drain, preventing late request scheduling. Resume cannot
revive a pre-suspend request. No provider pointer escapes this API.

## Final qualification

| Check | Result |
|---|---|
| Affected SM5440 tests | 112 PASS, including28 new requests |
| Full host regression, final source | 1424 PASS, 0 failures/errors/skips; 97.977s unittest / report elapsed in JSON |
| Retained Test269 IDs | All1396 retained;28 added;0 removed |
| ARM64 Image.gz / DTB / modules | PASS, clang/ccache/JOBS8, `sm5440-passive` profile |
| W=1 / sparse | PASS; driver object hash unchanged by static review |
| Embedded config | Exact resolved config and byte-identical Test263 |
| DTB | Byte-identical Test263 |
| Pairing | 181 regular module-directory files, exact archive match |
| Protected source | 96 unchanged; all8 compiled overlays match final commit |
| Container/DCC gates | 85 required container symbols retained; HVC_DCC absent |
| Frozen Stage2 artifacts | Intact |

The static pass retains the known upstream VDSO `__kernel_getrandom` declaration
warning. Config seed/merge warnings remain in build stderr; the resolved gates
passed. Do not claim a warning-free upstream build. Final artifact identities
are in `ARTIFACTS.json`; logs and command/source metadata are under `validation/`.
Exact Test263 config/DT diffs are empty. Standard artifact audit also compares
older Stage2/Test255 and explains the already accepted passive enablement; it is
not a new Test263 configuration or DT change.

### Superseded initial qualification

The initial build and1424 host tests at `2c8c8b9a` passed, but final pinned-source
review found `system_wq` and `system_percpu_wq` are separate allocations in7.2.
The fresh request must match `schedule_delayed_work()`'s `system_percpu_wq` to
retain same-work non-reentrancy. Commit399eb497 corrects that choice and adds a
pinned-API assertion to the real-C suite. Initial records are retained with
`initial-` names and are **not** final qualification. A final incremental build,
full regression and artifact/static audit were necessary because source changed.
The earlier snapshot mock's missing type declarations were also fixed without
removing or weakening its assertions; development note retains that host error.

## Behavior and safety preserved

No converter register operation, averaging/channel selection, 25ms poll/up-to300ms
wait, default1s worker cadence, startup classifier or protection recipe changed.
Absent an explicit kernel caller, normal monitoring follows its existing flow.
Requests do not clear a fault or automatically retry after refusal. A timed-out
request may leave the ordinary converter worker running; it never promotes its
later result to this request's success or cancels the ordinary monitor.

SM5714 switching charger/TCPC/TCPM, fixed5V<=1.8A/fixed9V<=1.5A,4440mV, pack
thermistor/fail-closed thermal handling, SM5440 protections, DTS/config, CPU/GPU,
USB/DWC3/gadget/adbd/NCM/SSH and Docker/UPower inputs remain unchanged.
No live adapter, current rise, source role, PPS transmission or pumpON was added.

## What remains unqualified

The100ms checks are software evidence validity/refusal rules, **not** a measured
hard-real-time operation, hardware cutoff, calibration or active-mode API.
Scheduling and in-flight I2C cannot be preempted. The unchanged32-sample converter
can exceed100ms and the API must then fail; real timing acceptance is untested.
OFF-mode/current0 cannot prove nonzero current accuracy or OCP behavior.

A separate bounded read-only kernel consumer is still needed to exercise this
new API on hardware; no caller or userspace trigger was installed. Independent
voltage/nonzero-current calibration, verified protection/cutoff, live adapter
supplier PM/lifetime, active acquisition and actual source PPS APDO remain open.
An18W/65W label alone is not APDO evidence. Keep existing active SOC/thermal/
voltage/current entry gates; do not bypass them to test this interface.

`FUTURE_PHYSICAL_PLAN.md` describes that separate passive candidate/consumer
acceptance and rescue rollback. Test272 itself requires no rollback because no
installed software changed. No GitHub Actions or automatic deployment occurred.
Historical Test267 STOP and Test271 startup classification gap remain unchanged.
