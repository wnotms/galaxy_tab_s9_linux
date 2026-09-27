# Host regression tiers

The primary development command is:

```sh
bash scripts/check-stall-offline.sh
# Equivalent test selection, with machine-readable results:
python3 scripts/run-host-tests.py core --report out/host-tests/core.json
```

All commands here run locally. They do not contact the tablet. SSH orchestration
tests substitute a temporary local executable. Existing kernel-source and some
built-config prerequisites remain in core; this first migration is not a promise
that a fresh checkout without `.work`/`out` can run every core test.

| Tier | When required | What it checks |
| --- | --- | --- |
| `core` (default) | Every code change | Boot handoff, rootfs installation, protocol/parser behavior, failure attribution, active script/config/source invariants and new tests |
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
The default shell wrapper checks every shell file individually and runs core;
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
