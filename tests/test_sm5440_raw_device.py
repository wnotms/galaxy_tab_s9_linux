"""New RAW evidence and first-fault lifecycle; historical READY stays unchanged."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_sm5440_timing_device as old

ROOT = Path(__file__).resolve().parents[1]
R = ROOT/'reference/boot-tests/test-321-off-continuous-raw-adc'


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, R/file)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


g = load('raw_device_gate', 'gate.py')


def fixture():
    s, p = old.fixture()
    s.update(timing_test='0', raw_test='1', conversion_freshness_proven='0',
             timing_observation_mode='2', timing_completed_ms='1650',
             timing_source1='1/2/3/1651/1655/5000/1800/1',
             timing_pack1='4/5/1656/1660/30/3700000/310')
    p.update(started_ms='1670', completed_ms='1675')
    for i in range(8):
        begin = 1080+i*70
        clear = 1051 if i == 0 else begin-70
        s.update({f'timing_sample{i}_times':f'{clear}/{begin}/{begin+1}/{begin+2}/{begin+10}',
                  f'timing_sample{i}_int':'00 00 20 00',
                  f'raw_sample{i}_read_ms':f'{begin+2}/{begin+10}',
                  f'raw_sample{i}_READY_observed':'0'})
    return s, p


class RawEvidenceTests(unittest.TestCase):
    def parse(self, s, p):
        return g.raw_capture(old.text(s), old.text(p))

    def test_no_ready_needed_and_no_freshness_or_charging_grant(self):
        s, p = fixture()
        r = self.parse(s, p)
        self.assertEqual(r['verdict'], 'OFF_CONTINUOUS_RAW_READS_CAPTURED')
        self.assertEqual(len(r['samples']), 8)
        self.assertFalse(any(x['READY_observed'] for x in r['samples']))
        for key in ('conversion_freshness_proven', 'source_calibrated',
                    'software_ocp_verified', 'PPS', 'pump_ON',
                    'ADC_active_100ms_gate_qualified', 'coherent_channels_qualified'):
            self.assertFalse(r[key])

    def test_optional_ready_retained_and_consistent(self):
        s, p = fixture()
        s['timing_sample1_int'] = '00 00 20 01'
        s['raw_sample1_READY_observed'] = '1'
        self.assertTrue(self.parse(s, p)['samples'][1]['READY_observed'])
        s['raw_sample1_READY_observed'] = '0'
        with self.assertRaises(ValueError):
            self.parse(s, p)

    def test_wrong_profile_fake_freshness_terminal_fault_and_cleanup_rejected(self):
        for key, value in [('timing_test', '1'), ('raw_test', '0'),
                           ('timing_observation_mode', '1'), ('conversion_freshness_proven', '1'),
                           ('timing_error', '-110'), ('timing_count', '7'),
                           ('timing_cleanup_error', '-5'), ('timing_restored', '0'),
                           ('timing_readiness_checks', '21'), ('fault', '1')]:
            s, p = fixture()
            s[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.parse(s, p)

    def test_early_read_inconsistent_read_brackets_and_deadline_rejected(self):
        for key, value in [('timing_sample1_times', '1080/1090/1091/1092/1100'),
                           ('raw_sample2_read_ms', '1230/1238'),
                           ('timing_completed_ms', '4000')]:
            s, p = fixture()
            s[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.parse(s, p)

    def test_generation_fault_controls_voltage_current_temperature_rejected(self):
        for key, value in [('timing_source1', '1/7/3/1651/1655/5000/1800/1'),
                           ('timing_pack1', '4/7/1656/1660/30/3700000/310'),
                           ('timing_controls', '08/df/09/df'),
                           ('timing_sample3_controls', '04/0b/df'),
                           ('timing_sample3_int', '00 00 22 00'),
                           ('timing_sample3_status_after', '00 00 60 00'),
                           ('timing_pack0', '4/5/966/990/30/3700000/450')]:
            s, p = fixture()
            s[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.parse(s, p)
        for offset, value in [(4, 1), (0, 255), (8, 40), (9, 0)]:
            s, p = fixture()
            a = s['timing_sample0_adc'].split()
            a[offset] = f'{value:02x}'
            s['timing_sample0_adc'] = ' '.join(a)
            with self.assertRaises(ValueError):
                self.parse(s, p)

    def test_current_port_changes_and_duplicate_fields_rejected(self):
        for key, value in [('online', '2'), ('budget_generation', '4'),
                           ('budget_ma', '3000'), ('charge_requested', '0')]:
            s, p = fixture()
            p[key] = value
            with self.assertRaises(ValueError):
                self.parse(s, p)
        s, p = fixture()
        with self.assertRaises(ValueError):
            g.raw_capture(old.text(s)+'\ntiming_count=1', old.text(p))


class RawLifecycleTests(unittest.TestCase):
    def test_registration_and_import_have_no_device_io(self):
        h = load('raw_registration', 'host_flow.py')
        with patch.object(h.p, 'Recorder') as rec:
            h.configure()
            rec.assert_not_called()
        self.assertIn('test321', h.h.STAGE)
        self.assertIn('test321', h.h.TMP)
        self.assertFalse(h.PLAN['PPS'])
        self.assertFalse(h.PLAN['pump_ON'])
        self.assertFalse(h.PLAN['converter_READY_required'])
        self.assertEqual(h.PLAN['normal_candidate_boots'], 1)

    def test_low_reserve_refuses_before_recovery_or_full_probe(self):
        h = load('raw_reserve', 'host_flow.py')
        h.configure()
        battery = 'POWER_SUPPLY_HEALTH=Good\nPOWER_SUPPLY_PRESENT=1\nPOWER_SUPPLY_CAPACITY=19\nPOWER_SUPPLY_VOLTAGE_NOW=3700000\nPOWER_SUPPLY_TEMP=310'
        with tempfile.TemporaryDirectory() as tmp:
            h.R = Path(tmp)
            with patch.object(h.p, 'Recorder') as rec, patch.object(h.base, 'preflight') as full:
                rec.return_value.folder = Path(tmp)
                rec.return_value.adb.return_value = ('@@boot\n'+'a'*32+'\n@@battery\n'+battery, 0)
                with self.assertRaisesRegex(ValueError, 'battery reserve'):
                    h.preflight()
                full.assert_not_called()
                self.assertFalse(json.loads((Path(tmp)/'summary.json').read_text())['device_mutation'])

    def test_low_reserve_at_mutation_boundary_refuses(self):
        h = load('raw_boundary_reserve', 'host_flow.py')
        h.configure()
        with tempfile.TemporaryDirectory() as tmp:
            h.R = Path(tmp)
            (h.R/'preflight').mkdir()
            h.write(h.R/'preflight/summary.json', dict(verdict='READY_FOR_REGISTERED_ONE_BOOT',
                    authenticated_wifi=True, boot_id='a'*32, collected_at_epoch=h.time.time()))
            with patch.object(h.p, 'Recorder') as rec, patch.object(h, 'identity',
                    return_value=({}, 'a'*32, {'soc': 19}, {})), patch.object(h.h, 'enter_recovery') as recovery:
                rec.return_value.adb.return_value = ('raw', 0)
                with self.assertRaisesRegex(ValueError, 'flash reserve'):
                    h.install_once()
                recovery.assert_not_called()
                self.assertFalse((h.R/'mutation-state.json').exists())

    def test_failure_and_success_both_restore_exactly_once(self):
        for failure in (False, True):
            h = load('raw_run_'+str(failure), 'host_flow.py')
            with tempfile.TemporaryDirectory() as tmp:
                h.R = Path(tmp)
                h.p.SERIAL = 'R52X10045LT'
                def install():
                    h.write(h.R/'mutation-state.json', dict(rollback_required=True))
                    if failure:
                        raise ValueError('native RAW fault')
                    return {'capture': 'raw'}
                with patch.object(h, 'verify_inputs'), patch.object(h, 'install_once', side_effect=install) as start, patch.object(h, 'restore') as restore:
                    if failure:
                        with self.assertRaisesRegex(RuntimeError, 'first non-clean'):
                            h.run()
                    else:
                        self.assertEqual(h.run(), {'capture': 'raw'})
                    start.assert_called_once()
                    restore.assert_called_once_with(from_recovery=True)

    def test_no_install_or_restore_replay(self):
        h = load('raw_no_replay', 'host_flow.py')
        with tempfile.TemporaryDirectory() as tmp:
            h.R = Path(tmp)
            h.write(h.R/'mutation-state.json', dict(rollback_required=False))
            with patch.object(h, 'verify_inputs'), patch.object(h, 'install_once') as install:
                with self.assertRaises(ValueError):
                    h.run()
                install.assert_not_called()
            with patch.object(h, 'verify_inputs') as verify:
                with self.assertRaisesRegex(ValueError, 'already restored'):
                    h.restore()
                verify.assert_not_called()

    def test_terminal_adc_fault_is_preserved_before_startup_service_gate(self):
        h = load('raw_native_first', 'host_flow.py')
        h.configure()
        raw = '@@snapshot\ntiming_attempted=1\ntiming_error=-110\n@@services\ninactive\nactive\nactive\n'
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with (patch.object(h.p, 'Recorder') as rec, patch.object(h.time, 'sleep') as wait,
                  patch.object(h, 'identity') as identity,
                  patch.object(h.gate, 'raw_capture', side_effect=ValueError('native terminal diagnostic state'))):
                rec.return_value.adb.side_effect = [(raw, 0), ('journal', 0), ('boots', 0)]
                with self.assertRaisesRegex(ValueError, 'native terminal'):
                    h.admission(folder, 'candidate', 'a'*32, 'old boots')
                self.assertEqual(rec.return_value.adb.call_count, 3)
                wait.assert_not_called()
                identity.assert_not_called()

    def test_completed_raw_waits_for_startup_service_without_repeating_adc(self):
        h = load('raw_service_readiness', 'host_flow.py')
        h.configure()
        boot = 'b'*32
        snap = {'timing_attempted': '1', 'timing_error': '0'}
        pending = '@@snapshot\ntiming_attempted=1\ntiming_error=0\n@@services\ninactive\nactive\nactive\n'
        ready = pending.replace('inactive', 'active')
        sec = {'snapshot': old.text(snap), 'source': '', 'uptime': '10.0 0.0'}
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with (patch.object(h.p, 'Recorder') as rec,
                  patch.object(h.time, 'sleep') as wait,
                  patch.object(h, 'identity', return_value=(sec, boot, {'soc': 30}, snap)),
                  patch.object(h.gate, 'raw_capture', return_value={'verdict': 'raw'}),
                  patch.object(h.base.old, 'scan_journal', return_value={}),
                  patch.object(h.h.g.evidence, 'attribute', return_value='attributed'),
                  patch.object(h.base, 'thermal'), patch.object(h, 'controls'),
                  patch.object(h.base.old, 'ncm_probe', return_value=('', 0))):
                rec.return_value.adb.side_effect = [(pending, 0), (ready, 0), ('journal', 0), ('boots', 0)]
                rec.return_value.ps.return_value = ('ProblemCode : 0', 0)
                result, history = h.admission(folder, 'candidate', 'a'*32, 'before')
                self.assertEqual(result['boot_id'], boot)
                self.assertEqual(history, 'boots')
                wait.assert_called_once_with(2)
                self.assertEqual(rec.return_value.adb.call_count, 4)


if __name__ == '__main__':
    unittest.main()
