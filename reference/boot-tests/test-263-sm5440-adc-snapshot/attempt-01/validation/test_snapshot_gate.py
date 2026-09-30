"""Offline sampling gate tests. Never import a device orchestration script."""
import importlib.util
from pathlib import Path
import unittest

A = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('snapshot_gate', A / 'snapshot_gate.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class GateTests(unittest.TestCase):
    def fixture(self, voltage=5, **changes):
        adc = [22, 0, 0, 0, 0, 0, 0, 0, 11, 122, 0]
        if voltage == 9:
            adc[:2] = [153, 64]
        d = dict(format='sm5440-passive-v1', registers_are_cached='1',
                 independently_calibrated='0', pump_enable_supported='0',
                 sample_present='1', sample_valid='1', sample_fresh='1',
                 stopped='0', fault='0', startup_pending='0',
                 last_sample_error='0', sample_faults='0x0', sample_age_ms='20',
                 sample_stamp_jiffies='100', capture_jiffies='120',
                 sample_mode_before='0x00', sample_mode_after='0x00',
                 sample_cntl2='0xf2', sample_vbuscntl='0x40',
                 sample_vbatcntl='0x7f', sample_prtncntl='0x00',
                 sample_int='00 00 00 01', sample_status='00 00 20 00',
                 sample_adc=' '.join(f'{n:02x}' for n in adc),
                 startup_int='00 00 00 00', startup_status='00 00 00 00',
                 startup_adc=' '.join(['00'] * 11), startup_faults='0x0',
                 startup_retained='0', sample_vbus_uv='4800000' if voltage == 5 else '9000000',
                 sample_vbat_uv='4000000', sample_ibus_ua='0', sample_die_decic='280')
        d.update(changes)
        return '\n'.join(f'{k}={v}' for k, v in d.items())

    def test_fixed5_and_fixed9_clean(self):
        for v in (5, 9):
            self.assertEqual(gate.validate_snapshot(self.fixture(v), v)['sample_fresh'], '1')

    def test_exact_age_boundary(self):
        gate.validate_snapshot(self.fixture(sample_age_ms='2500'))
        for age in ('2501', '-1', '4294967296'):
            with self.assertRaises(ValueError):
                gate.validate_snapshot(self.fixture(sample_age_ms=age))

    def test_missing_empty_duplicate(self):
        for raw in ('', self.fixture().replace('sample_valid=1\n', ''),
                    self.fixture() + '\nsample_valid=1'):
            with self.assertRaises((ValueError, KeyError)):
                gate.validate_snapshot(raw)

    def test_fault_stopped_pending_invalid_error(self):
        for k in ('sample_present', 'sample_valid', 'sample_fresh'):
            with self.assertRaises(ValueError):
                gate.validate_snapshot(self.fixture(**{k: '0'}))
        for k in ('stopped', 'fault', 'startup_pending', 'last_sample_error'):
            with self.assertRaises(ValueError):
                gate.validate_snapshot(self.fixture(**{k: '1'}))
        with self.assertRaises(ValueError):
            gate.validate_snapshot(self.fixture(sample_faults='0x80'))

    def test_future_or_zero_timestamp(self):
        for stamp in ('121', '0'):
            with self.assertRaises(ValueError):
                gate.validate_snapshot(self.fixture(sample_stamp_jiffies=stamp))

    def test_active_mode_rejected(self):
        for name in ('sample_mode_before', 'sample_mode_after'):
            with self.assertRaises(ValueError):
                gate.validate_snapshot(self.fixture(**{name: '0x04'}))

    def test_retained_startup_separate_not_live_fault(self):
        gate.validate_snapshot(self.fixture(startup_faults='0x80', startup_retained='1'))
        with self.assertRaises(ValueError):
            gate.validate_snapshot(self.fixture(startup_faults='0x82', startup_retained='1'))

    def test_raw_lengths_and_bytes(self):
        for raw in ('00 00', ' '.join(['gg'] * 11), ' '.join(['100'] * 11)):
            with self.assertRaises(ValueError):
                gate.validate_snapshot(self.fixture(sample_adc=raw))

    def test_conversion_mismatch_rejected(self):
        for k in ('sample_vbus_uv', 'sample_vbat_uv', 'sample_ibus_ua', 'sample_die_decic'):
            with self.assertRaises(ValueError):
                gate.validate_snapshot(self.fixture(**{k: '1'}))

    def test_no_calibration_or_pump_claim(self):
        for k in ('independently_calibrated', 'pump_enable_supported'):
            with self.assertRaises(ValueError):
                gate.validate_snapshot(self.fixture(**{k: '1'}))

    def test_unregistered_voltage(self):
        with self.assertRaises(ValueError):
            gate.validate_snapshot(self.fixture(9), 12)

    def test_runner_keeps_first_stop_and_snapshot_capture(self):
        text = (A / 'observe.py').read_text()
        for value in ('snapshot = validate_snapshot', "sections['snapshot-before']",
                      "sections['snapshot-after']", 'elapsed >= 30',
                      'protection == initial_protection', 'STOP first non-clean',
                      "'rollback_required': True", 'sm5440-0-0063/snapshot'):
            self.assertIn(value, text)
        self.assertNotIn('out/kernel-x710-260-passive', text)

    def test_pd_uses_verified_postboot_wifi_and_keeps_fault_stops(self):
        text = (A / 'observe-pd.py').read_text()
        self.assertIn("observation/final-wifi-address.txt", text)
        self.assertNotIn("preflight/summary.json", text)
        for value in ('validate_snapshot(sections[\'snapshot\'], 9)',
                      '<= 1500000', 'elapsed >= 30', 'STOP first non-clean',
                      'protection changed since PC', 'fixed9V contract'):
            self.assertIn(value, text)


if __name__ == '__main__':
    unittest.main()
