# Offline stall workflow review, 2026-09-27

Owner request: assess the repository's direction, improve testing, then proceed
to the next step, without physical testing. No tablet connection, reboot,
flashing, tracing setup or partition operation was performed.

Outcome and next work: [current workflow](../../../docs/STALL_TEST_WORKFLOW.md).
The mainline direction is retained; causal overclaims are corrected. The next
trace's persistent capacity is insufficient at the historical text rate, so
capture readiness remains unproven. This is an offline review, not test-229.

## Validation

* Full host regression: `python3 -m unittest discover -s tests -v` — **995 tests
  passed**, 246.925 seconds. This includes the actual test-228 log replay and
  a mock SSH transport, never the real SSH executable.
* After the final runtime-watchdog arming check was added:
  `bash scripts/check-stall-offline.sh --focused` — **12 tests passed**, 10.862
  seconds. It also checks every shell file in scripts/, scripts/lib/ and boot/
  individually and regenerates the trace audit. The integration test rejects a
  disabled runtime watchdog before issuing even a mocked reboot and proves
  that non-clean results stop a requested three-round series after round one.
* `USE_CCACHE=1 BUILD_MODULES=0 JOBS=16
  KERNEL_OUT_DIR="$PWD/out/kernel-offline-review" ./scripts/build-kernel.sh` —
  **compiled**, followed by a passing `sha256sum -c SHA256SUMS`. Configuration,
  DTB and release bytes match `out/kernel-gts9wifi/`. The kernel image's
  compressed hash is recorded without claiming reproducibility.
* `git diff --check` — passed. GitHub Actions remains manual-only and was not run.

The first full run exposed obsolete runner implementation-string assertions and
an outdated missing-console expectation. Those were replaced/corrected and the
full run repeated. It also hit LeakSanitizer's sandbox process-inspection limit;
the successful full run used the approved host environment. The first compile
hit a read-only ccache path; its approved host rerun completed. Neither problem
was bypassed by disabling the checker or claiming a failed build passed.

## Files

* `trace-feasibility.json`: source/config/event hashes, the minimal proposed
  event set, 896 KiB sink budget and explicit readiness blockers.
* `kernel-SHA256SUMS`: independent output directory's compiled artifact hashes.
* `host-tests.txt`, `focused-tests.txt`: successful test transcripts.
* `review-inputs.json`: base commit and hashes of the modified/new reviewed files.

No boot bundle was generated, because this change does not alter the kernel,
device tree or boot profile. The trace capacity audit is not a flash candidate.
