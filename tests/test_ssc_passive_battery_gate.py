"""Exercise amended Test379 admission at both deployment and RPC boundaries."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'reference/boot-tests/test-379-ssc-rpc-stat'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


H = load('ssc379_admission_host', R / 'host_flow.py')
M = load('ssc379_admission_runtime', R / 'runtime.py')


class PassiveBatteryGateTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'reference/boot-tests/test-377-ssc-userspace-pd-mapper/runtime-discovery/boundary.txt').read_text())
        self.plan = H.PLAN | {'boot_id': self.data['boot_id']}

    def check(self, data):
        H.identity(data, 'candidate', data['boot_id'])
        M.validate(data, self.plan)

    def test_full_battery_above_float_setpoint_admitted_both_boundaries(self):
        self.data['battery']['POWER_SUPPLY_CAPACITY'] = '100'
        for value in ('4440000', '4444000', '4447000', '4450000'):
            with self.subTest(voltage=value):
                self.data['battery']['POWER_SUPPLY_VOLTAGE_NOW'] = value
                self.check(self.data)

    def test_outside_observation_voltage_bounds_stops_both_boundaries(self):
        for value in ('3399999', '4450001', '4600000', '0', '-1'):
            with self.subTest(voltage=value):
                data = copy.deepcopy(self.data)
                data['battery']['POWER_SUPPLY_VOLTAGE_NOW'] = value
                for checker in (lambda: H.identity(data, 'candidate'), lambda: M.validate(data, self.plan)):
                    with self.assertRaises(ValueError):
                        checker()

    def test_invalid_or_missing_voltage_not_waived_by_good_health(self):
        for value in ('unknown', '', None):
            data = copy.deepcopy(self.data)
            data['battery']['POWER_SUPPLY_VOLTAGE_NOW'] = value
            for checker in (lambda: H.identity(data, 'candidate'), lambda: M.validate(data, self.plan)):
                with self.assertRaises((ValueError, TypeError)):
                    checker()
        del self.data['battery']['POWER_SUPPLY_VOLTAGE_NOW']
        with self.assertRaises(KeyError):
            self.check(self.data)

    def test_health_temperature_presence_and_design_still_stop(self):
        cases = [('POWER_SUPPLY_HEALTH', 'Over voltage'),
                 ('POWER_SUPPLY_HEALTH', 'Unknown'),
                 ('POWER_SUPPLY_PRESENT', '0'),
                 ('POWER_SUPPLY_TEMP', '420'),
                 ('POWER_SUPPLY_TEMP', '99'),
                 ('POWER_SUPPLY_CAPACITY', '19'),
                 ('POWER_SUPPLY_CAPACITY', '101'),
                 ('POWER_SUPPLY_VOLTAGE_MAX_DESIGN', '4450000')]
        for key, value in cases:
            data = copy.deepcopy(self.data)
            data['battery'][key] = value
            for checker in (lambda: H.identity(data, 'candidate'), lambda: M.validate(data, self.plan)):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    checker()

    def test_gate_uses_registration_for_host_and_runtime(self):
        self.assertEqual(self.plan['voltage_observation_max_uv'], 4450000)
        self.assertFalse(self.plan['PPS'])
        self.assertFalse(self.plan['pump_ON'])
        self.assertFalse(self.plan['charging_limits_changed'])
        self.assertEqual(H.PACKAGE['write_partitions'], ['vendor_boot'])
        self.assertEqual(H.PACKAGE['candidate_partitions']['boot'], H.PACKAGE['baseline_partitions']['boot'])
        self.assertEqual(H.PLAN['candidate_config_sha256'], H.PLAN['baseline_config_sha256'])


if __name__ == '__main__':
    unittest.main()
