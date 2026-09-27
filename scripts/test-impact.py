#!/usr/bin/env python3
"""Conservative, reviewed test selection from local Git changes. No network."""

import ast
import json
from pathlib import Path
import subprocess
import unittest


def git(root, *args):
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, check=False)
    if result.returncode:
        raise ValueError(f"git {args[0]} failed: {result.stderr.decode(errors='replace').strip()}")
    return result.stdout


def changed_paths(root, base="HEAD"):
    """Include committed changes since base, staged/unstaged edits and untracked files.

    Disable rename detection to retain BOTH sides, including the deleted source.
    Diff index and worktree separately so cancelling staged/unstaged edits count.
    NUL records retain spaces, tabs and newlines in file names.
    """
    revision = git(root, "rev-parse", "--verify", "--end-of-options", base + "^{commit}").decode().strip()
    paths = set()
    for args in (("diff", "--cached", "--name-only", "--no-renames", "-z", revision, "--"),
                 ("diff", "--name-only", "--no-renames", "-z", "--"),
                 ("ls-files", "--others", "--exclude-standard", "-z")):
        paths.update(value.decode(errors="surrogateescape") for value in git(root, *args).split(b"\0") if value)
    return revision, sorted(paths)


def matches(test, selector):
    return test.id() == selector or test.id().startswith(selector + ".")


def dependents(root, modules):
    """Static imports among test modules, including transitive helper consumers."""
    def module_name(name):
        parts = name.split(".")
        return parts[1] if len(parts) > 1 and parts[0] == "tests" else parts[0]

    imports = {}
    for path in sorted((root / "tests").glob("test_*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        dependencies = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                dependencies.update(module_name(alias.name) for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module == "tests" or (node.level and node.module is None):
                    dependencies.update(module_name(alias.name) for alias in node.names)
                elif node.module:
                    dependencies.add(module_name(node.module))
        imports[path.stem] = dependencies
    result = set(modules)
    while True:
        more = {name for name, dependencies in imports.items() if dependencies & result}
        if more <= result:
            return result
        result |= more


def select(root, tests, paths, manifest):
    """Return selected tests and auditable reasons; an unknown path selects all."""
    if not isinstance(manifest, dict) or set(manifest) != {"rules"} or not isinstance(manifest["rules"], list):
        raise ValueError("impact manifest must contain a rules list")
    rules = {}
    for rule in manifest["rules"]:
        if not isinstance(rule, dict) or set(rule) != {"paths", "selectors", "reason"}:
            raise ValueError("invalid impact rule")
        if not isinstance(rule["reason"], str) or not rule["reason"].strip():
            raise ValueError("impact rule needs a reason")
        if not isinstance(rule["selectors"], list) or not isinstance(rule["paths"], list) or not rule["paths"]:
            raise ValueError("impact rule needs paths and selectors lists")
        for selector in rule["selectors"]:
            if not isinstance(selector, str) or not selector or not any(matches(test, selector) for test in tests):
                raise ValueError(f"stale/unknown impact selector: {selector}")
        for path in rule["paths"]:
            if not isinstance(path, str) or not path or Path(path).is_absolute() or ".." in Path(path).parts:
                raise ValueError("impact paths must be relative to the repository")
            if path in rules:
                raise ValueError(f"duplicate impact path: {path}")
            if not (root / path).is_file() and path not in paths:
                raise ValueError(f"stale impact path: {path}")
            rules[path] = rule
    reasons = []
    selectors = set()
    changed_modules = set()
    fallback = False
    for path in paths:
        rule = rules.get(path)
        file = root / path
        if not file.is_file():
            fallback = True
            reasons.append({"path": path, "reason": "Deleted/renamed source or non-file: run all tests."})
        elif path.startswith("tests/test_") and path.endswith(".py") and file.parent == root / "tests":
            module = file.stem
            if any(matches(test, module) for test in tests):
                changed_modules.add(module)
                reasons.append({"path": path, "reason": "Changed test module and its static import consumers."})
            else:
                fallback = True
                reasons.append({"path": path, "reason": "Undiscovered test/helper module: run all tests."})
        elif rule is not None:
            selectors.update(rule["selectors"])
            reasons.append({"path": path, "reason": rule["reason"], "selectors": rule["selectors"]})
        else:
            fallback = True
            reasons.append({"path": path, "reason": "No reviewed dependency rule: run all tests."})
    if changed_modules:
        selectors.update(dependents(root, changed_modules))
    selected = [test for test in tests if fallback or isinstance(test, unittest.loader._FailedTest)
                or any(matches(test, selector) for selector in selectors)]
    return selected, {"paths": paths, "fallback_all": fallback, "selectors": sorted(selectors), "reasons": reasons}


def from_git(root, tests, base):
    revision, paths = changed_paths(root, base)
    manifest = json.loads((root / "tests/change-impact.json").read_text())
    selected, report = select(root, tests, paths, manifest)
    report["base"] = revision
    return selected, report
