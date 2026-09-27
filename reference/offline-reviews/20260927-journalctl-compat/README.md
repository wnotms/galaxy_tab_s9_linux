# journalctl 257 compatibility repair

Live test-229 found that Debian journalctl 257.13-1~deb13u1 rejects
`--no-legend`. The stall runner now requests a C-locale boot list without that
option. The evidence parser accepts its exact heading once at the beginning,
while rejecting duplicate/misplaced headings, header-only output and error text.
The archived real boot list and a mock transport that rejects the old option
cover both parser behavior and end-to-end replay.

Validation before commit:

* The existing change selector selects exactly 18 relevant tests from 956;
  no fallback to the full suite. `impact.json` is a selection-only report.
* The matching 18 tests were executed with `PYTHONPATH=tests python3 -m unittest
  test_wedge_evidence test_cpuidle_off_profile.WedgeSshRunnerTests
  test_csd_ipi_diagnostic.SshRunnerGateTests -v`: all passed, 18.635 seconds.
  Every selected test ID was cross-checked against `tests.txt`.
* Every shell file in scripts/, scripts/lib/ and boot/ passed individual bash -n.
* `USE_CCACHE=1 BUILD_MODULES=0 JOBS=16
  KERNEL_OUT_DIR=$PWD/out/kernel-journal-compat ./scripts/build-kernel.sh`
  completed. Config, DTB and release match production byte-for-byte; this new
  host-built kernel image has its own hash. Production output was preserved.

The tests use a mocked transport and do not reboot or contact the tablet.
The build was not installed. Real test-229 evidence is in the separate boot-test
archive, committed first as 07bc79f. Full regression was not repeated for this
scoped compatibility repair.
