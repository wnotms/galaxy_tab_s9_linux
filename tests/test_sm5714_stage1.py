"""The battery candidate gate rejects unrelated production-profile changes."""

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_sm5714_stage1", ROOT / "scripts/verify-sm5714-stage1.py")
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


class Stage1CandidateGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name) / "base"
        self.candidate = Path(self.temp.name) / "candidate"
        self.base.mkdir()
        self.candidate.mkdir()
        (self.base / "config").write_text(
            "# CONFIG_HVC_DCC is not set\n"
            "# CONFIG_QCOM_SPMI_ADC5_GEN3 is not set\n"
            "CONFIG_POWER_SUPPLY=y\n")
        (self.candidate / "config").write_text(
            "# CONFIG_HVC_DCC is not set\n"
            "CONFIG_QCOM_SPMI_ADC5_GEN3=y\n"
            "CONFIG_BATTERY_SM5714=y\n"
            "CONFIG_POWER_SUPPLY=y\n")
        (self.base / VERIFY.DTB).write_bytes(b"accepted board")
        (self.candidate / VERIFY.DTB).write_bytes(b"accepted board")

    def result(self):
        return VERIFY.verify(self.base, self.candidate)

    def test_exact_stage1_delta_passes(self):
        result = self.result()
        self.assertTrue(result["valid"])
        self.assertEqual(result["config_delta"], VERIFY.EXPECTED_DELTA)

    def test_unrelated_or_diagnostic_config_fails(self):
        with (self.candidate / "config").open("a") as stream:
            stream.write("CONFIG_ARM64_PSEUDO_NMI=y\n")
        self.assertFalse(self.result()["valid"])

    def test_dcc_reenable_fails_even_if_other_deltas_are_expected(self):
        config = self.candidate / "config"
        config.write_text(config.read_text().replace(
            "# CONFIG_HVC_DCC is not set", "CONFIG_HVC_DCC=y"))
        self.assertFalse(self.result()["valid"])

    def test_changed_dtb_fails(self):
        (self.candidate / VERIFY.DTB).write_bytes(b"changed board")
        self.assertFalse(self.result()["valid"])


if __name__ == "__main__":
    unittest.main()
