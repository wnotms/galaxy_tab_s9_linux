import copy
import json
from pathlib import Path
import unittest
from gate import sections, props, battery_entry, diagnostic_sample

ROOT = Path(__file__).resolve().parents[3]

class StartupDiagnosticTests(unittest.TestCase):
    def setUp(self):
        raw = (ROOT / 'reference/boot-tests/test-263-sm5440-adc-snapshot/attempt-01/observation/sample-000.txt').read_text()
        self.sec = sections(raw)
        self.sec['roles'] = '[sink]\n[device]\n'
        self.sec['usb'] = 'POWER_SUPPLY_ONLINE=1\nPOWER_SUPPLY_USB_TYPE=Unknown [SDP] DCP CDP PD\nPOWER_SUPPLY_INPUT_CURRENT_LIMIT=500000\n'
        self.sec['battery'] = self.sec['battery'].replace('POWER_SUPPLY_CAPACITY=56', 'POWER_SUPPLY_CAPACITY=84')

    def test_accepted_real_snapshot_does_not_grant_high_power(self):
        self.sec['battery'] = '\n'.join('POWER_SUPPLY_CAPACITY=84' if x.startswith('POWER_SUPPLY_CAPACITY=') else x for x in self.sec['battery'].splitlines())
        s = diagnostic_sample(self.sec)
        self.assertFalse(s['high_power_admission'])
        self.assertFalse(s['direct_SOC_gate'])

    def test_eof_empty_failed_section_is_preserved(self):
        self.assertEqual(sections('@@boot\nx\n@@failed\n')['failed'], '')

    def test_duplicate_section_refused(self):
        with self.assertRaises(ValueError): sections('@@boot\nx\n@@boot\ny\n')

    def test_original_voltage_temperature_entry_retained(self):
        b = props(self.sec['battery'])
        for key, value in [('POWER_SUPPLY_VOLTAGE_NOW', '4300000'), ('POWER_SUPPLY_TEMP', '380'), ('POWER_SUPPLY_HEALTH', 'Unknown')]:
            q = b | {key: value}
            with self.assertRaises(ValueError): battery_entry(q)

    def test_fault_and_stale_snapshot_stop(self):
        for before, after in [('fault=0\n', 'fault=1\n'), ('sample_fresh=1\n', 'sample_fresh=0\n')]:
            sec = self.sec | {'snapshot': self.sec['snapshot'].replace(before, after)}
            with self.assertRaises(ValueError): diagnostic_sample(sec)

    def test_source_or_pd_charger_refused(self):
        for key, value in [('roles', '[source]\n[host]\n'), ('usb', self.sec['usb'].replace('[SDP]', '[PD]'))]:
            with self.assertRaises(ValueError): diagnostic_sample(self.sec | {key: value})

    def test_failed_unit_refused(self):
        with self.assertRaises(ValueError): diagnostic_sample(self.sec | {'failed': 'bad.service failed'})

    def test_original_off_raw_snapshot_gate_refuses_ibus(self):
        sec = self.sec | {'snapshot': self.sec['snapshot'].replace('sample_ibus_ua=0\n', 'sample_ibus_ua=625\n')}
        with self.assertRaises(ValueError): diagnostic_sample(sec)

if __name__ == '__main__':
    unittest.main(verbosity=2)
