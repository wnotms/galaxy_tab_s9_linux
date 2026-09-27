"""Exercise changed-test selection against real temporary Git repositories."""

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("test_impact", ROOT / "scripts/test-impact.py")
IMPACT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(IMPACT)


class ChangedTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.git("init", "-q")
        self.write(".gitignore", "out/\n__pycache__/\n")
        self.write("scripts/a.py", "# source a\n")
        self.write("README.md", "workflow\n")
        self.write("tests/test_a.py", "import unittest\nclass A(unittest.TestCase):\n def test_ok(self): pass\n")
        self.write("tests/test_b.py", "import unittest\nclass B(unittest.TestCase):\n def test_bad(self): self.fail('fixture failure')\n")
        self.write("tests/suites.json", '{"classes": {}, "tests": {}}')
        self.manifest = {"rules": [
            {"paths": ["scripts/a.py"], "selectors": ["test_a"], "reason": "fixture behavior"},
            {"paths": ["README.md"], "selectors": [], "reason": "fixture prose"},
        ]}
        self.write("tests/change-impact.json", json.dumps(self.manifest))
        for name in ("run-host-tests.py", "test-impact.py", "check-stall-offline.sh"):
            shutil.copy2(ROOT / "scripts" / name, self.root / "scripts" / name)
        self.write("scripts/lib/fixture.sh", "#!/bin/sh\n:\n")
        self.write("boot/fixture.sh", "#!/bin/sh\n:\n")
        self.commit()

    def git(self, *args):
        return IMPACT.git(self.root, *args)

    def write(self, path, text):
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)

    def commit(self):
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "fixture")

    def cases(self, *names):
        class Case:
            def __init__(self, name):
                self.name = name

            def id(self):
                return self.name
        return [Case(name) for name in names]

    def cli(self, *args):
        report = self.root / "out/result.json"
        report.unlink(missing_ok=True)
        result = subprocess.run([sys.executable, str(self.root / "scripts/run-host-tests.py"),
                                 "changed", "--report", str(report), *args],
                                cwd=self.root, capture_output=True, text=True, timeout=10)
        return result, json.loads(report.read_text()) if report.exists() else None

    def wrapper(self, *args):
        return subprocess.run(["bash", str(self.root / "scripts/check-stall-offline.sh"), *args],
                              cwd=self.root, capture_output=True, text=True, timeout=10)

    def test_git_collects_staged_unstaged_untracked_and_cancelled_edits(self):
        self.write("scripts/a.py", "staged change\n")
        self.git("add", "scripts/a.py")
        self.write("scripts/a.py", "# source a\n")  # worktree cancels the index change
        self.write("README.md", "unstaged\n")
        unusual = "new file\twith\nnewline.py"
        self.write(unusual, "untracked\n")
        self.write("out/ignored.py", "ignored\n")
        revision, paths = IMPACT.changed_paths(self.root)
        self.assertEqual(len(revision), 40)
        self.assertEqual(set(paths), {"scripts/a.py", "README.md", unusual})

    def test_rename_keeps_both_paths_and_deletion_forces_all(self):
        self.git("mv", "scripts/a.py", "scripts/renamed.py")
        _, paths = IMPACT.changed_paths(self.root)
        self.assertEqual(set(paths), {"scripts/a.py", "scripts/renamed.py"})
        tests = self.cases("test_a.A.test_ok", "test_b.B.test_bad")
        selected, report = IMPACT.select(self.root, tests, paths, self.manifest)
        self.assertEqual(selected, tests)
        self.assertTrue(report["fallback_all"])

    def test_explicit_base_includes_committed_changes_and_invalid_base_fails(self):
        base, paths = IMPACT.changed_paths(self.root)
        self.assertEqual(paths, [])
        self.write("scripts/a.py", "committed change\n")
        self.commit()
        self.assertEqual(IMPACT.changed_paths(self.root)[1], [])
        self.assertEqual(IMPACT.changed_paths(self.root, base)[1], ["scripts/a.py"])
        result = self.wrapper("--changed", "--base", base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("selected=1,", result.stderr)
        with self.assertRaises(ValueError):
            IMPACT.changed_paths(self.root, "not-a-ref")
        result, report = self.cli("--base", "not-a-ref")
        self.assertEqual(result.returncode, 2)
        self.assertIsNone(report)

    def test_test_helper_changes_include_transitive_consumers(self):
        self.write("tests/test_b.py", "from test_a import A\n")
        self.write("tests/test_c.py", "import test_b\n")
        self.write("tests/test_d.py", "from tests import test_c\n")
        self.write("tests/test_e.py", "from . import test_d\n")
        tests = self.cases("test_a.A.test_ok", "test_b.B.test_bad", "test_c.C.test_c",
                           "test_d.D.test_d", "test_e.E.test_e", "test_other.F.test_f")
        selected, report = IMPACT.select(self.root, tests, ["tests/test_a.py"], self.manifest)
        self.assertEqual(selected, tests[:5])
        self.assertFalse(report["fallback_all"])

    def test_unknown_path_selects_all_and_stale_map_is_an_error(self):
        tests = self.cases("test_a.A.test_ok", "test_b.B.test_bad")
        self.write("scripts/new-helper.py", "# unknown dependency\n")
        selected, report = IMPACT.select(self.root, tests, ["scripts/new-helper.py"], self.manifest)
        self.assertEqual(selected, tests)
        self.assertTrue(report["fallback_all"])
        self.manifest["rules"][0]["selectors"] = ["test_missing"]
        with self.assertRaises(ValueError):
            IMPACT.select(self.root, tests, [], self.manifest)

    def test_cli_executes_only_mapped_tests_and_propagates_failures(self):
        self.write("scripts/a.py", "changed\n")
        result, report = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["selected"], ["test_a.A.test_ok"])
        self.assertEqual(report["tests_run"], 1)
        self.assertFalse(report["change_selection"]["fallback_all"])
        wrapped = self.wrapper()
        self.assertEqual(wrapped.returncode, 0, wrapped.stderr)
        self.assertIn("selected=1,", wrapped.stderr)
        self.assertEqual(self.wrapper("--core", "--base", "HEAD").returncode, 2)
        self.write("unmapped.txt", "unknown\n")
        result, report = self.cli()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertTrue(report["change_selection"]["fallback_all"])
        self.assertEqual(report["failures"], ["test_b.B.test_bad"])
        result, report = self.cli("--list")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(report["executed"])
        self.assertEqual(len(report["selected"]), 2)

    def test_cli_clean_and_reviewed_docs_report_no_tests_not_a_passed_suite(self):
        result, report = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(report["executed"])
        self.assertEqual(report["selected"], [])
        self.assertIn("No changed paths", report["no_tests_reason"])
        self.write("README.md", "new workflow text\n")
        result, report = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(report["executed"])
        self.assertIn("documentation", report["no_tests_reason"])

    def test_import_failure_cannot_hide_behind_unrelated_mapping(self):
        self.write("tests/test_bad_import.py", "raise RuntimeError('fixture import error')\n")
        self.commit()
        self.write("scripts/a.py", "changed\n")
        result, report = self.cli()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(len(report["errors"]), 1)
        self.assertIn("test_bad_import", report["errors"][0])

    def test_empty_discovery_is_an_error_even_in_changed_mode(self):
        (self.root / "tests/test_a.py").unlink()
        (self.root / "tests/test_b.py").unlink()
        result, report = self.cli()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIsNone(report)
        self.assertIn("no tests discovered", result.stderr)
