# Host regression tiers

The primary development command is:

```sh
bash scripts/check-stall-offline.sh
# Equivalent test selection, with machine-readable results:
python3 scripts/run-host-tests.py changed --report out/host-tests/changed.json
# Include already committed changes since a chosen commit:
bash scripts/check-stall-offline.sh --changed --base HEAD~1
# Preview the selection without executing tests:
python3 scripts/run-host-tests.py changed --list
```

All commands here run locally. They do not contact the tablet. SSH orchestration
tests substitute a temporary local executable. Existing kernel-source and some
built-config prerequisites remain in core; this first migration is not a promise
that a fresh checkout without `.work`/`out` can run every core test.

## Changed files (daily default)

The shell wrapper now defaults to `--changed`. The Python runner retains its
old `core` default for compatibility; use its explicit `changed` argument.
Changed mode unions staged changes since `HEAD` (or `--base REV`), unstaged
changes and untracked, non-ignored files. `--base` is an exact commit comparison,
not an implicit merge-base or the previous successful run. It also includes local
edits. Invalid revisions/Git errors fail instead of producing an empty selection.

`tests/change-impact.json` records reviewed dependencies. Current narrow rules:

| Changed path | Selected coverage |
| --- | --- |
| `scripts/wedge-evidence.py`, `scripts/wedge-ssh.sh` | 17 replay, mocked transport and profile gate tests |
| `scripts/audit-dt-providers.py` | 11 scanner and built-DTB audit tests, including the artifact tier |
| `tests/test_*.py` | That entire test module plus transitive static-import consumers (the panel test exports helpers to three Pogo modules) |
| Root `README.md`, this workflow document | Documentation review; no unit tests |
| Any other path, deleted source or renamed source | All retained tests |

Selections are unioned and deduplicated. Each path's reason and any full-suite
fallback are printed and included in `--report`. Public build/config/kernel
changes, suite/impact configuration and unknown dependencies currently use the
all-tests fallback. Changed modules include tests from every tier. Import
failures remain visible even if the changed file is unrelated. Stale dependency
selectors are errors. Only exact reviewed documentation paths may select nothing;
other documentation and new unknown files trigger the full fallback.

A clean worktree against `HEAD` executes **zero tests** and says so explicitly.
After committing, use `--base HEAD~1` to verify that commit, or `--core`/`--full`
for unconditional regression. Reports with no selected tests say `executed: false`;
this is not a successful full regression. Build outputs in ignored `out/`, kernel
checkout changes in `.work`, toolchain/environment changes and dynamic imports are
outside Git path selection: run the appropriate artifact/full checks yourself.
Update the dependency map when introducing a new consumer of a mapped script.

This selection is for iteration. Run all tests after editing selection rules,
for broad integration changes and for final candidate review. No past passing
result is cached or reused, and the tool does not build, flash or contact hardware.

| Tier | When required | What it checks |
| --- | --- | --- |
| `core` | Unconditional broad host regression | Boot handoff, rootfs installation, protocol/parser behavior, failure attribution, active script/config/source invariants and new tests |
| `artifacts` | Kernel, DTB, config, profile or packaging changes; after building | Selected production/diagnostic configs, images, bundle DTB extraction and built-in provider audit |
| `archive` | Historical records, manifests, captured logs or parked images change; before discarding old build outputs | Selected historical registrations, evidence provenance and immutable bundle identity |
| `all` | Suite routing/retirement changes, broad cross-cutting changes, final candidate review | Every retained test, exactly once |

```sh
python3 scripts/run-host-tests.py artifacts --fail-on-skip
python3 scripts/run-host-tests.py archive --fail-on-skip
python3 scripts/run-host-tests.py all --fail-on-skip --report out/host-tests/all.json
python3 scripts/run-host-tests.py core --list
```

`--fail-on-skip` requires all selected prerequisites to be available. Without it,
unittest's usual skip behavior is retained, with reasons printed and included in
the JSON report; a skipped artifact check is not proof that an image was verified.
The report includes selected IDs, tier counts, failures/errors, skips and wall
time. `--list` discovers without running and labels the report `executed: false`.

`check-stall-offline.sh --focused` retains the short verdict/replay check and trace
feasibility report. `--artifacts` also runs trace feasibility; `--archive` runs the
archive tier. `--full` still means **all retained tests**, plus shell syntax and
trace feasibility. Plain `python3 -m unittest discover -s tests` remains exhaustive.
The default shell wrapper checks every shell file individually and runs changed;
trace preparation is no longer a prerequisite for unrelated host development.

## Routing and retirement rules

`tests/suites.json` is an explicit reviewed manifest, using exact class selectors
and exact test overrides with reasons. Class rules enumerate their reviewed
methods; overrides take precedence. Unclassified tests, including new methods in
an existing archive class, default to core. Stale selectors/members, invalid tiers,
empty reasons and duplicate discovered IDs fail selection. Import failures remain
core failures. The three tiers form a disjoint union of discovery, with no hidden
test-name filtering or blanket GPU/CSD exclusion.

Mixed classes stay in core unless individual methods were reviewed. For example,
`DocumentationTests` contains an actual decompression/hash check of the historical
test-191 image: it remains executable in archive. Actual test-228 log replay stays
in core because it tests today's attribution algorithm. This is an incremental
migration; some historical prose and build-dependent checks still remain in core.

The first review starts from commit `f02bd15e77c7c4177501aee2d4657e83ff489ca7`
(999 tests). `tests/retired-tests.json` records each removed ID and reason:
documentation phrase locks were removed, scanner source-text checks were replaced
by actual rg/grep fixture tests, and CSD gate text checks by mocked execution of
valid and rejected runtime states. Two CSD summary-format checks remain until
equivalent behavioral coverage exists. Original documents and captured evidence
are preserved; scientific interpretations may evolve with evidence.

Do not remove an operational guard merely to reduce the count. Replace the needed
behavior first. Moving a test to another tier changes when it runs, not whether
it exists. A faster core run has narrower scope than `all`; report both timings
separately rather than presenting selection as a full-regression speedup.
