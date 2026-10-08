"""Identity and collision gates for the opt-in paired S Pen loader."""
import gzip
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "userspace/gnome/palm/load.py"


def module():
    spec = importlib.util.spec_from_file_location("gts9_palm_loader", SOURCE)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class PalmLoaderTests(unittest.TestCase):
    def setUp(self):
        self.m = module()
        self.root = Path(tempfile.mkdtemp())
        for path in ("proc/sys/kernel/random", "sys/firmware/devicetree/base",
                     "sys/kernel", "sys/module", "sys/bus/i2c/devices/6-0056/of_node",
                     "sys/bus/i2c/devices/7-0049/of_node",
                     "sys/class/power_supply/sm5714-battery",
                     "usr/local/lib/gts9-desktop"):
            (self.root / path).mkdir(parents=True, exist_ok=True)
        (self.root / "proc/sys/kernel/random/boot_id").write_text("boot-363\n")
        (self.root / "sys/firmware/devicetree/base/compatible").write_bytes(b"samsung,gts9wifi\0")
        (self.root / "proc/cmdline").write_text("console=tty0\n")
        config = b"CONFIG_TEST=y\n"
        (self.root / "proc/config.gz").write_bytes(gzip.compress(config))
        (self.root / "sys/kernel/notes").write_bytes(b"notes")
        self.m.PROFILE["config_sha256"] = self.m.digest(config)
        self.m.PROFILE["notes_sha256"] = self.m.digest(b"notes")
        (self.root / "sys/bus/i2c/devices/6-0056/of_node/compatible").write_bytes(b"wacom,w90xx\0")
        (self.root / "sys/bus/i2c/devices/7-0049/of_node/compatible").write_bytes(b"st,fts1ba90a\0")
        (self.root / "sys/class/power_supply/sm5714-battery/health").write_text("Good\n")
        (self.root / "sys/class/power_supply/sm5714-battery/temp").write_text("250\n")
        (self.root / "usr/local/lib/gts9-desktop/wacom-wez01.ko").write_bytes(b"pen")
        (self.root / "usr/local/lib/gts9-desktop/fts1ba90a-palm.ko").write_bytes(b"touch")
        self.m.PEN = Path("/usr/local/lib/gts9-desktop/wacom-wez01.ko")
        self.m.TOUCH = Path("/usr/local/lib/gts9-desktop/fts1ba90a-palm.ko")
        self.m.PROFILE["pen_sha256"] = self.m.digest(b"pen")
        self.m.PROFILE["touch_sha256"] = self.m.digest(b"touch")

    def test_unbound_exact_pair_is_ready(self):
        result = self.m.inspect(self.root, machine="aarch64", release=self.m.PROFILE["release"])
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["insmod_attempts"], 0)

    def test_unqualified_and_charging_boots_skip(self):
        self.assertEqual(self.m.inspect(self.root, machine="x86_64",
                                         release=self.m.PROFILE["release"])["status"], "skipped")
        (self.root / "proc/cmdline").write_text("sm5440_direct.direct_charge=1\n")
        result = self.m.inspect(self.root, machine="aarch64", release=self.m.PROFILE["release"])
        self.assertEqual(result["status"], "skipped")
        self.assertIn("charging", result["reason"])

    def test_existing_ordinary_touch_is_never_replaced(self):
        (self.root / "sys/module/fts1ba90a").mkdir()
        result = self.m.inspect(self.root, machine="aarch64", release=self.m.PROFILE["release"])
        self.assertEqual(result["status"], "error")
        self.assertIn("already loaded", result["reason"])

    def test_bound_pair_is_only_accepted_for_post_load_poll(self):
        (self.root / "sys/module/wacom_wez01").mkdir()
        (self.root / "sys/module/fts1ba90a").mkdir()
        for device, name in (("6-0056", "wacom-wez01"), ("7-0049", "fts1ba90a")):
            driver = self.root / "sys/bus/i2c/drivers" / name
            driver.mkdir(parents=True)
            client = self.root / "sys/bus/i2c/devices" / device
            (client / "driver").symlink_to(driver)
        result = self.m.inspect(self.root, machine="aarch64", release=self.m.PROFILE["release"], allow_pair=True)
        self.assertEqual(result["status"], "already-loaded-pair")

    def test_source_orders_pen_before_touch_and_has_no_force_load(self):
        source = SOURCE.read_text()
        self.assertLess(source.index("for module in (PEN, TOUCH)"), source.index("normal loader rejected pair"))
        self.assertNotIn("--force", source)
        self.assertIn("do not replace accepted touch module", source)


if __name__ == "__main__":
    unittest.main()
