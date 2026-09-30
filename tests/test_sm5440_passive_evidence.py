import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('passive', ROOT / 'scripts/sm5440_passive_evidence.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class PassiveEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.battery = {'POWER_SUPPLY_HEALTH': 'Good', 'POWER_SUPPLY_PRESENT': '1',
                        'POWER_SUPPLY_CAPACITY': '56', 'POWER_SUPPLY_TEMP': '281',
                        'POWER_SUPPLY_VOLTAGE_NOW': '3899000'}
        self.passive = {'POWER_SUPPLY_HEALTH': 'Good', 'POWER_SUPPLY_STATUS': 'Not charging',
                        'POWER_SUPPLY_ONLINE': '1', 'POWER_SUPPLY_TEMP': '285',
                        'POWER_SUPPLY_VOLTAGE_NOW': '5000000', 'POWER_SUPPLY_CURRENT_NOW': '0'}

    def errors(self, role='[sink]', data='[device]'):
        return p.passive_errors(self.battery, self.passive, role, data)

    def test_reported_passive_sample_clean(self):
        self.assertEqual(self.errors(), [])

    def test_missing_adc_field_stops(self):
        for key in ('POWER_SUPPLY_VOLTAGE_NOW', 'POWER_SUPPLY_CURRENT_NOW', 'POWER_SUPPLY_TEMP'):
            with self.subTest(key=key):
                before = self.passive.pop(key)
                self.assertTrue(self.errors())
                self.passive[key] = before

    def test_adc_timeout_unknown_or_fault_latch_stops(self):
        for health in ('Unknown', 'Unspecified failure', ''):
            self.passive['POWER_SUPPLY_HEALTH'] = health
            self.assertTrue(self.errors())

    def test_temperature_and_vbat_stop_boundaries(self):
        for target, key, value in [(self.battery, 'POWER_SUPPLY_TEMP', '420'),
                                   (self.battery, 'POWER_SUPPLY_VOLTAGE_NOW', '4300000'),
                                   (self.passive, 'POWER_SUPPLY_TEMP', '600')]:
            old = target[key]; target[key] = value
            self.assertTrue(self.errors())
            target[key] = old

    def test_vbus_and_ibus_reported_bounds(self):
        for key, value in [('POWER_SUPPLY_VOLTAGE_NOW', '5500001'),
                           ('POWER_SUPPLY_VOLTAGE_NOW', '4499999'),
                           ('POWER_SUPPLY_CURRENT_NOW', '100001'),
                           ('POWER_SUPPLY_CURRENT_NOW', '-1')]:
            old = self.passive[key]; self.passive[key] = value
            self.assertTrue(self.errors()); self.passive[key] = old

    def test_charging_source_or_dfp_is_rejected(self):
        self.passive['POWER_SUPPLY_STATUS'] = 'Charging'
        self.assertTrue(self.errors())
        self.passive['POWER_SUPPLY_STATUS'] = 'Not charging'
        self.assertTrue(self.errors('[source] sink'))
        self.assertTrue(self.errors(data='[host] device'))

    def test_known_vendor_charge_boot_allows_baseline_reboot_only(self):
        self.assertTrue(p.charge_boot_only('panic=0 sec_pon_alarm.lpcharge=1 cpufreq_limit.lpcharge=1',
                                         'panic=0 sec_pon_alarm.lpcharge=0'))

    def test_panic_or_unknown_parameter_change_is_not_charge_boot_only(self):
        for actual in ('panic=10 sec_pon_alarm.lpcharge=1',
                       'panic=0 sec_pon_alarm.lpcharge=1 unknown.lpcharge=1',
                       'panic=0 sec_pon_alarm.lpcharge=1 CONFIG_HVC_DCC=y'):
            self.assertFalse(p.charge_boot_only(actual, 'panic=0 sec_pon_alarm.lpcharge=0'))

    def test_duplicate_invalid_or_already_normal_flags_rejected(self):
        before = 'panic=0 sec_pon_alarm.lpcharge=0'
        for actual in (before, 'panic=0 sec_pon_alarm.lpcharge=2',
                       'panic=0 sec_pon_alarm.lpcharge=1 sec_pon_alarm.lpcharge=1'):
            self.assertFalse(p.charge_boot_only(actual, before))
