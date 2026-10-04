"""Offline parser/lifecycle tests for one Test318 capture, with no device IO."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reference/boot-tests/test-318-off-continuous-adc-timing'

def load(name,file):
    spec=importlib.util.spec_from_file_location(name,R/file)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

g=load('timing_device_gate','gate.py')

def fixture():
    s=dict(format='sm5440-passive-v1',registers_are_cached='1',independently_calibrated='0',pump_enable_supported='0',
           timing_test='1',timing_attempted='1',timing_count='8',timing_restored='1',timing_admission_error='0',
           timing_exit_error='0',timing_error='0',timing_cleanup_error='0',timing_off_attempted='0',timing_off_error='0',
           fault='0',stopped='0',startup_pending='0',last_sample_error='0',timing_polls='20',timing_readiness_checks='1',
           timing_first_readiness_error='0',timing_started_ms='1000',timing_disabled_ms='1001',timing_enabled_ms='1051',
           timing_completed_ms='1190',timing_controls='08/df/08/df',timing_initial_int='00 00 20 01',timing_initial_status='00 00 20 00',
           timing_source0='1/2/3/960/965/5000/1800/1',timing_source1='1/2/3/1191/1195/5000/1800/1',
           timing_pack0='4/5/966/990/30/3700000/310',timing_pack1='4/5/1196/1200/30/3700000/310')
    for i in range(8):
        ready=1065+i*16
        a=[0]*11
        for high,low,raw in [(0,1,904),(9,10,3304)]:a[high]=raw>>5;a[low]=(raw&31)<<3
        a[8]=17
        s.update({f'timing_sample{i}_times':f'{ready-5}/{ready}/{ready+1}/{ready+1}/{ready+2}',
                  f'timing_sample{i}_int':'00 00 20 01',f'timing_sample{i}_status':'00 00 20 00',
                  f'timing_sample{i}_status_after':'00 00 20 00',f'timing_sample{i}_adc':' '.join(f'{x:02x}' for x in a),
                  f'timing_sample{i}_controls':'00/0b/df',f'timing_sample{i}_faults':'0x0'})
    p=dict(format='sm5714-current-port-v1',ret='0',online='1',charge_requested='1',instance='1',source_generation='2',budget_generation='3',
           budget_mv='5000',budget_ma='1800',voltage_uv='5000000',current_ua='1800000',started_ms='1210',completed_ms='1215')
    return s,p

def text(s):return '\n'.join(f'{k}={v}' for k,v in s.items())

class TimingEvidence(unittest.TestCase):
    def test_clean_actual_format(self):
        s,p=fixture();r=g.timing(text(s),text(p))
        self.assertEqual(r['samples'][0]['vbus_uv'],5000000)
        self.assertEqual(r['samples'][0]['vbat_uv'],3700000)
        self.assertFalse(r['software_ocp_verified']);self.assertFalse(r['pump_ON'])

    def test_terminal_failures(self):
        for key,value in [('timing_count','7'),('timing_error','-110'),('timing_cleanup_error','-5'),('fault','1'),('timing_off_attempted','1'),('timing_first_readiness_error','-5'),('timing_readiness_checks','21')]:
            with self.subTest(key=key):
                s,p=fixture();s[key]=value
                with self.assertRaises(ValueError):g.timing(text(s),text(p))

    def test_restoration_and_control_drift(self):
        for key,value in [('timing_controls','08/df/09/df'),('timing_sample3_controls','04/0b/df'),('timing_sample3_controls','00/09/df'),('timing_sample3_controls','00/0b/de')]:
            s,p=fixture();s[key]=value
            with self.assertRaises(ValueError):g.timing(text(s),text(p))

    def test_new_ready_and_live_faults(self):
        for key,value in [('timing_sample2_int','00 00 20 00'),('timing_sample2_int','00 00 22 01'),('timing_sample2_status_after','00 00 60 00')]:
            s,p=fixture();s[key]=value
            with self.assertRaises(ValueError):g.timing(text(s),text(p))

    def test_native_epoch_and_pack_reject(self):
        for key,value in [('timing_source1','1/7/3/1191/1195/5000/1800/1'),('timing_pack1','4/7/1196/1200/30/3700000/310'),('timing_pack0','4/5/966/990/30/3700000/450'),('timing_source0','1/2/3/960/965/9000/3000/2')]:
            s,p=fixture();s[key]=value
            with self.assertRaises(ValueError):g.timing(text(s),text(p))

    def test_current_source_changes(self):
        for key,value in [('online','2'),('budget_generation','4'),('budget_ma','3000'),('charge_requested','0')]:
            s,p=fixture();p[key]=value
            with self.assertRaises(ValueError):g.timing(text(s),text(p))

    def test_physical_bounds(self):
        for offset,value in [(4,1),(0,255),(8,40),(9,0)]:
            s,p=fixture();a=s['timing_sample0_adc'].split();a[offset]=f'{value:02x}';s['timing_sample0_adc']=' '.join(a)
            with self.assertRaises(ValueError):g.timing(text(s),text(p))

    def test_time_missing_and_malformed(self):
        for key,value in [('timing_sample1_times','1055/1056/1057/1058/1059'),('timing_completed_ms','4000'),('timing_disabled_ms','1040'),('timing_sample0_adc','00'),('timing_source0','1/2')]:
            s,p=fixture();s[key]=value
            with self.assertRaises(ValueError):g.timing(text(s),text(p))

    def test_original_fields_not_conflicting(self):
        s,p=fixture()
        with self.assertRaises(ValueError):g.timing(text(s)+'\ntiming_count=1',text(p))

class RunnerLifecycle(unittest.TestCase):
    def test_low_reserve_skips_full_preflight(self):
        h=load('timing_device_runner_fast_reserve','host_flow.py');h.configure()
        battery='POWER_SUPPLY_HEALTH=Good\nPOWER_SUPPLY_PRESENT=1\nPOWER_SUPPLY_CAPACITY=19\nPOWER_SUPPLY_VOLTAGE_NOW=3700000\nPOWER_SUPPLY_TEMP=310'
        with tempfile.TemporaryDirectory() as tmp:
            h.R=Path(tmp)
            with patch.object(h.p,'Recorder') as recorder,patch.object(h.base,'preflight') as full:
                recorder.return_value.folder=Path(tmp)
                recorder.return_value.adb.return_value=('@@boot\n'+'a'*32+'\n@@battery\n'+battery,0)
                with self.assertRaisesRegex(ValueError,'battery reserve'):h.preflight()
                full.assert_not_called()
                self.assertFalse(json.loads((Path(tmp)/'summary.json').read_text())['device_mutation'])

    def test_low_reserve_refuses_before_recovery(self):
        h=load('timing_device_runner_reserve','host_flow.py');h.configure()
        with tempfile.TemporaryDirectory() as tmp:
            h.R=Path(tmp);(h.R/'preflight').mkdir()
            h.write(h.R/'preflight/summary.json',dict(verdict='READY_FOR_REGISTERED_ONE_BOOT',authenticated_wifi=True,
                                                     boot_id='a'*32,collected_at_epoch=h.time.time()))
            with patch.object(h.p,'Recorder') as recorder,patch.object(h,'identity',return_value=({},'a'*32,{'soc':19},{})),patch.object(h.h,'enter_recovery') as recovery:
                recorder.return_value.adb.return_value=('raw',0)
                with self.assertRaisesRegex(ValueError,'flash reserve'):h.install_once()
                recovery.assert_not_called()
                self.assertFalse((h.R/'mutation-state.json').exists())

    def test_no_restore_replay(self):
        h=load('timing_device_runner_restore_replay','host_flow.py')
        with tempfile.TemporaryDirectory() as tmp:
            h.R=Path(tmp);h.write(h.R/'mutation-state.json',dict(rollback_required=False))
            with patch.object(h,'verify_inputs') as verify:
                with self.assertRaisesRegex(ValueError,'already restored'):h.restore()
                verify.assert_not_called()

    def test_import_and_registration(self):
        h=load('timing_device_runner','host_flow.py');h.configure()
        self.assertIn('test318',h.h.STAGE);self.assertIn('test318',h.h.TMP)
        self.assertFalse(h.PLAN['PPS']);self.assertFalse(h.PLAN['pump_ON'])
        self.assertEqual(h.PLAN['normal_candidate_boots'],1)

    def test_failure_always_restores_once(self):
        h=load('timing_device_runner_failure','host_flow.py')
        with tempfile.TemporaryDirectory() as tmp:
            h.R=Path(tmp);h.p.SERIAL='R52X10045LT'
            def install():
                h.write(h.R/'mutation-state.json',dict(rollback_required=True))
                raise ValueError('native ADC fault')
            with patch.object(h,'verify_inputs'),patch.object(h,'install_once',side_effect=install) as start,patch.object(h,'restore') as restore:
                with self.assertRaisesRegex(RuntimeError,'first non-clean'):h.run()
                start.assert_called_once();restore.assert_called_once_with(from_recovery=True)
                self.assertEqual(json.loads((h.R/'first-failure.json').read_text())['error'],'native ADC fault')

    def test_success_still_restores(self):
        h=load('timing_device_runner_success','host_flow.py')
        with tempfile.TemporaryDirectory() as tmp:
            h.R=Path(tmp);h.p.SERIAL='gts9wifi-0001'
            def install():h.write(h.R/'mutation-state.json',dict(rollback_required=True));return {'capture':'ok'}
            with patch.object(h,'verify_inputs'),patch.object(h,'install_once',side_effect=install),patch.object(h,'restore') as restore:
                self.assertEqual(h.run(),{'capture':'ok'});restore.assert_called_once_with(from_recovery=False)

    def test_previous_mutation_refuses(self):
        h=load('timing_device_runner_replay','host_flow.py')
        with tempfile.TemporaryDirectory() as tmp:
            h.R=Path(tmp);(h.R/'mutation-state.json').write_text('{}')
            with patch.object(h,'verify_inputs'),patch.object(h,'install_once') as install:
                with self.assertRaises(ValueError):h.run()
                install.assert_not_called()

if __name__=='__main__':unittest.main()
