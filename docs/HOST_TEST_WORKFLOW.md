# Host regression tiers

## Validate changes, not commits (owner instruction, 2026-09-30)

A candidate gets one final build/artifact audit and one final full host run.
Reuse that qualification for the exact unchanged source/build inputs and hashed
artifacts. Recording results or updating documentation does not require another
kernel build or full regression. Keep the source revision and artifact hashes in
the qualification record; a later documentation commit is not a new candidate.

| Actual change | Required work |
| --- | --- |
| Kernel, driver, config, DTS, build integration | Affected tests during development; one final build/config/DT/protected-file/artifact audit and full host run |
| Runner or parser | Affected host tests and syntax checks; no kernel rebuild unless kernel/build inputs also change |
| Suite routing | One full host run; no kernel rebuild solely for routing |
| Documentation, status, raw results | Diff review, new evidence hash/summary checks where relevant; no build or full host run |
| Unchanged candidate, physical observation | Essential live identity/rescue/battery gates and observation; reuse offline qualification |

Do not invoke wrapper, changed and all consecutively when they execute the same
IDs. For a final candidate, the full run can serve the selected host regression
too; record shell/artifact checks separately if needed. Existing tests remain
available and unchanged. A failed check or a change to the relevant source,
profile, pin, toolchain, build input or artifact invalidates the affected
qualification. A new commit containing only results does not.

For a reviewed documentation/results-only commit, record `executed: false`, the
reason and the earlier qualification being reused. Do not label omitted tests a
new regression pass. The selection tool still conservatively falls back to all
for unknown paths; that fallback does not mandate executing it for prose-only
work. Do not add blanket exclusions for evidence or documentation that is read
by executable tests.

Physical checks are also scoped: inspect the full baseline once, verify files
and partition/module readback at deployment, then use boot/config/notes and
health/transport gates on startup. Combine telemetry, boot ID and fault checks
per sample. Preserve full kernel journal at stage boundaries and on first fault;
do not retrieve it or rehash unchanged rollback directories on every sample.
Unknown identity, new reboot, lost rescue or a safety fault still stops the test.
Registered observation windows and safety limits remain in force.

## Round speed (owner instruction, 2026-10-02)

Use [CHARGING_ROUND_WORKFLOW.md](CHARGING_ROUND_WORKFLOW.md) for the reviewed
sequence. Group related capture and independent read-only checks, accept native
ADB recovery readiness promptly, and reuse unchanged build/test qualification.
Do not pause for a separate commit or review after each command; register/push
before mutation and archive/push each completed meaningful stage/test. Preserve
safety/identity/transport gates, observation limits and first-failure handling.
A failure needs immediate cleanup/recovery, not a wait for a network push.

## Device completion criterion (owner instruction, 2026-09-30)

For subsequent physical tests, normal device behavior within the registered
scope is sufficient to complete device acceptance. Record a host-only logging,
filename or parser defect separately; it does not itself require a rollback,
reflash, repeated physical observation window or complete host regression.
When needed, collect only the missing device evidence in a fresh namespace.
Preserve the original error/raw verdict and distinguish device completion from
an original runner's clean result. Unknown device state remains an evidence
gap, not a fabricated pass. Actual device safety/identity/transport failures
still stop. This criterion does not authorize PPS/pump/current escalation or
another unregistered physical test.

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
for broad integration changes and once for final candidate review. The tool
itself does not cache passing results, build, flash or contact hardware. The
workflow may reuse a recorded qualification for unchanged source/artifacts as
described above; it must not present that reuse as a new executed test run.

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
