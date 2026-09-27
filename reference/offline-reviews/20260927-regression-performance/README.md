# Full host regression performance, 2026-09-27

Request: reduce the duration of the full regression suite while preserving
coverage. No physical device was contacted or operated.

## Measured result

Both full runs used Python 3.14.4 on the same host, without concurrent kernel
builds. They used the same artifacts and command:

```sh
python3 -m unittest discover -s tests --durations 0
```

| Measurement | Before | After |
|---|---:|---:|
| Tests, all passing | 995 | 999 |
| unittest elapsed | 125.281 s | 81.046 s |
| Process wall time | 125.41 s | 81.16 s |
| Process peak RSS | 396,028 KiB | 399,936 KiB |
| Standalone DT provider audit wall time | 48.43 s | 0.44 s |

The full suite saved **44.235 seconds (35.31%)**, with four additional behavior
tests and no removed tests, artifact checks or sanitizer checks. These are local
single-run measurements, not a guaranteed runtime. Filesystem caches were not
flushed. The earlier 246.925-second review run overlapped a kernel build and is
deliberately not used as the performance baseline.

## Change and equivalence checks

`audit-dt-providers.py` previously recursively searched the kernel source for
each unbound compatible. It now scans declarations once per invocation, using
`rg` when installed and GNU `grep` otherwise, and shares the resulting in-memory
index. No persistent cache or test parallelism is involved. Exact compatible
matching, declaration-only matching, ignored source exclusions, fallback
compatibles, Makefile ownership and y/m/n classification remain in place.

Three full audit outputs were compared byte-for-byte: the original implementation
from commit `007ba4a`, the new implementation using rg, and its grep fallback.
They are identical. `unchanged-audit-report.json` holds that report, and
`measurement.json` holds its three matching hashes plus the relevant input
hashes and base revision.

The four added tests exercise both engines on synthetic source trees, scanner
failure versus a valid empty result, exact matching including regex punctuation,
hidden/ignored files, repeated lookups without rescanning, fresh source edits on
the next invocation, and config/fallback classification. The audit module's
20 tests passed in 0.678 seconds. A scanner failure now stops the audit instead
of being misreported as missing drivers.

## Evidence

* `before-tests.txt` / `after-tests.txt`: complete successful full-suite output
  with per-test timing; adjacent `*-time.txt` files record wall time and peak RSS.
* `index-tests.txt`: focused audit regression output.
* `audit-before-time.txt` / `audit-after-time.txt`: standalone audit timing.
* `measurement.json`: structured comparison and input/report identities.
* `unchanged-audit-report.json`: common report from all three implementations.
* `kernel-SHA256SUMS`: the separate compile-only output, built after both timed
  runs with `USE_CCACHE=1 BUILD_MODULES=0 JOBS=16
  KERNEL_OUT_DIR="$PWD/out/kernel-regression-performance" ./scripts/build-kernel.sh`.
  Its manifest verifies; config, DTB and release match production. All benchmark
  input hashes were checked again after compilation and still match. Shell syntax
  checks and `git diff --check` also passed.

The remaining largest individual costs are the mocked SSH series (~10.6 s) and
parked-bundle validation (~8.3 s). Those checks are still enabled. Use
`--durations 20` to identify future bottlenecks before changing coverage or
adding cross-process caches.
