import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('native_mapper_snapshot', ROOT / 'userspace/sensors/native-mapper-snapshot.py')
mapper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mapper)
BOOT = '78ec1906-4713-4837-9acc-fe245647d7cf'
OTHER = '98ec1906-4713-4837-9acc-fe245647d7cf'


class NativeMapperSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        boot = self.root / 'proc/sys/kernel/random/boot_id'
        boot.parent.mkdir(parents=True)
        boot.write_text(BOOT + '\n')
        self.bus = self.root / 'sys/bus/auxiliary'
        self.driver = self.bus / 'drivers' / mapper.DRIVER
        self.driver.mkdir(parents=True)
        (self.bus / 'devices').mkdir()

    def device(self, suffix='0', driver=True):
        name = 'qcom_common.pd-mapper.' + suffix
        actual = self.root / 'sys/devices/platform/remoteproc' / name
        actual.mkdir(parents=True)
        (actual / 'modalias').write_text('auxiliary:qcom_common.pd-mapper\n')
        (self.bus / 'devices' / name).symlink_to(actual)
        if driver:
            (actual / 'driver').symlink_to(self.driver)
        return actual

    def capture(self):
        return mapper.snapshot(self.root, expected_boot=BOOT)

    def test_bound_on_auxiliary_bus_does_not_prove_service_response(self):
        self.device()
        result = self.capture()
        self.assertEqual(result['binding_state'], 'bound')
        self.assertEqual(result['devices'][0]['driver_path'], str(self.driver))
        self.assertFalse(result['service_response_verified'])
        self.assertFalse(result['sensor_discovery_verified'])

    def test_no_device_is_not_binding_pass(self):
        self.assertEqual(self.capture()['binding_state'], 'no-device')

    def test_absent_driver_is_reported(self):
        self.driver.rmdir()
        self.assertFalse(self.capture()['driver_registered'])

    def test_unbound_device(self):
        self.device(driver=False)
        self.assertEqual(self.capture()['binding_state'], 'unbound')

    def test_wrong_driver_is_not_accepted(self):
        device = self.device(driver=False)
        wrong = self.bus / 'drivers/wrong'
        wrong.mkdir()
        (device / 'driver').symlink_to(wrong)
        self.assertEqual(self.capture()['binding_state'], 'unexpected-binding')

    def test_all_devices_must_be_bound(self):
        self.device('0')
        self.device('1', driver=False)
        self.assertNotEqual(self.capture()['binding_state'], 'bound')

    def test_malformed_device_name(self):
        self.device('bad')
        with self.assertRaisesRegex(ValueError, 'unexpected PD-mapper'):
            self.capture()

    def test_broken_driver_link_fails_evidence(self):
        device = self.device(driver=False)
        (device / 'driver').symlink_to(self.bus / 'drivers/missing')
        with self.assertRaises(FileNotFoundError):
            self.capture()

    def test_wrong_boot_before_reading_sysfs(self):
        with self.assertRaisesRegex(ValueError, 'before'):
            mapper.snapshot(self.root, expected_boot=OTHER)

    def test_boot_change_during_snapshot(self):
        self.device()
        with patch.object(mapper, 'boot_id', side_effect=[BOOT, OTHER]):
            with self.assertRaisesRegex(ValueError, 'during'):
                self.capture()

    def test_old_platform_path_does_not_substitute_for_auxiliary_binding(self):
        old = self.root / 'sys/bus/platform/drivers/qcom-pd-mapper'
        old.mkdir(parents=True)
        self.assertEqual(self.capture()['binding_state'], 'no-device')

    def test_read_only_snapshot_keeps_fixture_bytes_and_links(self):
        self.device()
        def inventory():
            return {str(p.relative_to(self.root)): ('link', str(p.readlink())) if p.is_symlink()
                    else ('file', p.read_bytes()) for p in self.root.rglob('*')
                    if p.is_symlink() or p.is_file()}
        before = inventory()
        self.capture()
        self.assertEqual(before, inventory())


if __name__ == '__main__':
    unittest.main()
