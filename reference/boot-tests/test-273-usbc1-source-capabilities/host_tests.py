"""Collector gates with immutable device fixtures; no real transport calls."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

A = Path(__file__).resolve().parent
S = importlib.util.spec_from_file_location('source_collector273', A / 'capture.py')
c = importlib.util.module_from_spec(S)
S.loader.exec_module(c)


class CollectorTests(unittest.TestCase):
    def pc(self):
        return c.gate.sections((A / 'preflight/current-state.txt').read_text())

    def pd(self):
        sec = self.pc()
        p = c.ROOT / 'reference/boot-tests/test-263-sm5440-adc-snapshot/attempt-01/pd-observation/summary.json'
        actual = json.loads(p.read_text())['samples'][0]
        for key in ('battery', 'usb', 'passive', 'tcpm'):
            sec[key] = '\n'.join(k + '=' + v for k, v in actual[key].items()) + '\n'
        sec['snapshot'] = '\n'.join(k + '=' + v for k, v in actual['snapshot'].items()) + '\n'
        return sec

    def test_current_pc_fixture_healthy(self):
        value = c.sample(self.pc())
        self.assertFalse(value['high_power_admission'])

    def test_accepted_pd_fixture_healthy_fixed(self):
        value = c.sample(self.pd(), True)
        self.assertEqual(value['negotiated_voltage_mv'], 9000)
        self.assertFalse(value['active_charge_admission'])

    def test_unapproved_contract_voltage_refused(self):
        sec = self.pd()
        sec['tcpm'] = sec['tcpm'].replace('POWER_SUPPLY_VOLTAGE_NOW=9000000', 'POWER_SUPPLY_VOLTAGE_NOW=12000000')
        with self.assertRaises(c.p.CaptureError):
            c.sample(sec, True)

    def test_raised_contract_or_input_current_refused(self):
        for section, prop in (('tcpm', 'POWER_SUPPLY_CURRENT_MAX'), ('usb', 'POWER_SUPPLY_INPUT_CURRENT_LIMIT')):
            sec = self.pd()
            sec[section] = sec[section].replace(prop + '=1500000', prop + '=3000000')
            with self.assertRaises(c.p.CaptureError):
                c.sample(sec, True)

    def test_thermal_and_fault_refused(self):
        sec = self.pd()
        b = c.gate.props(sec['battery'])
        sec['battery'] = sec['battery'].replace('POWER_SUPPLY_TEMP=' + b['POWER_SUPPLY_TEMP'], 'POWER_SUPPLY_TEMP=420')
        with self.assertRaises(ValueError):
            c.sample(sec, True)
        sec = self.pd()
        sec['snapshot'] = sec['snapshot'].replace('\nfault=0\n', '\nfault=1\n')
        with self.assertRaises(ValueError):
            c.sample(sec, True)

    def test_pump_on_is_refused(self):
        sec = self.pd()
        sec['snapshot'] = sec['snapshot'].replace('sample_mode_after=0x01', 'sample_mode_after=0x05')
        with self.assertRaises(ValueError):
            c.sample(sec, True)

    def test_identity_role_or_failed_unit_refused(self):
        for key, value in (('boot', '0123456789abcdef0123456789abcdef'),
                           ('identity', 'wrong -\nwrong /sys/kernel/notes'),
                           ('roles', '[sink]\n[host]\n'), ('failed', 'new.service loaded failed')):
            sec = self.pd()
            sec[key] = value
            with self.assertRaises(c.p.CaptureError):
                c.sample(sec, True)

    def test_negotiated_pps_refused_even_if_voltage_is_nine(self):
        sec = self.pd()
        sec['tcpm'] = sec['tcpm'].replace('[PD]', 'PD [PD_PPS]')
        with self.assertRaises(c.p.CaptureError):
            c.sample(sec, True)

    def test_rp_budget_is_not_charger_draw(self):
        parsed = {'limits': [{'voltage_mv': 0, 'current_ma': 0},
                             {'voltage_mv': 5000, 'current_ma': 3000},
                             {'voltage_mv': 9000, 'current_ma': 1500}]}
        result = c.fixed_budget_history(parsed)
        self.assertFalse(result['limits_are_measured_draw'])
        self.assertEqual(result['fixed5V_input_ceiling_ma'], 1800)
        self.assertEqual(c.sample(self.pd(), True)['usb']['POWER_SUPPLY_INPUT_CURRENT_LIMIT'], '1500000')

    def test_unapproved_voltage_or_budget_still_refused(self):
        for mv, ma in ((12000, 1500), (20000, 3000), (9000, 3000), (5000, 3500), (0, 500)):
            with self.assertRaises(c.p.CaptureError):
                c.fixed_budget_history({'limits': [{'voltage_mv': mv, 'current_ma': ma}]})

    def test_dcc_absence_required(self):
        sec = self.pc()
        sec['dcc'] = 'present'
        with self.assertRaises(c.p.CaptureError):
            c.sample(sec)

    def test_pc_ncm_interface_required(self):
        sec = self.pc()
        sec['network'] = 'lo wlan0'
        with self.assertRaises(c.p.CaptureError):
            c.sample(sec)

    def test_owner_confirmation_required_before_capture(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(c, 'A', Path(tmp)):
            with self.assertRaises(c.p.CaptureError):
                c.execute('source', False)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_existing_phase_cannot_retry_or_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(c, 'A', Path(tmp)):
            (Path(tmp) / 'source').mkdir()
            with self.assertRaises(c.p.CaptureError):
                c.execute('source', True)

    def test_first_failure_stops_and_preserves_no_charge_writes(self):
        sec = self.pc()
        sec['boot'] = '0123456789abcdef0123456789abcdef'
        raw = ''.join('@@' + k + '\n' + v + '\n' for k, v in sec.items())
        calls = []
        def fake_ssh(rec, name, command, timeout=20, required=True):
            calls.append(name)
            return raw
        class MockRecorder:
            def __init__(self, folder):
                self.folder = folder
                folder.mkdir()
        with tempfile.TemporaryDirectory() as tmp, patch.object(c, 'A', Path(tmp)), \
                patch.object(c.p, 'Recorder', MockRecorder), patch.object(c, 'ssh', fake_ssh), \
                patch.object(c.time, 'sleep', return_value=None):
            (Path(tmp) / 'prepare').mkdir()
            (Path(tmp) / 'prepare/summary.json').write_text(json.dumps({'verdict': 'READY_FOR_OWNER_C1_ATTACH', 'cursor': 'fixture'}))
            with self.assertRaises(c.p.CaptureError):
                c.execute('source', True)
            result = json.loads((Path(tmp) / 'source/summary.json').read_text())
            self.assertEqual(result['verdict'], 'STOP_FIRST_NON_CLEAN')
            self.assertFalse(result['PPS'])
            self.assertFalse(result['pump_ON'])
            self.assertEqual(result['samples'], [])
        self.assertEqual(calls, ['initial-state', 'first-failure-state', 'first-failure-kernel-json'])


if __name__ == '__main__':
    unittest.main()
