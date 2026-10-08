"""Host tests for the identity-gated optional pen loader."""
import gzip
import importlib.util
import io
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "userspace/gnome/pen/load.py"


def load_module():
    spec = importlib.util.spec_from_file_location("gts9_pen_loader", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PenLoaderTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.root = Path(tempfile.mkdtemp())
        for path in (
            "proc/sys/kernel",
            "sys/firmware/devicetree/base",
            "sys/kernel",
            "sys/module",
            "sys/bus/i2c/devices/6-0056/of_node",
            "sys/class/power_supply/sm5714-battery",
            "usr/local/lib/gts9-desktop",
        ):
            (self.root / path).mkdir(parents=True, exist_ok=True)
        (self.root / "proc/sys/kernel/random").mkdir(parents=True)
        (self.root / "proc/sys/kernel/random/boot_id").write_text("boot-362\n")
        (self.root / "sys/firmware/devicetree/base/compatible").write_bytes(b"samsung,gts9wifi\0")
        (self.root / "proc/cmdline").write_text("console=tty0\n")
        (self.root / "sys/kernel/notes").write_bytes(b"notes")
        config = b"CONFIG_TEST=y\n"
        (self.root / "proc/config.gz").write_bytes(gzip.compress(config))
        self.module.PROFILE["config_sha256"] = self.module._sha(config)
        self.module.PROFILE["notes_sha256"] = self.module._sha(b"notes")
        (self.root / "sys/bus/i2c/devices/6-0056/of_node/compatible").write_bytes(b"wacom,w90xx\0")
        (self.root / "sys/class/power_supply/sm5714-battery/health").write_text("Good\n")
        (self.root / "sys/class/power_supply/sm5714-battery/temp").write_text("250\n")
        self.module.MODULE = Path("/usr/local/lib/gts9-desktop/wacom-wez01.ko")
        (self.root / "usr/local/lib/gts9-desktop/wacom-wez01.ko").write_bytes(b"module")
        self.module.PROFILE["module_sha256"] = self.module._sha(b"module")

    def test_already_loaded_bound_input_needs_no_insmod(self):
        (self.root / "sys/module/wacom_wez01").mkdir()
        client = self.root / "sys/bus/i2c/devices/6-0056"
        driver = self.root / "sys/bus/i2c/drivers/wacom-wez01"
        driver.mkdir(parents=True)
        (client / "driver").symlink_to(driver)
        (client / "input/input5").mkdir(parents=True)
        (client / "input/input5/event5").touch()
        result = self.module.inspect(self.root, machine="aarch64",
                                     release=self.module.PROFILE["release"])
        self.assertEqual(result["status"], "already-loaded")
        self.assertEqual(self.module.run(True, inspect_state=lambda: result)["insmod_attempts"], 0)

    def test_unqualified_kernel_skips_without_reading_module(self):
        result = self.module.inspect(self.root, machine="x86_64",
                                     release=self.module.PROFILE["release"])
        self.assertEqual(result["status"], "skipped")

    def test_charging_experiment_skips(self):
        (self.root / "proc/cmdline").write_text("sm5440_direct.direct_charge=1\n")
        result = self.module.inspect(self.root, machine="aarch64",
                                     release=self.module.PROFILE["release"])
        self.assertEqual(result["status"], "skipped")
        self.assertIn("charging", result["reason"])

    def test_unbound_client_is_ready_after_safety_gate(self):
        result = self.module.inspect(self.root, machine="aarch64",
                                     release=self.module.PROFILE["release"])
        self.assertEqual(result["status"], "ready")

    def test_bad_temperature_is_error_for_qualified_kernel(self):
        (self.root / "sys/class/power_supply/sm5714-battery/temp").write_text("420\n")
        result = self.module.inspect(self.root, machine="aarch64",
                                     release=self.module.PROFILE["release"])
        self.assertEqual(result["status"], "error")
        self.assertIn("safety", result["reason"])

    def test_loader_source_has_no_force_or_firmware_operations(self):
        source = SOURCE.read_text()
        self.assertNotIn("--force", source)
        self.assertNotIn("request_firmware", source)
        self.assertIn("insmod_attempts", source)


if __name__ == "__main__":
    unittest.main()
