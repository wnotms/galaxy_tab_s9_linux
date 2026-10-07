"""Test345 bounded OFF settling witnesses and inherited guardian cleanup."""
import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
import test_sm5440_bounded_direct as old

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reference/boot-tests/test-345-final-refresh-reserve'
spec=importlib.util.spec_from_file_location('guard345',R/'guard.py')
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
        self.assertEqual(plan['source_revision'],'01747a5f44dacb7fa6a5d45ea814e8827998c4e1')
        self.assertEqual((plan['hardware_input_setpoint_ma'],plan['physical_ibus_max_ua']),(1700,1800000))
        self.assertIn('.gts9-test345-original',(R/'module-swap.sh').read_text())
        self.assertNotIn('.gts9-test344-original',(R/'module-swap.sh').read_text())
        spec=importlib.util.spec_from_file_location('flow345',R/'host_flow.py')
        f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f);f.configure()
        self.assertTrue(f.authorized())
        # This round is immutable and closed. A subsequent kernel candidate
        # must still fail its live deployment gate. Exercise the positive gate
        # using the actual registered source, not by changing the old manifest.
        name='kernel/drivers/sm5440-fedora.c'
        path=ROOT/name
        expected=json.loads((R/'INPUTS.json').read_text())[name]
        historical=subprocess.check_output(['git','-C',str(ROOT),'show',
                                            plan['source_revision']+':'+name])
        self.assertEqual(hashlib.sha256(historical).hexdigest(),expected)
        test_name='tests/test_sm5440_refresh_reserve_deployment.py'
        registered_test=subprocess.check_output(['git','-C',str(ROOT),'show',
                                                '7c596eedbb3c76a2c0c5cf278f48921ea10f4dd6:'+test_name])
        self.assertEqual(hashlib.sha256(registered_test).hexdigest(),
                         json.loads((R/'INPUTS.json').read_text())[test_name])
        read_bytes=Path.read_bytes
        if hashlib.sha256(read_bytes(path)).hexdigest()!=expected:
            with self.assertRaisesRegex(ValueError,'input drift: '+name):
                f.verify_inputs()
        def registered_bytes(candidate):
            if candidate==path:
                return historical
            if candidate==ROOT/test_name:
                return registered_test
            return read_bytes(candidate)
        with patch.object(Path,'read_bytes',registered_bytes):
            f.verify_inputs()


class FinalReserveEvidenceTests(unittest.TestCase):
    def deferred_journal(self):
        rows=journal()
        rows.insert(7,old.row('one-shot refresh deferred: remaining=1000ms deadline=30900ms pump_unchanged=1',29900000))
        return rows

    def test_deferral_is_valid_only_with_complete_native_transaction(self):
        rows=self.deferred_journal()
        self.assertEqual(g.native_proof(rows,old.BOOT,True)['refresh_deferrals'],1)
        self.assertIsNone(g.native_proof(rows[:8],old.BOOT))
        with self.assertRaises(ValueError):g.native_proof(rows[:8],old.BOOT,True)

    def test_deferral_without_final_reserve_is_rejected(self):
        for text in ('remaining=2001ms deadline=30900ms pump_unchanged=1',
                     'remaining=0ms deadline=30900ms pump_unchanged=1',
                     'remaining=1000ms deadline=31900ms pump_unchanged=1',
                     'remaining=1000ms deadline=30900ms pump_unchanged=0',
                     'remaining=1ms deadline=30900ms pump_unchanged=1'):
            rows=self.deferred_journal();rows[7]['MESSAGE']='one-shot refresh deferred: '+text
            with self.subTest(text=text),self.assertRaises(ValueError):g.native_proof(rows,old.BOOT)
        for stamp in (28000000,30900000):
            rows=self.deferred_journal();rows[7]['_SOURCE_MONOTONIC_TIMESTAMP']=str(stamp)
            with self.subTest(stamp=stamp),self.assertRaises(ValueError):g.native_proof(rows,old.BOOT)

    def test_duplicate_out_of_phase_and_subsequent_park_rejected(self):
        rows=self.deferred_journal();rows.insert(8,old.row(rows[7]['MESSAGE'],29900100))
        with self.assertRaises(ValueError):g.native_proof(rows,old.BOOT)
        for index in (1,5,9):
            rows=journal();rows.insert(index,old.row('one-shot refresh deferred: remaining=1000ms deadline=30900ms pump_unchanged=1',29900000))
            with self.subTest(index=index),self.assertRaises(ValueError):g.native_proof(rows,old.BOOT)
        rows=self.deferred_journal();rows.insert(8,old.row('one-shot refresh parked: pump_OFF=1',29900100))
        with self.assertRaises(ValueError):g.native_proof(rows,old.BOOT)

    def test_test344_native_primary_remains_failure_and_is_not_masked(self):
        raw=(ROOT/'reference/boot-tests/test-344-parked-current-settle/physical-collection/kernel-json.txt').read_text()
        rows=[json.loads(x) for x in raw.splitlines()]
        with self.assertRaisesRegex(ValueError,'primary=-62 cleanup=0 lease=0'):
            g.native_proof(rows,rows[0]['_BOOT_ID'],True)

    def test_post_return_import_is_bound_to_new_guardian(self):
        code=(R/'observe-post-return.py').read_text()
        self.assertIn('from bounded345_guard import native_proof',code)
        self.assertNotIn('bounded342_guard',code)


class RuntimeRegressionTests(unittest.TestCase):
    def test_inherited_cleanup_on_pass_fault_transport_and_no_live_sample(self):
        fixture=old.BoundedGuardianTests('test_guardian_cleanup_on_success_fault_transport_and_missing_pump_sample')
        with patch.object(old,'g',g),patch.object(old,'journal',journal):
            fixture.test_guardian_cleanup_on_success_fault_transport_and_missing_pump_sample()


if __name__=='__main__':unittest.main()
