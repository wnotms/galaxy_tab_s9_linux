"""Exercise the actual patched Debian C client against synthetic sysfs/procfs."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('acpi_build', ROOT / 'userspace/acpi/build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class AcpiPowerSupplyCapacityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.TemporaryDirectory()
        cls.output = Path(cls.work.name) / 'build'
        build.build('host', cls.output)
        cls.binary = cls.output / 'acpi'

    @classmethod
    def tearDownClass(cls):
        cls.work.cleanup()

    def battery(self, values, *args):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            battery = root / 'power_supply' / 'BAT0'
            battery.mkdir(parents=True)
            for name, value in dict(type='Battery', status='Discharging', **values).items():
                (battery / name).write_text(str(value) + '\n')
            return subprocess.check_output([str(self.binary), '-b', '-d', str(root), *args], text=True)

    def test_real_x710_shape_uses_reported_capacity(self):
        text = self.battery(dict(capacity=75, current_now=-1062000,
                                 voltage_now=4098000, charge_full_design=8160000), '-i')
        self.assertIn('Discharging, 75%', text)
        self.assertIn('time information unavailable', text)
        self.assertIn('design capacity 8160 mAh, last full capacity unavailable', text)
        self.assertNotIn('-81 mAh', text)
        self.assertNotIn('= 100%', text)  # No invented learned capacity/health.

    def test_reported_zero_is_valid(self):
        self.assertIn('0%', self.battery(dict(capacity=0)))

    def test_reported_full_is_valid(self):
        self.assertIn('100%', self.battery(dict(capacity=100)))

    def test_gauge_percentage_preferred_to_charge_ratio(self):
        text = self.battery(dict(capacity=75, charge_now=4000000, charge_full=8000000))
        self.assertIn('75%', text)
        self.assertNotIn('50%', text)

    def test_missing_capacity_preserves_charge_ratio_and_time(self):
        text = self.battery(dict(charge_now=4000000, charge_full=8000000, current_now=-1000000))
        self.assertIn('50%, 04:00:00 remaining', text)

    def test_invalid_percentage_falls_back_to_real_charge(self):
        for value in ['-1', '101', '75x', '75.5', 'unknown', '99999999999999999999999']:
            with self.subTest(value=value):
                text = self.battery(dict(capacity=value, charge_now=4000000, charge_full=8000000))
                self.assertIn('50%', text)

    def test_invalid_percentage_without_charge_is_unknown(self):
        text = self.battery(dict(capacity='bad'))
        self.assertIn('capacity information unavailable', text)
        self.assertNotIn('0%', text)

    def test_missing_remaining_charge_does_not_estimate_from_percentage(self):
        text = self.battery(dict(capacity=75, charge_full=8000000, current_now=-1000000))
        self.assertIn('75%, time information unavailable', text)

    def test_missing_full_charge_does_not_compute_charging_time(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            battery = root / 'power_supply/BAT0'
            battery.mkdir(parents=True)
            for key, value in dict(type='Battery', status='Charging', capacity=75,
                                   charge_now=4000000, current_now=1000000).items():
                (battery / key).write_text(str(value) + '\n')
            text = subprocess.check_output([str(self.binary), '-b', '-d', str(root)], text=True)
            self.assertIn('Charging, 75%, time information unavailable', text)

    def test_energy_battery_keeps_existing_ratio_and_time(self):
        text = self.battery(dict(energy_now=20000000, energy_full=40000000,
                                 power_now=5000000, voltage_now=4000000))
        self.assertIn('50%, 04:00:00 remaining', text)

    def test_legacy_proc_interface(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            battery = root / 'battery/BAT0'
            battery.mkdir(parents=True)
            (battery / 'info').write_text('last full capacity: 8000 mAh\ndesign capacity: 8160 mAh\n')
            (battery / 'state').write_text('charging state: discharging\nremaining capacity: 4000 mAh\npresent rate: 1000 mA\n')
            text = subprocess.check_output([str(self.binary), '-b', '-p', '-d', str(root)], text=True)
            self.assertIn('50%, 04:00:00 remaining', text)

    def test_adapter_is_not_reported_as_battery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = root / 'power_supply/AC'
            adapter.mkdir(parents=True)
            (adapter / 'type').write_text('USB\n')
            (adapter / 'online').write_text('1\n')
            text = subprocess.check_output([str(self.binary), '-b', '-d', str(root)], text=True)
            self.assertEqual(text, '')


if __name__ == '__main__':
    unittest.main()
