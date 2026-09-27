#!/usr/bin/env python3
"""Run real tests for simulated one-path changes; does not modify source files."""

import json
from pathlib import Path
import runpy
import time
import unittest

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "out/changed-tests-review"
OUT.mkdir(parents=True, exist_ok=True)
runner = runpy.run_path(str(ROOT / "scripts/run-host-tests.py"))
impact = runpy.run_path(str(ROOT / "scripts/test-impact.py"))
manifest = json.loads((ROOT / "tests/change-impact.json").read_text())
reports = []
for path in ("scripts/audit-dt-providers.py", "scripts/wedge-evidence.py", "tests/test_panel_x710.py"):
    start = time.perf_counter()
    tests = list(runner["flatten"](unittest.TestLoader().discover(str(ROOT / "tests"))))
    selected, selection = impact["select"](ROOT, tests, [path], manifest)
    ids = [test.id() for test in selected]
    result = unittest.TextTestRunner(verbosity=1).run(unittest.TestSuite(selected))
    reports.append({"simulated_changed_path": path, "selection": selection, "selected": ids,
                    "elapsed_s": round(time.perf_counter() - start, 3), "tests_run": result.testsRun,
                    "passed": result.wasSuccessful(), "skipped": len(result.skipped)})
    if not result.wasSuccessful() or result.skipped:
        raise SystemExit("scenario failed or skipped prerequisites")
(OUT / "scenarios.json").write_text(json.dumps(reports, indent=2) + "\n")
