"""Test343: distinguish programmed 1.7A from 1.8A contract/safety ceiling."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_sm5440_bounded_direct as old
import test_sm5440_temperature_activation as previous
import test_sm5440_source_capability_observer as capability
import test_sm5440_bounded_deployment as deployment

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'reference/boot-tests/test-343-current-programming-margin'
spec = importlib.util.spec_from_file_location('guard343', R / 'guard.py')
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)
ORIGINAL_JOURNAL = old.journal


def journal():
    rows = ORIGINAL_JOURNAL()
    rows[1]['MESSAGE'] = rows[1]['MESSAGE'].replace('ibus limit 1800', 'ibus limit 1700')
    return rows


class NativeRegression(previous.PriorGuardTests):
    def setUp(self):
        for module, name, value in ((previous, 'g', g), (old, 'journal', journal)):
            p = patch.object(module, name, value)
            p.start()
            self.addCleanup(p.stop)
        super().setUp()


class CleanupRegression(previous.PriorCleanupTests):
    def setUp(self):
        p = patch.object(previous, 'g', g)
        p.start()
        self.addCleanup(p.stop)
        super().setUp()


class ActivationRegression(previous.ActivationTests):
    def setUp(self):
        p = patch.object(previous, 'g', g)
        p.start()
        self.addCleanup(p.stop)


class CapabilityRegression(capability.CapabilityTests):
    def setUp(self):
        p = patch.object(capability, 'g', g)
        p.start()
        self.addCleanup(p.stop)


class HardwareWitnessTests(unittest.TestCase):
    def test_lower_programming_limit_and_unchanged_contract_are_distinct(self):
        result = g.native_proof(journal(), old.BOOT, required=True)
        self.assertEqual((result['hardware_input_ma'], result['target_ma']), (1700, 1800))

    def test_wrong_missing_or_mismatched_hardware_and_contract_witness_stops(self):
        for text in ('direct charge started: PPS 8940 mV/1800 mA, ibus limit 1800 mA',
                     'direct charge started: PPS 8940 mV/1800 mA, ibus limit 1750 mA',
                     'direct charge started: PPS 8940 mV/1700 mA, ibus limit 1700 mA',
                     'direct charge started: PPS 8960 mV/1800 mA, ibus limit 1700 mA',
                     'direct charge started: PPS 8940 mV/1800 mA'):
            rows = journal()
            rows[1]['MESSAGE'] = text
            with self.subTest(text=text), self.assertRaises(ValueError):
                g.native_proof(rows, old.BOOT, required=True)

    def test_terminal_range_snapshots_stop_before_later_completion(self):
        for text in ('one-shot range rejected: ibus=1843750uA cap=1800000uA',
                     'one-shot pack range rejected: ibat=3600001uA'):
            rows = journal()[:3] + [old.row(text, 2000000)]
            with self.subTest(text=text), self.assertRaises(ValueError):
                g.native_proof(rows, old.BOOT)

    def test_test342_raw_current_and_mixed_return_tuple_remain_failures(self):
        for mixed in (False, True):
            sample = old.sample()
            sample['adc']['ibus_ua'] = 1843750
            if mixed:
                sample['tcpm'].update(POWER_SUPPLY_ONLINE='1', POWER_SUPPLY_CURRENT_NOW='271000')
            with self.subTest(mixed=mixed), self.assertRaises(ValueError):
                g.check_sample(sample)

    def test_shared_source_and_exclusive_namespace(self):
        plan = json.loads((R / 'registration.json').read_text())
        self.assertEqual((plan['hardware_input_setpoint_ma'], plan['physical_ibus_max_ua']),
                         (1700, 1800000))
        self.assertEqual(plan['source_revision'], '95159eec14a0f8ee1c75b470f615026b650b2316')
        self.assertIn('.gts9-test343-original', (R / 'module-swap.sh').read_text())
        self.assertNotIn('.gts9-test342-original', (R / 'module-swap.sh').read_text())
        flow = (R / 'host_flow.py').read_text()
        self.assertIn("h.TMP='/tmp/gts9-test343'", flow)
        self.assertIn('owner-C1-confirmation.json', flow)
        self.assertIn('direct_charge_once=1', (R / 'build_package.py').read_text())
        self.assertEqual(g.check_sample(old.sample()), True)


class DeploymentRegression(deployment.DeploymentTests):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('flow343', R / 'host_flow.py')
        cls.flow = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.flow)
        cls.flow.configure()

    def setUp(self):
        p = patch.object(deployment, 'f', self.flow)
        p.start()
        self.addCleanup(p.stop)

    def test_scope_and_namespace(self):
        f = self.flow
        self.assertTrue(f.authorized())
        self.assertEqual(f.h.TMP, '/tmp/gts9-test343')
        self.assertIn('gts9-test343', f.h.STAGE)
        self.assertNotEqual(json.loads((R / 'staged-files.json').read_text())['module-swap.sh']['sha256'],
                            json.loads((R.parent / 'test-342-source-capability-observer/staged-files.json').read_text())['module-swap.sh']['sha256'])

    def test_scope_forbids_changed_programming_request_or_software_cap(self):
        f = self.flow
        original = json.loads((R / 'execution-scope.json').read_text())
        for key, value in (('hardware_programming_ma', 1800), ('input_cap_ma', 1900),
                           ('pump_window_max_ms', 31000), ('registration_sha256', '0' * 64)):
            changed = dict(original, **{key: value})
            with self.subTest(key=key), patch.object(f, 'read', return_value=changed):
                self.assertFalse(f.authorized())


if __name__ == '__main__':
    unittest.main()
