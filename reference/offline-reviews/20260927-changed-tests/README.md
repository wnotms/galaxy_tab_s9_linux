# Changed-file host regression, 2026-09-27

Baseline: `eed88ce27bff07d12bdaf45fff6fe79a668f5268` (946 retained tests).
Nine new selector tests bring the full suite to 955. No device was contacted,
rebooted or flashed. Raw hardware evidence was not changed.

## Behavior

The daily shell wrapper defaults to Git changed-file selection. Exact reviewed
dependencies cover the attribution/SSH scripts and DT provider auditor. Unknown
paths, shared build/configuration changes, deleted sources and renamed sources
select all tests. Test module changes include transitive static-import consumers.
Selections span all tiers, so a DT auditor change includes actual artifact checks.
Known workflow prose can select zero; other unclassified documentation selects all.

Git discovery includes staged, unstaged and untracked non-ignored files, handles
NUL-separated names and both rename sides, and retains staged edits cancelled by
the worktree. `--base REV` includes committed changes since that exact commit plus
local edits. Clean HEAD means no test execution and an explicit report, not a full
pass. Git errors, invalid revisions, stale selectors, import failures and empty
discovery cannot silently produce a successful regression verdict.

`selector-tests.log` records nine behavioral cases in temporary Git repositories,
including actual CLI/wrapper execution, valid partial selection, full fallback and
failure exit status, list-only behavior, document/clean no-op, unusual filenames,
renames, explicit bases, static dependency closure and hidden import failures.
Wrapper assertions were added after the full run and the nine selector tests
were rerun successfully; selection/runtime code did not change after the full run.

## Measurements

`benchmark.py` supplies one simulated changed path at a time to the actual
selector, then executes the selected real repository tests. It does not edit those
source files or pretend the current broad working-tree changes are narrow.
`scenarios.json` records each supplied path, selection IDs, runtime and result.

| Simulated change | Tests actually run | Seconds |
| --- | ---: | ---: |
| `scripts/audit-dt-providers.py` | 11 | 0.746 |
| `scripts/wedge-evidence.py` | 17 | 18.784 |
| `tests/test_panel_x710.py` (shared function extractor) | 9 | 1.524 |

All scenarios passed without skips. Times include discovery/selection and are
single-run observations, not a claim about equivalent-coverage full regression.
The full 955-test run also passed without skips (`all.json`, `all.log`). The
working-tree `changed --list` run correctly selected all tests because this change
edits the selector and its configuration (`selection.json`, `selection.log`).

```sh
python3 -m unittest discover -s tests -p test_changed_tests.py -v
python3 scripts/run-host-tests.py all --fail-on-skip --report out/changed-tests-review/all.json
python3 reference/offline-reviews/20260927-changed-tests/benchmark.py
for script in scripts/*.sh scripts/lib/*.sh boot/*.sh; do bash -n "$script"; done
USE_CCACHE=1 BUILD_MODULES=0 JOBS=16 KERNEL_OUT_DIR="$PWD/out/kernel-changed-tests" ./scripts/build-kernel.sh
```

Shell syntax passed. The isolated ccache build, output hashes and comparison with
production config/DTB/release are archived here. No kernel build overlapped the
full regression or scenario runs. Trace retention remains the next investigation
gate; changed-file selection does not establish physical capture readiness.
