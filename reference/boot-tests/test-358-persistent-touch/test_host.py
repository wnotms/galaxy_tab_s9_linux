"""Execute touch loader gates/one-shot behavior with an isolated sysfs fixture."""
import gzip
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("touch_loader", ROOT / "userspace/gnome/touch/load.py")
loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loader)
QUALIFIED_PROFILE = dict(loader.PROFILE)


class TouchLoader(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.put("proc/sys/kernel/random/boot_id", "accepted-boot")
        self.put("proc/cmdline", "console=tty0 nowatchdog")
        self.put("sys/firmware/devicetree/base/compatible", b"samsung,gts9wifi\0qcom,sm8550\0")
        self.put("proc/config.gz", gzip.compress(b"approved config"))
        self.put("sys/kernel/notes", b"approved notes")
        self.put(str(loader.MODULE).lstrip("/"), b"approved module")
        self.put("sys/bus/i2c/devices/7-0049/of_node/compatible", b"st,fts1ba90a\0")
        self.put("sys/bus/i2c/devices/2-0049/of_node/compatible", b"siliconmitus,sm5714-charger\0")
        self.put("sys/class/power_supply/sm5714-battery/health", "Good")
        self.put("sys/class/power_supply/sm5714-battery/temp", "328")
        profile = dict(loader.PROFILE, config_sha256=loader.digest(b"approved config"),
                       notes_sha256=loader.digest(b"approved notes"),
                       module_sha256=loader.digest(b"approved module"))
        self.profile_patch = patch.object(loader, "PROFILE", profile)
        self.profile_patch.start()
        self.addCleanup(self.profile_patch.stop)

    def put(self, name, data):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data.encode() if isinstance(data, str) else data)

    def inspect(self):
        return loader.inspect(self.root, machine="aarch64", release=loader.PROFILE["release"])

    def bind(self):
        (self.root / "sys/module/fts1ba90a").mkdir(parents=True)
        (self.root / "sys/bus/i2c/drivers/fts1ba90a").mkdir(parents=True)
        (self.root / "sys/bus/i2c/devices/7-0049/driver").symlink_to("../../drivers/fts1ba90a")
        (self.root / "sys/bus/i2c/devices/7-0049/input/input4/event4").mkdir(parents=True)
        self.put("sys/bus/i2c/devices/7-0049/double_tap_to_wake", "0")

    def test_current_qualification_matches_real_artifacts(self):
        for key, file in [("config_sha256", "out/kernel-x710-fedora-snapshot-fix/config"),
                          ("notes_sha256", "out/kernel-x710-fedora-snapshot-fix/kernel-notes.bin"),
                          ("module_sha256", "out/gnome-trixie-arm64/touch-module/fts1ba90a.ko")]:
            self.assertEqual(loader.digest((ROOT / file).read_bytes()), QUALIFIED_PROFILE[key])
        config = (ROOT / "out/kernel-x710-fedora-snapshot-fix/config").read_text()
        self.assertIn("# CONFIG_HVC_DCC is not set", config)
        self.assertIn("CONFIG_USER_NS=y", config)

    def test_qualified_existing_client_ignores_charger_same_address(self):
        result = self.inspect()
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["client"], "7-0049")

    def test_same_release_wrong_notes_or_config_is_skipped(self):
        for name, data in [("sys/kernel/notes", b"Test348 notes"),
                           ("proc/config.gz", gzip.compress(b"changed config"))]:
            with self.subTest(name=name):
                original = (self.root / name).read_bytes()
                self.put(name, data)
                self.assertEqual(self.inspect()["status"], "skipped")
                self.put(name, original)

    def test_wrong_board_arch_or_release_is_skipped(self):
        for machine, release in [("x86_64", loader.PROFILE["release"]), ("aarch64", "different")]:
            self.assertEqual(loader.inspect(self.root, machine=machine, release=release)["status"], "skipped")
        self.put("sys/firmware/devicetree/base/compatible", b"samsung,gts9ultra\0")
        self.assertEqual(self.inspect()["status"], "skipped")

    def test_charging_opt_ins_skip_before_module_check(self):
        (self.root / str(loader.MODULE).lstrip("/")).unlink()
        for flag in ("sm5440_fedora.direct_charge=1", "sm5440_fedora.direct_charge_once=1",
                     "sm5440_fedora.pps_return_check=1", "sm5440_fedora.fixed_return_check=1",
                     "sm5440_direct.direct_charge=1", "lpcharge=1"):
            with self.subTest(flag=flag):
                self.put("proc/cmdline", flag)
                self.assertEqual(self.inspect()["status"], "skipped")

    def test_missing_and_corrupt_identity_skip_without_loading(self):
        self.put("proc/config.gz", b"bad gzip")
        self.assertEqual(self.inspect()["status"], "skipped")
        (self.root / "sys/kernel/notes").unlink()
        self.assertEqual(self.inspect()["status"], "skipped")

    def test_wrong_module_hash_is_error(self):
        self.put(str(loader.MODULE).lstrip("/"), b"wrong module")
        self.assertEqual(self.inspect()["status"], "error")

    def test_ambiguous_or_missing_touch_client_is_error(self):
        self.put("sys/bus/i2c/devices/8-0049/of_node/compatible", b"st,fts1ba90a\0")
        self.assertEqual(self.inspect()["status"], "error")
        for name in ("7-0049", "8-0049"):
            (self.root / "sys/bus/i2c/devices" / name / "of_node/compatible").unlink()
        self.assertEqual(self.inspect()["status"], "error")

    def test_battery_sensor_invalid_or_hot_stops_new_load(self):
        for temperature in ("420", "-1", "invalid"):
            self.put("sys/class/power_supply/sm5714-battery/temp", temperature)
            self.assertEqual(self.inspect()["status"], "error")
        self.put("sys/class/power_supply/sm5714-battery/temp", "328")
        self.put("sys/class/power_supply/sm5714-battery/health", "Unknown")
        self.assertEqual(self.inspect()["status"], "error")

    def test_readonly_and_already_loaded_never_call_insmod(self):
        invoke = Mock(side_effect=AssertionError("insmod must not run"))
        self.assertEqual(loader.run(False, inspect_state=self.inspect, invoke=invoke)["status"], "ready")
        self.bind()
        result = loader.run(True, inspect_state=self.inspect, invoke=invoke)
        self.assertEqual(result["status"], "already-loaded")
        self.assertEqual(result["insmod_attempts"], 0)
        invoke.assert_not_called()

    def test_unqualified_identity_never_calls_insmod(self):
        self.put("sys/kernel/notes", b"unapproved")
        invoke = Mock()
        self.assertEqual(loader.run(True, inspect_state=self.inspect, invoke=invoke)["status"], "skipped")
        invoke.assert_not_called()

    def test_doubletap_or_loaded_unbound_module_is_error(self):
        self.bind()
        self.put("sys/bus/i2c/devices/7-0049/double_tap_to_wake", "1")
        self.assertEqual(self.inspect()["status"], "error")
        (self.root / "sys/bus/i2c/devices/7-0049/driver").unlink()
        self.assertTrue(self.inspect()["probe_pending"])

    def test_one_normal_load_then_async_probe_ready(self):
        def invoke(argv, **kwargs):
            self.assertEqual(argv, ["/sbin/insmod", str(loader.MODULE)])
            self.bind()
            return subprocess.CompletedProcess(argv, 0, "", "")
        runner = Mock(side_effect=invoke)
        result = loader.run(True, inspect_state=self.inspect, invoke=runner)
        self.assertEqual(result["status"], "loaded")
        self.assertEqual(result["insmod_attempts"], 1)
        runner.assert_called_once()

    def test_loader_failure_or_timeout_is_terminal_without_retry(self):
        for response in (subprocess.CompletedProcess([], 1, "", "bad CRC"),
                         subprocess.TimeoutExpired("insmod", 8)):
            invoke = Mock(side_effect=response) if isinstance(response, Exception) else Mock(return_value=response)
            result = loader.run(True, inspect_state=self.inspect, invoke=invoke)
            self.assertEqual(result["status"], "error")
            self.assertEqual(result["insmod_attempts"], 1)
            invoke.assert_called_once()

    def test_probe_timeout_has_no_reload_or_unload(self):
        ready = self.inspect()
        pending = dict(ready, status="error", probe_pending=True, reason="unbound")
        inspect_state = Mock(side_effect=[ready, pending])
        invoke = Mock(return_value=subprocess.CompletedProcess([], 0, "", ""))
        result = loader.run(True, inspect_state=inspect_state, invoke=invoke,
                            clock=Mock(side_effect=[0, 6]))
        self.assertEqual(result["status"], "error")
        invoke.assert_called_once()

    def test_boot_change_during_load_is_terminal(self):
        ready = self.inspect()
        inspect_state = Mock(side_effect=[ready, dict(ready, status="already-loaded", boot_id="new-boot")])
        invoke = Mock(return_value=subprocess.CompletedProcess([], 0, "", ""))
        self.assertEqual(loader.run(True, inspect_state=inspect_state, invoke=invoke)["status"], "error")
        invoke.assert_called_once()

    def test_real_systemd_unit_syntax(self):
        target = self.root / "gts9-touch.service"
        target.write_bytes((ROOT / "userspace/gnome/touch/gts9-touch.service").read_bytes())
        # ExecStart's Python is installed on the host; the loader is an argument.
        result = subprocess.run(["systemd-analyze", "verify", str(target)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
