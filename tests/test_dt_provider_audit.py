"""Host checks for scripts/audit-dt-providers.py and the report behind it.

The audit exists because five of this port's defects were the same shape and were
each found by hand.  These checks are deliberately about the *tool's* failure
modes, because every one of them made the audit say "fine" when it was not:

* the `alias=of:` modalias is the module-autoload key, not the binding test, and
  its `C*` form means "further compatibles follow", not "any compatible with this
  prefix" - read as a prefix it made `qcom,sm8550-llcc-bwmon` match the LLCC
  controller's `qcom,sm8550-llcc` and hid a real gap;
* a built driver with no ``MODULE_DEVICE_TABLE(of, ...)`` contributes no alias at
  all (``qcom,pcie-sm8550`` with ``CONFIG_PCIE_QCOM=y``);
* a file merely *mentioning* a compatible is not its driver
  (``drivers/of/platform.c``'s ``reserved_mem_matches[]`` lists
  ``"qcom,rmtfs-mem"`` to create a platform device for the carve-out);
* ``grep -E`` has no non-capturing groups, so a ``(?:...)`` alternation matches
  nothing and every gap collapses to "no driver source".
"""
import importlib.util
import json
import pathlib
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]

SCRIPT = "scripts/audit-dt-providers.py"
DOC = "docs/DT_PROVIDER_AUDIT.md"
DTB = "out/kernel-gts9wifi/sm8550-samsung-gts9wifi.dtb"
MODINFO = ".work/build/linux-out/modules.builtin.modinfo"

_AUDIT_CACHE = {}

_SPEC = importlib.util.spec_from_file_location("dt_provider_audit", ROOT / SCRIPT)
AUDIT = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(AUDIT)


def read(rel):
    return (ROOT / rel).read_text()


