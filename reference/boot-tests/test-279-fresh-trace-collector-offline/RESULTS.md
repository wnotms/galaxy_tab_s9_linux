# Test279 result — offline collector qualification completed

Registration commit: `14346f20`, pushed to `origin/test` before development.
Task baseline: `8a87778afcdc9cd5d2e26d58410d496c8ff104a9`.

Implemented an isolated, bounded tracefs collector and a strict raw-evidence
parser. The collector has no observer load/unload, ADC request, charger access,
ADB, reboot or flashing operations. Actual tracefs/backend capabilities remain
unverified on the tablet. This is host qualification, not a physical result.

## Executed validation

- **50 host tests passed**, zero failures/errors/skips; syntax checks passed.
- Mocked normal collection, output/instance/probe collision, absent symbols/clock,
  incompatible format/filter, partial setup, deadline, interruption, snapshot
  failure and cleanup failure. Raw trace is preserved when counter reads fail.
- Parser tested boot/clock changes, hashes, missing/empty/truncated/lost/consumed
  evidence, unknown CPU, probe misses/hit-count mismatch, request/work pairing,
  older in-flight work and first-refusal stop. No timing or charging grant.
- Seven tracing files match the actual pinned Linux source. Signed return types,
  inherited instance options, runtime symbol filters and probe-profile columns
  are audited; no reliance on function-graph tracing or an inlined symbol.
- **198 protected tracked files unchanged** against task baseline. All21 Test278
  hashed inputs still match; Test275380, Test277417 and Test27825 sealed files
  verified. Corrected276observer `.ko` hash remains `9aafabf6…`.

The synthetic fixture intentionally models a101ms refusal,9ms queue delay and
121ms aggregate worker. These numbers are **invented test inputs**, not new
measurements or an explanation of275/277. ADC duration and timeout branch remain
null/UNKNOWN. A second synthetic scenario preserves an older worker and a later
queued callback without inventing a causal request assignment.

## Qualification reused

Kernel build/full suite executed: **false**. No kernel/build integration or global
test routing changed. Reuse unchanged Test272 provider and Test2761481-test/W=1/
sparse qualification; affected host tests and syntax ran once for final review.
No Actions/CI, kernel/config/DT/rootfs/ADC/deadline change or device command.

Last recorded physical endpoint remains Test277's restored Test263 boot
`cdce6deba2e04f3481679632e38ac997`. It was not rechecked in279. Fixed-PD limits,
4440mV/thermal/suspend behavior, DCC=n, container config and ADB reconnect code
are unchanged. Test275 freeze causation and Test277 acquisition refusal remain
unresolved; history is not rewritten.

## Next

Prepare a separately registered single passive trace attempt following
`docs/SM5440_FRESH_TRACE_COLLECTOR.md`. No physical execution, new kernel build,
deadline relaxation, ADC policy change, PPS/pump enable or power increase is
authorized by this offline result. Physical collection/orchestration and kernel
probe acceptance are **NOT TESTED**. Active Stage3 remains **NOT READY**.
