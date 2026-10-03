"""Test306 evidence/entry refusals; no device commands or physical acceptance."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'reference/boot-tests/test-306-adc-condition-comparison'
spec = importlib.util.spec_from_file_location('condition306', R / 'gate.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
BOOT = '1' * 32


def fixture():
    snapshot = dict(condition_test='1', condition_attempted='1', enhiz_restore_pending='0',
                    last_sample_error='0', pump_enable_supported='0', sample_valid='1',
                    fault='0', stopped='0', startup_pending='0', startup_faults='0x0',
                    condition_cntl6_before_valid='1', condition_cntl6_during_valid='1',
                    condition_cntl6_restored_valid='1', condition_cntl6_before='0x89',
                    condition_cntl6_during='0x09', condition_cntl6_restored='0x89',
                    condition_condition_error='0', condition_restore_error='0',
                    condition_mode_before='0x01', condition_mode_after='0x01',
                    condition_ibus_ua='0', condition_vbus_uv='5006000',
                    condition_vbat_uv='4000000', condition_die_decic='260',
                    condition_faults='0x0', condition_gauge_attempted='1',
                    condition_gauge_ret='0', condition_gauge_uv='3826000',
                    condition_adc_read_completed_ms='316', condition_gauge_started_ms='316',
                    condition_gauge_completed_ms='318', condition_int='00 00 20 00',
                    condition_status='00 00 20 00')
    message = ('sm5440-passive 0-0063: startup voltage pair seq=1 ADC-start=174ms '
               'ADC-read=316ms VBAT=4000000uV gauge-start=316ms gauge-end=318ms '
               'gauge-ret=0 gauge=3826000uV')
    journal = json.dumps(dict(_BOOT_ID=BOOT, MESSAGE=message)) + '\n'
    return snapshot, journal


def raw(snapshot):
    return ''.join(k + '=' + v + '\n' for k, v in snapshot.items())


class ConditionEvidenceTests(unittest.TestCase):
    def case(self, changes=None, journal=None):
        s, j = fixture()
        s.update(changes or {})
        return m.condition(raw(s), j if journal is None else journal, BOOT)

    def test_complete_one_pair_preserves_difference_and_no_grant(self):
        r = self.case()
        self.assertEqual(r['verdict'], 'OFF_CONDITION_COMPARISON_CAPTURED')
        self.assertEqual(r['acquisition_interval_ms'], 142)
        self.assertEqual(r['gauge_minus_ADC_uv'], -174000)
        for key in ['source_calibrated', 'physical_freshness_grant', 'charging_authorized',
                    'PPS', 'pump_ON']:
            self.assertFalse(r[key])

    def test_already_clear_is_not_informative(self):
        self.assertEqual(self.case({'condition_cntl6_before': '0x09',
                                   'condition_cntl6_restored': '0x09'})['verdict'],
                         'NO_ENHIZ_CONDITION_CHANGE')

    def test_read_flags_restoration_pending_error_refused(self):
        cases = [('condition_cntl6_before_valid', '0'), ('condition_cntl6_during_valid', '0'),
                 ('condition_cntl6_restored_valid', '0'), ('condition_restore_error', '-5'),
                 ('condition_condition_error', '-110'), ('enhiz_restore_pending', '1'),
                 ('condition_cntl6_restored', '0x09'), ('condition_cntl6_during', '0x89')]
        for key, value in cases:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.case({key: value})

    def test_fault_stop_missing_sample_and_wrong_profile_refused(self):
        for key, value in [('fault', '1'), ('stopped', '1'), ('sample_valid', '0'),
                           ('condition_attempted', '0'), ('condition_test', '0'),
                           ('pump_enable_supported', '1'), ('last_sample_error', '-5')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.case({key: value})

    def test_mode_current_voltage_temperature_refused(self):
        for key, value in [('condition_mode_after', '0x05'), ('condition_ibus_ua', '625'),
                           ('condition_vbus_uv', '9000000'), ('condition_vbat_uv', '3498000'),
                           ('condition_vbat_uv', '4440001'), ('condition_die_decic', '420')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.case({key: value})

    def test_only_original_preconversion_revblk_can_be_retained(self):
        s = {'condition_faults': '0x80', 'startup_faults': '0x80', 'startup_pending': '2',
             'condition_int': '00 00 62 00'}
        self.assertEqual(self.case(s)['verdict'], 'OFF_CONDITION_COMPARISON_CAPTURED')
        for key, value in [('startup_faults', '0x0'), ('startup_pending', '0'),
                           ('condition_status', '00 00 22 00'),
                           ('condition_int', '08 00 62 00'), ('fault', '1')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.case(dict(s, **{key: value}))

    def test_journal_absent_mixed_extra_pair_refused(self):
        _, j = fixture()
        for bad in ['', j + j, j + json.dumps({'_BOOT_ID': '2'*32, 'MESSAGE': 'boot'})+'\n',
                    j.replace('seq=1', 'seq=2'), j.replace('gauge-ret=0', 'gauge-ret=-5')]:
            with self.subTest(journal=bad), self.assertRaises(ValueError):
                self.case(journal=bad)

    def test_pair_timestamp_and_value_mismatch_refused(self):
        for key, value in [('condition_gauge_uv', '3879000'),
                           ('condition_vbat_uv', '4000500'),
                           ('condition_adc_read_completed_ms', '317'),
                           ('condition_gauge_started_ms', '315'),
                           ('condition_gauge_completed_ms', '320')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.case({key: value})

    def test_gauge_unavailable_and_malformed_fields_refused(self):
        for changes in [{'condition_gauge_ret': '-5'}, {'condition_gauge_attempted': '0'},
                        {'condition_cntl6_before': 'unknown'}, {'condition_faults': '0x82'}]:
            with self.assertRaises(ValueError):
                self.case(changes)

    def test_conflicting_duplicate_field_refused(self):
        s, j = fixture()
        with self.assertRaises(ValueError):
            m.condition(raw(s)+'enhiz_restore_pending=1\n', j, BOOT)


class BatteryEntryTests(unittest.TestCase):
    def test_safe_entry(self):
        text = ('POWER_SUPPLY_HEALTH=Good\nPOWER_SUPPLY_PRESENT=1\n'
                'POWER_SUPPLY_CAPACITY=20\nPOWER_SUPPLY_VOLTAGE_NOW=3800000\nPOWER_SUPPLY_TEMP=313\n')
        self.assertEqual(m.battery_entry(text)['soc'], 20)

    def test_low_battery_actual_record_refused(self):
        real = ROOT / 'reference/boot-tests/test-305-adc-condition-offline/validation/retained-device.txt'
        with self.assertRaises(ValueError):
            m.battery_entry(real.read_text())

    def test_soc_voltage_temperature_and_health_bounds(self):
        b = dict(POWER_SUPPLY_HEALTH='Good', POWER_SUPPLY_PRESENT='1',
                 POWER_SUPPLY_CAPACITY='20', POWER_SUPPLY_VOLTAGE_NOW='3800000', POWER_SUPPLY_TEMP='313')
        for key, value in [('POWER_SUPPLY_CAPACITY', '0'), ('POWER_SUPPLY_CAPACITY', '80'),
                           ('POWER_SUPPLY_VOLTAGE_NOW', '3500000'), ('POWER_SUPPLY_VOLTAGE_NOW', '4300000'),
                           ('POWER_SUPPLY_TEMP', '199'), ('POWER_SUPPLY_TEMP', '380'),
                           ('POWER_SUPPLY_HEALTH', 'Unknown')]:
            text = raw(dict(b, **{key: value}))
            if value == '3500000':
                self.assertEqual(m.battery_entry(text)['voltage_uv'], 3500000)
            else:
                with self.assertRaises(ValueError):
                    m.battery_entry(text)


if __name__ == '__main__':
    unittest.main()
