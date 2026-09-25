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
import json
import pathlib
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]

SCRIPT = "scripts/audit-dt-providers.py"
DOC = "docs/DT_PROVIDER_AUDIT.md"
DTB = "out/kernel-gts9wifi/sm8550-samsung-gts9wifi.dtb"
MODINFO = ".work/build/linux-out/modules.builtin.modinfo"

_AUDIT_CACHE = {}


def read(rel):
    return (ROOT / rel).read_text()


def audit():
    """Run the audit once per process, or skip without the build artifacts.

    Pass 2 greps the kernel tree, so this costs tens of seconds; running it per
    test class would dominate the suite for no extra signal.
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

    def test_it_requires_a_declaration_not_a_mention(self):
        text = read(SCRIPT)
        self.assertIn(".compatible", text)
        self.assertIn("*DECLARE", text)
        self.assertIn("*MATCH", text)
        self.assertIn("reserved_mem_matches", text)

    def test_it_has_no_compatible_prefix_matching(self):
        """The modalias `C*` form is not a string prefix."""
        text = read(SCRIPT)
        self.assertIn("There is no prefix logic here", text)
        self.assertIn("llcc-bwmon", text)

    def test_it_uses_plain_groups_in_grep_patterns(self):
        """`(?:` in a grep -E pattern matches nothing, silently.

        Python regexes elsewhere in the file may use `(?:...)` freely; what must
        not is the pattern handed to grep, which is POSIX ERE.
        """
        text = read(SCRIPT)
        self.assertIn("non-capturing groups", text)
        self.assertIn("? at start of expression", text)
        # The pattern handed to grep must not contain one.
        pattern_lines = [line for line in text.splitlines()
                         if line.strip().startswith("pattern = ")]
        self.assertTrue(pattern_lines, "no grep pattern found")
        self.assertNotIn("(?:", "\n".join(pattern_lines))


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


class AuditDocTests(unittest.TestCase):
    def contains(self, *needles):
        text = read(DOC)
        missing = [n for n in needles if n not in text]
        self.assertEqual(missing, [], f"{DOC} is missing {missing}")

    def test_it_names_the_pattern_and_where_it_comes_from(self):
        self.contains(
            "expresses Qualcomm platform support as **modules**",
            "no module tree",
            "CONFIG_INTERCONNECT_QCOM_OSM_L3=m",
            "CONFIG_QCOM_ICC_BWMON=m",
        )

    def test_it_records_all_three_traps(self):
        self.contains("The modalias is not the binding test",
                      "A driver can be built and contribute no alias",
                      "Mentioning a compatible is not declaring it",
                      "no non-capturing groups")

    def test_it_records_the_makefile_idioms(self):
        self.contains("composite objects", "objects built by an ancestor Makefile",
                      "arm_smmu-objs", "disp/dpu1/dpu_kms.o")

    def test_it_distinguishes_eq_m_from_eq_n_and_from_eq_y(self):
        self.contains("this port installs no module tree, so `=m` yields no driver",
                      "`m` means the symbol **is** requested")

    def test_it_names_the_second_cpu_path_gap_as_its_own_candidate(self):
        self.contains(
            "24091000.pmu",
            "240b6400.pmu",
            "not* bundled into test-191",
            "byte-identical to what is flashed",
        )

    def test_it_states_its_own_limits(self):
        self.contains("a gap is a question, not a verdict",
                      "That any of these gaps causes the CPU wedge")


if __name__ == "__main__":
    unittest.main()
