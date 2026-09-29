"""Resolved OCI config, fail-closed build gate and exact-delta regressions.

Host only. No Docker daemon, device transport or runtime sysctl is invoked.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "container_config", ROOT / "scripts/verify-container-config.py")
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)
BASE = ROOT / "reference/boot-tests/test-252-sm5714-stage1/validation/candidate.config"


class ContainerKernelConfigTests(unittest.TestCase):
    def setUp(self):
        self.before = BASE.read_text()
        self.config = GATE.read_config(self.before)
        self.config.update({k: "y" for k in GATE.REQUIRED_Y})
        self.config.update({k: "n" for k in GATE.BLOCKED_NEW_ON})
        self.text = self.render(self.config)

    @staticmethod
    def render(config):
        return "".join(f"# {k} is not set\n" if v == "n" else f"{k}={v}\n"
                       for k, v in sorted(config.items()))

    def test_test252_fixture_matches_accepted_manifest_and_latest_embedded_config(self):
        manifest = json.loads((BASE.parents[1] / "ARTIFACTS.json").read_text())
        self.assertEqual(hashlib.sha256(BASE.read_bytes()).hexdigest(),
                         manifest["kernel_artifacts"]["config"])
        latest = ROOT / ("reference/boot-tests/test-253-adbd-usb-reconnect/"
                         "attempt-04/final-acceptance/embedded-config.txt")
        self.assertEqual(BASE.read_bytes(), latest.read_bytes())

    def test_existing_baseline_fails_missing_userns_and_container_features(self):
        result = GATE.verify(self.before)
        self.assertFalse(result["valid"])
        self.assertTrue(any("CONFIG_USER_NS" in e for e in result["errors"]))
        self.assertTrue(result["dcc_absent"])

    def test_complete_prerequisites_pass(self):
        self.assertTrue(GATE.verify(self.text)["valid"])

    def test_missing_each_namespace_resource_and_network_prerequisite_fails(self):
        for symbol in GATE.REQUIRED_Y:
            with self.subTest(symbol=symbol):
                config = dict(self.config)
                config.pop(symbol)
                self.assertFalse(GATE.verify(self.render(config))["valid"])

    def test_required_feature_as_module_does_not_satisfy_builtin_gate(self):
        for symbol in ("CONFIG_USER_NS", "CONFIG_NFT_NAT", "CONFIG_MACVLAN"):
            with self.subTest(symbol=symbol):
                config = {**self.config, symbol: "m"}
                self.assertFalse(GATE.verify(self.render(config))["valid"])

    def test_nft_family_without_expressions_fails(self):
        config = {**self.config, "CONFIG_NFT_NAT": "n", "CONFIG_NFT_COMPAT": "n"}
        self.assertFalse(GATE.verify(self.render(config))["valid"])

    def test_old_iptables_symbol_does_not_replace_linux72_legacy_parents(self):
        for parent in ("CONFIG_NETFILTER_XTABLES_LEGACY",
                       "CONFIG_IP_NF_IPTABLES_LEGACY", "CONFIG_IP6_NF_IPTABLES_LEGACY"):
            with self.subTest(parent=parent):
                self.assertFalse(GATE.verify(self.render({**self.config, parent: "n"}))["valid"])

    def test_dcc_cannot_be_restored_as_builtin_or_module(self):
        for value in ("y", "m"):
            with self.subTest(value=value):
                result = GATE.verify(self.render({**self.config, "CONFIG_HVC_DCC": value}))
                self.assertFalse(result["valid"])
                self.assertFalse(result["dcc_absent"])

    def test_invisible_disabled_symbol_is_not_required_to_have_a_comment(self):
        config = dict(self.config)
        config.pop("CONFIG_HVC_DCC")
        self.assertTrue(GATE.verify(self.render(config))["valid"])

    def test_sm5714_and_thermistor_provider_remain_required(self):
        for symbol in GATE.PRESERVE_Y:
            with self.subTest(symbol=symbol):
                self.assertFalse(GATE.verify(self.render({**self.config, symbol: "n"}))["valid"])

    def test_conflicting_assignments_fail_closed(self):
        with self.assertRaises(ValueError):
            GATE.verify(self.text + "# CONFIG_USER_NS is not set\n")

    def test_empty_config_fails(self):
        self.assertFalse(GATE.verify("")["valid"])

    def test_opened_menus_cannot_restore_unrelated_stock_requests(self):
        for symbol in GATE.BLOCKED_NEW_ON:
            with self.subTest(symbol=symbol):
                self.assertFalse(GATE.verify(self.render({**self.config, symbol: "y"}))["valid"])

    def test_exact_reviewed_delta_passes(self):
        expected = GATE.delta(GATE.read_config(self.before), self.config)
        result = GATE.verify(self.text, self.before, expected)
        self.assertTrue(result["valid"])
        self.assertEqual(result["unexpected_delta"], {})

    def test_unrelated_hardware_change_fails_exact_delta(self):
        expected = GATE.delta(GATE.read_config(self.before), self.config)
        for symbol in ("CONFIG_USB_DWC3", "CONFIG_ARM_QCOM_CPUFREQ_HW", "CONFIG_ATH11K"):
            with self.subTest(symbol=symbol):
                result = GATE.verify(self.render({**self.config, symbol: "n"}), self.before, expected)
                self.assertFalse(result["valid"])
                self.assertIn(symbol, result["unexpected_delta"])

    def test_missing_expected_change_fails(self):
        expected = GATE.delta(GATE.read_config(self.before), self.config)
        expected["CONFIG_FAKE_UNREVIEWED_SYMBOL"] = ["absent", "n"]
        result = GATE.verify(self.text, self.before, expected)
        self.assertFalse(result["valid"])
        self.assertIn("CONFIG_FAKE_UNREVIEWED_SYMBOL", result["missing_expected_delta"])

    def test_absent_and_explicit_disabled_are_distinct_in_exact_diff(self):
        self.assertEqual(GATE.delta({}, {"CONFIG_FOO": "n"}),
                         {"CONFIG_FOO": ["absent", "n"]})

    def test_expected_delta_without_baseline_is_rejected(self):
        with self.assertRaises(ValueError):
            GATE.verify(self.text, expected_delta={})

    def test_cli_saves_full_diff_and_machine_verdict(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            config = path / "config"
            config.write_text(self.text)
            expected = path / "expected.json"
            expected.write_text(json.dumps(GATE.delta(GATE.read_config(self.before), self.config)))
            result = subprocess.run(["python3", str(SPEC.origin), str(config),
                                     "--baseline", str(BASE), "--expected-delta", str(expected),
                                     "--report", str(path / "report.json"),
                                     "--diff", str(path / "config.diff")],
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads((path / "report.json").read_text())["valid"])
            self.assertIn("+CONFIG_USER_NS=y", (path / "config.diff").read_text())

    def test_cli_missing_config_fails(self):
        result = subprocess.run(["python3", str(SPEC.origin), "/nonexistent/container-config"],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)

    def test_build_gate_executes_after_olddefconfig_before_compilation(self):
        script = (ROOT / "scripts/build-kernel.sh").read_text()
        call = 'python3 "$repo_root/scripts/verify-container-config.py" "$build_dir/.config"'
        self.assertGreater(script.index(call), script.index("ARCH=arm64 LLVM=1 olddefconfig"))
        self.assertLess(script.index(call), script.index('Image.gz qcom/sm8550-samsung-gts9wifi.dtb'))
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / ".config"
            for text, code in ((self.text, 0), (self.before, 1)):
                config.write_text(text)
                result = subprocess.run(["bash", "-c", call],
                                        env={"PATH": "/usr/bin:/bin", "repo_root": str(ROOT),
                                             "build_dir": temp}, capture_output=True, timeout=5)
                self.assertEqual(result.returncode, code, result.stderr)

    def test_fragment_and_existing_seed_cover_required_features(self):
        resolved_requests = GATE.read_config(self.before)
        resolved_requests.update(GATE.read_config(
            (ROOT / "kernel/config/gts9wifi-mainline.fragment").read_text()))
        # NFT_FIB has no prompt: family providers select it at olddefconfig.
        # The actual candidate test below checks that resolution separately.
        for symbol in GATE.REQUIRED_Y - {"CONFIG_NFT_FIB"}:
            with self.subTest(symbol=symbol):
                self.assertEqual(resolved_requests.get(symbol), "y")
        self.assertEqual(resolved_requests["CONFIG_HVC_DCC"], "n")

    def test_actual_candidate_resolved_config_passes(self):
        config = ROOT / "out/kernel-container-candidate/config"
        self.assertTrue(config.is_file(), "build the isolated container candidate first")
        self.assertTrue(GATE.verify(config.read_text())["valid"])

    def test_actual_candidate_has_only_the_reviewed_exact_delta(self):
        validation = ROOT / "reference/boot-tests/test-254-debian-container-kernel/validation"
        config = ROOT / "out/kernel-container-candidate/config"
        expected = json.loads((validation / "expected-delta.json").read_text())
        result = GATE.verify(config.read_text(), self.before, expected)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["unexpected_delta"], {})
        before = GATE.read_config(self.before)
        after = GATE.read_config(config.read_text())
        for symbol in ("CONFIG_SECURITY_APPARMOR", "CONFIG_SECURITY_SELINUX",
                       "CONFIG_CHECKPOINT_RESTORE", "CONFIG_IP_SCTP", "CONFIG_CGROUP_HUGETLB"):
            with self.subTest(symbol=symbol):
                self.assertEqual(before.get(symbol), after.get(symbol))


if __name__ == "__main__":
    unittest.main()