def audit():
    """Run the audit once per process, or skip without the build artifacts.

    Pass 2 scans the kernel tree once. Share the report across result tests;
    isolated synthetic trees below exercise fresh input and scan failures.
    """
    if "report" in _AUDIT_CACHE:
        report = _AUDIT_CACHE["report"]
        if report is None:
            raise unittest.SkipTest("no built kernel artifacts to audit")
        return report
    if not (ROOT / DTB).is_file() or not (ROOT / MODINFO).is_file():
        _AUDIT_CACHE["report"] = None
        raise unittest.SkipTest("no built kernel artifacts to audit")
    proc = subprocess.run(
        ["python3", str(ROOT / SCRIPT), "--json"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if proc.returncode not in (0, 1):
        raise AssertionError(f"audit failed: {proc.stderr}")
    _AUDIT_CACHE["report"] = json.loads(proc.stdout)
    return _AUDIT_CACHE["report"]


class AuditScriptTests(unittest.TestCase):
    def test_it_is_executable_and_compiles(self):
        path = ROOT / SCRIPT
        self.assertTrue(path.stat().st_mode & 0o111)
        subprocess.run(["python3", "-m", "py_compile", str(path)], check=True)


class DriverIndexTests(unittest.TestCase):
    """Use actual source files and both search engines, without a kernel build."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.tree = pathlib.Path(self.temp.name)
        for directory in AUDIT.SEARCH_DIRS:
            (self.tree / directory).mkdir(parents=True)

    def write(self, name, text):
        path = self.tree / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def scan(self, backend):
        if backend == "rg" and not shutil.which("rg"):
            self.skipTest("rg unavailable; grep fallback is tested separately")
        executable = shutil.which("rg") if backend == "rg" else None
        with mock.patch.object(AUDIT.shutil, "which", return_value=executable):
            return AUDIT.driver_source_index(self.tree)

    def test_both_engines_preserve_exact_declarations_and_exclusions(self):
        self.write("drivers/test.c", '.compatible = "vendor,chip"; .compatible = "vendor,chip.v1+rev";\n')
        self.write("drivers/macros.c", 'IRQCHIP_MATCH("vendor,irq", init)\n'
                   'TIMER_OF_DECLARE(timer, "vendor,timer", init)\n'
                   'CLK_OF_DECLARE(clk, "vendor,clock", init)\n')
        self.write("drivers/of/platform.c", '.compatible = "vendor,not-a-driver";\n')
        self.write("drivers/mentions.c", 'const char *name = "vendor,bare-mention";\n')
        self.write("drivers/.hidden.c", '.compatible = "vendor,hidden";\n')
        self.write("drivers/space name.c", '.compatible = "vendor,space";\n')
        self.write("drivers/ignored.c", '.compatible = "vendor,ignored";\n')
        self.write("drivers/.ignore", "ignored.c\n")
        self.write("drivers/header.h", '.compatible = "vendor,header";\n')
        expected = {
            "vendor,chip": [pathlib.Path("drivers/test.c")],
            "vendor,chip.v1+rev": [pathlib.Path("drivers/test.c")],
            "vendor,irq": [pathlib.Path("drivers/macros.c")],
            "vendor,timer": [pathlib.Path("drivers/macros.c")],
            "vendor,clock": [pathlib.Path("drivers/macros.c")],
            "vendor,hidden": [pathlib.Path("drivers/.hidden.c")],
            "vendor,space": [pathlib.Path("drivers/space name.c")],
            "vendor,ignored": [pathlib.Path("drivers/ignored.c")],
        }
        for backend in ("grep", "rg"):
            with self.subTest(backend=backend):
                index = self.scan(backend)
                self.assertEqual(index, expected)
                self.assertEqual(AUDIT.driver_sources(self.tree, "vendor,chip-extra", index), [])
                self.assertEqual(AUDIT.driver_sources(self.tree, "vendor,chipXv1+rev", index), [])

    def test_empty_result_is_valid_but_scan_errors_are_not(self):
        self.write("drivers/empty.c", "int unrelated;\n")
        for backend in ("grep", "rg"):
            with self.subTest(backend=backend):
                self.assertEqual(self.scan(backend), {})
        (self.tree / "sound").rmdir()
        for backend in ("grep", "rg"):
            with self.subTest(backend=backend):
                with self.assertRaisesRegex(RuntimeError, "scan failed"):
                    self.scan(backend)

    def test_one_scan_per_audit_and_new_invocations_see_source_edits(self):
        self.write("drivers/test.c", '.compatible = "vendor,original";\n')
        with mock.patch.object(AUDIT.subprocess, "run", wraps=subprocess.run) as scan:
            index = AUDIT.driver_source_index(self.tree)
            for _ in range(5):
                self.assertEqual(AUDIT.driver_sources(self.tree, "vendor,original", index),
                                 [pathlib.Path("drivers/test.c")])
            self.assertEqual(scan.call_count, 1)
            self.write("drivers/test.c", '.compatible = "vendor,updated";\n')
            fresh = AUDIT.driver_source_index(self.tree)
            self.assertEqual(scan.call_count, 2)
            self.assertNotIn("vendor,original", fresh)
            self.assertIn("vendor,updated", fresh)

    def test_fallback_compatible_and_config_classification_still_work(self):
        self.write("drivers/test.c", '.compatible = "vendor,generic";\n')
        self.write("drivers/Makefile", "obj-$(CONFIG_TEST_PROVIDER) += test.o\n")
        index = AUDIT.driver_source_index(self.tree)
        for value, expected in (("y", "built_no_alias"), ("m", "module_only"), ("n", "symbol_off")):
            with self.subTest(config=value):
                result = AUDIT.classify(self.tree, {"TEST_PROVIDER": value}, set(),
                                        ["vendor,specific", "vendor,generic"], index)
                self.assertEqual(result["kind"], expected)
                self.assertEqual(result["sources"], [["drivers/test.c", "TEST_PROVIDER", value, "vendor,generic"]])


class AuditResultTests(unittest.TestCase):
    def setUp(self):
        self.report = audit()
        self.by_compatible = {
            entry["compatible"]: entry
            for entry in self.report["known_gaps"] + self.report["unknown"]
        }
        self.late = {e["compatible"]: e
                     for e in self.report["bound_without_alias"]}

    def test_nothing_is_unclassified(self):
        """An empty UNKNOWN set is the gate; a new node must fail loudly."""
        self.assertEqual(self.report["unknown"], [])

    def test_pcie_is_not_reported_as_a_gap(self):
        """CONFIG_PCIE_QCOM=y with no MODULE_DEVICE_TABLE: bound, not a gap."""
        self.assertNotIn("qcom,pcie-sm8550", self.by_compatible)
        self.assertIn("qcom,pcie-sm8550", self.late)
        sources = self.late["qcom,pcie-sm8550"]["second_source"]["sources"]
        self.assertTrue(any(s[1] == "PCIE_QCOM" and s[2] == "y" for s in sources))

    def test_rmtfs_mem_is_reported_as_a_real_gap(self):
        """drivers/of/platform.c mentions it and is not its driver."""
        entry = self.by_compatible.get("qcom,rmtfs-mem")
        self.assertIsNotNone(entry, "rmtfs-mem must be reported")
        source = entry["second_source"]
        self.assertNotEqual(source["kind"], "built_no_alias")
        symbols = {s[1]: s[2] for s in source["sources"]}
        self.assertEqual(symbols.get("QCOM_RMTFS_MEM"), "n")
        self.assertNotIn("obj-y", symbols)

    def test_llcc_bwmon_is_not_hidden_by_the_llcc_controller(self):
        """`qcom,sm8550-llcc` must not swallow `qcom,sm8550-llcc-bwmon`.

        This is the exact false "bound" the prefix bug produced, and it hid one of
        the two findings this audit exists to report.
        """
        entry = self.by_compatible.get("qcom,sm8550-llcc-bwmon")
        self.assertIsNotNone(entry, "llcc-bwmon must be reported")
        sources = entry["second_source"]["sources"]
        self.assertTrue(any(s[0].endswith("icc-bwmon.c") for s in sources))
        self.assertFalse(any(s[0].endswith("llcc.c") for s in sources))

    def test_the_cpu_path_bandwidth_monitors_are_reported(self):
        """The finding that made this worth automating."""
        for compatible in ("qcom,sm8550-cpu-bwmon", "qcom,sm8550-llcc-bwmon"):
            with self.subTest(compatible=compatible):
                entry = self.by_compatible.get(compatible)
                self.assertIsNotNone(entry, f"{compatible} must be reported")
                self.assertIn("CONFIG_QCOM_ICC_BWMON", entry["note"])
                self.assertIn("upstream defconfig has it =m", entry["note"])
                symbols = {s[1]: s[2]
                           for s in entry["second_source"]["sources"]}
                self.assertEqual(symbols.get("QCOM_ICC_BWMON"), "n")

    def test_the_module_only_trap_is_distinguished_from_n(self):
        """`=m` yields no driver here; the report must not blur it with `=n`."""
        kinds = {(e["second_source"] or {}).get("kind")
                 for e in self.report["known_gaps"]}
        self.assertIn("module_only", kinds)
        self.assertIn("symbol_off", kinds)


if __name__ == "__main__":
    unittest.main()
