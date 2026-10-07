"""Test344 bounded OFF settling witnesses and inherited guardian cleanup."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import test_sm5440_bounded_direct as old

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reference/boot-tests/test-344-parked-current-settle'
spec=importlib.util.spec_from_file_location('guard344',R/'guard.py')
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
ORIGINAL=old.journal


def journal():
    rows=ORIGINAL()
    rows[1]['MESSAGE']=rows[1]['MESSAGE'].replace('ibus limit 1800','ibus limit 1700')
    rows.insert(1,old.row('one-shot parked settled: samples=3 waited=120ms raw_ibus=0 pump_OFF=1',900000))
    rows.insert(5,old.row('one-shot parked settled: samples=3 waited=120ms raw_ibus=0 pump_OFF=1',5120000))
    return rows


class SettlingEvidenceTests(unittest.TestCase):
    def test_clean_initial_and_refresh_witnesses(self):
        d=g.native_proof(journal(),old.BOOT,required=True)
        self.assertEqual((d['parked_zero_proofs'],d['refreshes'],d['hardware_input_ma'],d['target_ma']),(2,1,1700,1800))

    def test_missing_initial_or_refresh_witness_cannot_pass(self):
        for index in (1,5):
            rows=journal();rows.pop(index)
            with self.subTest(index=index),self.assertRaises(ValueError):g.native_proof(rows,old.BOOT,required=True)

    def test_short_or_nonzero_or_malformed_settling_proof_rejected(self):
        for text in ('samples=2 waited=120ms raw_ibus=0 pump_OFF=1',
                     'samples=3 waited=99ms raw_ibus=0 pump_OFF=1',
                     'samples=31 waited=120ms raw_ibus=0 pump_OFF=1',
                     'samples=3 waited=120ms raw_ibus=625 pump_OFF=1',
                     'samples=3 waited=120ms raw_ibus=0 pump_OFF=0'):
            rows=journal();rows[5]['MESSAGE']='one-shot parked settled: '+text
            with self.subTest(text=text),self.assertRaises(ValueError):g.native_proof(rows,old.BOOT)

    def test_duplicate_and_out_of_phase_zero_witness_rejected(self):
        for index,stamp in ((2,950000),(4,4000000),(6,5130000)):
            rows=journal();rows.insert(index,old.row('one-shot parked settled: samples=3 waited=120ms raw_ibus=0 pump_OFF=1',stamp))
            with self.subTest(index=index),self.assertRaises(ValueError):g.native_proof(rows,old.BOOT)

    def test_parked_timeout_and_native_range_stop_remain_failures(self):
        for text in ('one-shot parked settle failed: zero_samples=0 waited=1470ms pump_OFF=1',
                     'one-shot range rejected: running=0 ibus=1744375uA',
                     'one-shot pump stopped: primary=-110 cleanup=0 lease=0 no_restart=1'):
            rows=journal()[:5]+[old.row(text,5100000)]
            with self.subTest(text=text),self.assertRaises(ValueError):g.native_proof(rows,old.BOOT)

    def test_partial_proof_never_counts_as_completion(self):
        rows=journal()
        for n in range(1,len(rows)):
            self.assertIsNone(g.native_proof(rows[:n],old.BOOT))
            with self.assertRaises(ValueError):g.native_proof(rows[:n],old.BOOT,required=True)

    def test_current_voltage_temperature_caps_unchanged(self):
        for section,key,value in (('adc','ibus_ua',1800625),('adc','die_decic',850),
                                  ('battery','POWER_SUPPLY_TEMP','420'),
                                  ('battery','POWER_SUPPLY_CURRENT_NOW','3600001')):
            s=old.sample();s[section][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):g.check_sample(s)

    def test_long_park_wait_does_not_relax_existing_two_second_resume_bound(self):
        rows=journal();rows[6]['_SOURCE_MONOTONIC_TIMESTAMP']='7000001'
        with self.assertRaises(ValueError):g.native_proof(rows,old.BOOT)

    def test_registered_source_and_exclusive_module_namespace(self):
        plan=json.loads((R/'registration.json').read_text())
        self.assertEqual(plan['source_revision'],'d60f264198476df8d15c4f38febf97d2f32c6318')
        self.assertEqual((plan['hardware_input_setpoint_ma'],plan['physical_ibus_max_ua']),(1700,1800000))
        self.assertIn('.gts9-test344-original',(R/'module-swap.sh').read_text())
        self.assertNotIn('.gts9-test343-original',(R/'module-swap.sh').read_text())
        spec=importlib.util.spec_from_file_location('flow344',R/'host_flow.py')
        f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f);f.configure()
        self.assertTrue(f.authorized());f.verify_inputs()


class RuntimeRegressionTests(unittest.TestCase):
    def test_inherited_cleanup_on_pass_fault_transport_and_no_live_sample(self):
        fixture=old.BoundedGuardianTests('test_guardian_cleanup_on_success_fault_transport_and_missing_pump_sample')
        with patch.object(old,'g',g),patch.object(old,'journal',journal):
            fixture.test_guardian_cleanup_on_success_fault_transport_and_missing_pump_sample()


if __name__=='__main__':unittest.main()
