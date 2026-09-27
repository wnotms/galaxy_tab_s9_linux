# Host regression tier review, 2026-09-27

Baseline: `f02bd15e77c7c4177501aee2d4657e83ff489ca7` (999 tests).
No tablet connection, physical preflight, reboot or flash was performed.

## Selection audit

999 original IDs = 939 retained + 60 explicitly retired. Seven new behavioral
tests give 946 retained tests: core 841, artifacts 18, archive 87. The executed
IDs in `all.json` were reconciled against baseline discovery and every removed ID
in [`tests/retired-tests.json`](../../../tests/retired-tests.json). No unexplained
deletion or duplicate selected ID exists.

The retired set contains 53 documentation-only phrase checks, three scanner
source-text checks covered by real rg/grep fixture tests, and four CSD gate
source-text checks replaced by mocked execution. The new CSD test exercises ten
runtime states, including the valid case and missing capability, unconsumed or
conflicting tokens, wrong timeout, early panic and recovery failures. Six suite
runner tests exercise partitioning, new-test defaults, invalid selectors,
duplicates, import failures, failure exit codes, skips and list-only execution.
Class rules enumerate reviewed methods, so adding a method to an existing
archive class still puts that new test in core. The final selection was compared
with the earlier full run: the same 946 IDs in the same order, then rerun in full.

Raw historical evidence and documents were preserved. Historical image integrity
checks still execute in archive, while current attribution replay stays core.
Active behavior tests in mixed documentation/history classes stay core unless an
individual override was reviewed. This is an incremental migration, not a claim
that all remaining tests have been converted to behavioral tests.

## Verification and timing

```sh
python3 scripts/run-host-tests.py core --fail-on-skip --report out/test-suite-review/core.json
python3 scripts/run-host-tests.py all --fail-on-skip --report out/test-suite-review/all.json
for script in scripts/*.sh scripts/lib/*.sh boot/*.sh; do bash -n "$script"; done
python3 scripts/prepare-csd-trace.py --output out/test-suite-review/offline-report.json
USE_CCACHE=1 BUILD_MODULES=0 JOBS=16 KERNEL_OUT_DIR="$PWD/out/kernel-test-suites" ./scripts/build-kernel.sh
```

Both core and all passed without skips: core 841 tests in 64.254 s; all 946 tests in 84.792 s (discovery included). Exact elapsed times and selected IDs are
in `measurement.json`, `core.json` and `all.json`; logs retain compiler warnings
from host fixtures. The recorded core run followed an initial all run; the final
all run followed the last routing hardening. Neither recorded run overlapped
another test run or kernel build. These single samples are approximate durations,
not a controlled benchmark of small performance differences.

The previous 999-test full regression took 81.046 seconds after the scanner
optimization (see the sibling `20260927-regression-performance` record). The
default now has narrower scope. Its shorter runtime must not be presented as an
equivalent-coverage full-regression improvement; all remains available and is
required after suite migration or retirement.

Shell syntax and offline trace-source checks passed. Trace capture readiness
remains unproven: the historical text rate fits only about 5.35 seconds in the
reserved console, against a required interval of at least 41 seconds. Kernel
build verification and output hashes are recorded alongside this review.
