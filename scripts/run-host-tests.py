#!/usr/bin/env python3
"""Reviewed host test tiers. Unclassified/new tests always run in core."""

import argparse
import json
import os
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
TIERS = ("core", "artifacts", "archive")


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def partition(suite, manifest):
    tests = list(flatten(suite))
    ids = [test.id() for test in tests]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate discovered test IDs")
    classes = {name.rsplit(".", 1)[0] for name in ids}
    if set(manifest) != {"classes", "tests"}:
        raise ValueError("manifest must contain classes and tests")
    for kind, known in (("classes", classes), ("tests", set(ids))):
        for selector, rule in manifest[kind].items():
            if selector not in known:
                raise ValueError(f"stale/unknown {kind} selector: {selector}")
            fields = {"suite", "reason", "members"} if kind == "classes" else {"suite", "reason"}
            if set(rule) != fields or rule["suite"] not in TIERS or not rule["reason"].strip():
                raise ValueError(f"invalid tier/reason: {selector}")
            if kind == "classes":
                members = rule["members"]
                if not isinstance(members, list) or not members or any(not isinstance(member, str) for member in members):
                    raise ValueError(f"invalid reviewed members: {selector}")
                if len(members) != len(set(members)) or any(f"{selector}.{member}" not in ids for member in members):
                    raise ValueError(f"duplicate/stale reviewed members: {selector}")
    groups = {name: [] for name in TIERS}
    for test in tests:
        name = test.id()
        class_name, method = name.rsplit(".", 1)
        rule = manifest["tests"].get(name)
        if rule is None:
            class_rule = manifest["classes"].get(class_name)
            if class_rule is not None and method in class_rule["members"]:
                rule = class_rule
        # Import failures must fail even the default run, irrespective of routing.
        tier = "core" if rule is None or isinstance(test, unittest.loader._FailedTest) else rule["suite"]
        groups[tier].append(test)
    return groups


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", nargs="?", choices=(*TIERS, "all"), default="core")
    parser.add_argument("--list", action="store_true", help="list IDs without executing tests")
    parser.add_argument("--report", type=Path, help="write selection, results and wall time as JSON")
    parser.add_argument("--fail-on-skip", action="store_true", help="require all selected prerequisites")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    os.chdir(ROOT)
    started = time.perf_counter()
    try:
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
        groups = partition(suite, json.loads((ROOT / "tests/suites.json").read_text()))
    except (ValueError, OSError, TypeError) as error:
        parser.error(str(error))
    selected = [test for tier in TIERS for test in groups[tier]] if args.suite == "all" else groups[args.suite]
    if not selected:
        parser.error("empty test selection")
    report = {"suite": args.suite, "counts": {tier: len(group) for tier, group in groups.items()},
              "selected": [test.id() for test in selected], "executed": False}
    print(f"Host suite={args.suite}: selected={len(selected)}, tiers={report['counts']}", file=sys.stderr)
    code = 0
    if args.list:
        print("\n".join(report["selected"]))
    else:
        result = unittest.TextTestRunner(verbosity=2 if args.verbose else 1).run(unittest.TestSuite(selected))
        report.update(executed=True, tests_run=result.testsRun,
                      failures=[test.id() for test, _ in result.failures],
                      errors=[test.id() for test, _ in result.errors],
                      skipped=[{"id": test.id(), "reason": reason} for test, reason in result.skipped],
                      expected_failures=[test.id() for test, _ in result.expectedFailures],
                      unexpected_successes=[test.id() for test in result.unexpectedSuccesses])
        code = int(not result.wasSuccessful() or (args.fail_on_skip and bool(result.skipped)))
        if args.fail_on_skip and result.skipped:
            print("Required tests were skipped; refusing a complete validation verdict.", file=sys.stderr)
    report.update(elapsed_s=round(time.perf_counter() - started, 3), exit_code=code)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
