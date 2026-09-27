"""Test suite routing and verdicts using executable synthetic test cases."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("host_suites", ROOT / "scripts/run-host-tests.py")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class SuiteSelectionTests(unittest.TestCase):
    def fixtures(self):
        class Sample(unittest.TestCase):
            def test_pass(self):
                pass

            def test_fail(self):
                self.fail("deliberate fixture failure")

            def test_skip(self):
                self.skipTest("missing fixture artifact")

        return [Sample(name) for name in ("test_pass", "test_fail", "test_skip")]

    def test_disjoint_complete_and_new_tests_default_to_core(self):
        tests = self.fixtures()
        rule = lambda tier: {"suite": tier, "reason": "fixture"}
        class_rule = dict(rule("archive"), members=["test_pass", "test_fail"])
        manifest = {"classes": {tests[0].id().rsplit(".", 1)[0]: class_rule},
                    "tests": {tests[1].id(): rule("core"), tests[2].id(): rule("artifacts")}}
        groups = RUNNER.partition(unittest.TestSuite([unittest.TestSuite(tests)]), manifest)
        self.assertEqual(groups, {"core": [tests[1]], "artifacts": [tests[2]], "archive": [tests[0]]})
        # A new method in a previously reviewed class must still default to core.
        del manifest["tests"][tests[2].id()]
        self.assertEqual(RUNNER.partition(unittest.TestSuite(tests), manifest)["core"], tests[1:])
        self.assertEqual(RUNNER.partition(unittest.TestSuite(tests), {"classes": {}, "tests": {}})["core"], tests)

    def test_stale_selector_invalid_tier_and_duplicate_ids_fail(self):
        tests = self.fixtures()
        for kind, selector, rule in (
            ("tests", "missing.test", {"suite": "archive", "reason": "fixture"}),
            ("classes", "missing.Class", {"suite": "archive", "reason": "fixture"}),
            ("tests", tests[0].id(), {"suite": "typo", "reason": "fixture"}),
            ("tests", tests[0].id(), {"suite": "archive", "reason": ""}),
            ("classes", tests[0].id().rsplit(".", 1)[0],
             {"suite": "archive", "reason": "fixture", "members": ["test_missing"]}),
            ("classes", tests[0].id().rsplit(".", 1)[0],
             {"suite": "archive", "reason": "fixture", "members": ["test_pass", "test_pass"]}),
        ):
            manifest = {"classes": {}, "tests": {}}
            manifest[kind][selector] = rule
            with self.subTest(selector=selector, rule=rule), self.assertRaises(ValueError):
                RUNNER.partition(unittest.TestSuite(tests), manifest)
        with self.assertRaises(ValueError):
            RUNNER.partition(unittest.TestSuite([tests[0], tests[0]]), {"classes": {}, "tests": {}})

    def run_fixture(self, tests, *args):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.json"
            with mock.patch.object(RUNNER.unittest.defaultTestLoader, "discover", return_value=unittest.TestSuite(tests)), \
                 mock.patch.object(RUNNER.json, "loads", return_value={"classes": {}, "tests": {}}), \
                 contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                code = RUNNER.main([*args, "--report", str(report)])
            return code, json.loads(report.read_text())

    def test_failed_test_propagates_to_exit_and_report(self):
        code, report = self.run_fixture(self.fixtures()[:2], "all")
        self.assertEqual(code, 1)
        self.assertEqual(report["tests_run"], 2)
        self.assertEqual(report["failures"], [self.fixtures()[1].id()])

    def test_skip_is_reported_and_strict_mode_fails(self):
        for args, expected in (([], 0), (["--fail-on-skip"], 1)):
            code, report = self.run_fixture([self.fixtures()[2]], *args)
            self.assertEqual(code, expected)
            self.assertEqual(report["skipped"][0]["reason"], "missing fixture artifact")

    def test_list_does_not_execute_failure_fixture(self):
        code, report = self.run_fixture([self.fixtures()[1]], "--list")
        self.assertEqual(code, 0)
        self.assertFalse(report["executed"])
        self.assertEqual(report["selected"], [self.fixtures()[1].id()])

    def test_discovery_import_failure_cannot_be_hidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "test_bad_import.py").write_text("raise RuntimeError('broken import')\n")
            suite = unittest.TestLoader().discover(tmp)
            failed = list(RUNNER.flatten(suite))[0]
            groups = RUNNER.partition(suite, {"classes": {}, "tests": {
                failed.id(): {"suite": "archive", "reason": "must not hide import error"}}})
            self.assertEqual(groups["core"], [failed])
            result = unittest.TestResult()
            failed.run(result)
            self.assertEqual(len(result.errors), 1)
