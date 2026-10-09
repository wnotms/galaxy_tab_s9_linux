"""Focused offline gates for Test373's one missing Fedora userspace dependency."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'reference/boot-tests/test-373-ssc-userspace-pd-mapper'


class SSCUserspacePdMapperScopeTests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads((R / 'registration.json').read_text())
        self.packages = json.loads((R / 'runtime-packages.json').read_text())
        self.runtime = (R / 'runtime.py').read_text()
        self.desktop = json.loads((R / 'desktop-manifest.json').read_text())

    def test_scope_is_userspace_only(self):
        self.assertEqual(self.plan['test'], 'Test373')
        self.assertFalse(self.plan['PPS'])
        self.assertFalse(self.plan['pump_ON'])
        self.assertEqual(self.plan['write_partitions'], ['vendor_boot'])
        self.assertEqual(self.plan['candidate_config_sha256'], self.plan['baseline_config_sha256'])

    def test_exact_mapper_dependency_set(self):
        rows = {row['package']: row for row in self.packages}
        self.assertEqual(set(rows), {'libprotobuf-c1', 'libssc2', 'gts9-hexagonrpc',
                                     'iio-sensor-proxy', 'libqrtr1', 'pd-mapper'})
        self.assertEqual(rows['pd-mapper']['version'], '1.1+gts9.1')
        self.assertEqual(rows['libqrtr1']['version'], '1.1-2+b1')
        for name in ('pd-mapper', 'libqrtr1'):
            self.assertRegex(rows[name]['sha256'], r'^[0-9a-f]{64}$')
            self.assertGreater(rows[name]['bytes'], 0)

    def test_mapper_starts_before_sensor_daemons(self):
        self.assertIn("systemctl','start','--no-block','pd-mapper.service", self.runtime)
        self.assertIn("UNITS[1:-1]", self.runtime)
        self.assertLess(self.runtime.index("pd-mapper.service"), self.runtime.index("UNITS[1:-1]"))

    def test_mapper_is_owned_and_removed_on_cleanup(self):
        self.assertIn("dpkg','--unpack", self.runtime)
        self.assertIn("dpkg','--purge','pd-mapper','libqrtr1", self.runtime)
        self.assertIn("disable','--now','pd-mapper.service", self.runtime)

    def test_overlay_has_no_old_test372_namespace(self):
        self.assertTrue(all('test372' not in (key + json.dumps(value)) for key, value in self.desktop.items()))
        self.assertIn('gts9-test373', json.dumps(self.desktop))

    def test_no_hardware_or_charging_scope(self):
        text = (R / 'README.md').read_text()
        for forbidden in ('SM5440', 'charging pump', 'charging_limits_changed'):
            self.assertNotIn(forbidden, text)


if __name__ == '__main__':
    unittest.main()
