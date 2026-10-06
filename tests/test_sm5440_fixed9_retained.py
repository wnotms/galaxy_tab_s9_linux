"""Actual retained-evidence parser and once-only rollback lifecycle, no hardware."""
import copy,importlib.util,json,unittest,ast
from pathlib import Path
from test_sm5440_oneshot_device import fixture,packet
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reference/boot-tests/test-325-fixed9-native-off'
spec=importlib.util.spec_from_file_location('retained325_tests',R/'gate.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
BOOT='a'*32

def snapshot():
 d=dict(fault=0,stopped=0,startup_pending=0,last_sample_error=0,pump_enable_supported=0,startup_retained=1,startup_faults='0x80',sample_faults=0)
 for prefix in ('startup_','sample_'):
  for k,v in dict(mode_before='0x01',mode_after='0x01',ibus_ua=0,vbus_uv=9400000,vbat_uv=3800000,die_decic=300,int4_wait='0x01',cntl2='0xf2',vbuscntl='0xe7',vbatcntl='0x37',prtncntl='0xfe').items():d[prefix+k]=v
 return d

def journal():
 rows=[]
 def add(ms,msg):rows.append({'_BOOT_ID':BOOT,'_TRANSPORT':'kernel','_SOURCE_MONOTONIC_TIMESTAMP':str(ms*1000),'__MONOTONIC_TIMESTAMP':str((ms+2000)*1000),'MESSAGE':msg})
 add(100,'sm5440-passive 0-0063: startup voltage pair seq=1 ADC-start=40ms ADC-read=90ms VBAT=3800000uV')
 add(110,'sm5440-passive 0-0063: passive startup REVBLK awaiting two fresh confirmations')
 add(450,'sm5440-passive 0-0063: startup voltage pair seq=2 ADC-start=400ms ADC-read=440ms VBAT=3800000uV')
 add(850,'sm5440-passive 0-0063: startup voltage pair seq=3 ADC-start=800ms ADC-read=840ms VBAT=3800000uV')
 add(860,'sm5440-passive 0-0063: passive startup REVBLK confirmed inactive; event retained')
 add(500,'sm5714-usbpd 3-0033: TCPM Sink budget: 9000 mV 1500 mA (not measured VBUS)')
 add(35000,'sm5714-usbpd 3-0033: TCPM Sink budget: 0 mV 0 mA (not measured VBUS)')
 add(36000,'sm5714-usbpd 3-0033: TCPM Sink budget: 5000 mV 1800 mA (not measured VBUS)')
 return rows

def lines(rows):return ''.join(json.dumps(r)+'\n' for r in rows)

class RetainedTests(unittest.TestCase):
 def call(self,d=None,s=None,rows=None):return g.retained_observation(packet(d or fixture()),packet(s or snapshot()),lines(rows or journal()),BOOT)
 def test_complete_scope_preserves_no_charging_grant(self):
  r=self.call();self.assertEqual(r['source_hold_ms'],34500);self.assertEqual(r['startup_confirmations'],2);self.assertFalse(r['PPS']);self.assertFalse(r['pump_ON']);self.assertFalse(r['calibrated'])
 def test_host_receipt_time_not_used(self):
  rows=journal()
  for row in rows:row['__MONOTONIC_TIMESTAMP']='999999999999'
  self.assertEqual(self.call(rows=rows)['source_hold_ms'],34500)
 def test_missing_or_foreign_timestamps(self):
  for name,value in [('_BOOT_ID','b'*32),('_TRANSPORT','stdout'),('_SOURCE_MONOTONIC_TIMESTAMP',None)]:
   rows=journal();rows[0][name]=value;self.assertRaises(ValueError,self.call,rows=rows)
 def test_missing_or_incomplete_startup_confirmations(self):
  for index in [0,1,2,3,4]:
   rows=journal();rows.pop(index);self.assertRaises(ValueError,self.call,rows=rows)
 def test_reused_or_late_confirmation_refused(self):
  rows=journal();rows[3]['MESSAGE']=rows[3]['MESSAGE'].replace('seq=3','seq=2');self.assertRaises(ValueError,self.call,rows=rows)
 def test_initial_latch_missing_or_live_fault_refused(self):
  for k,v in [('startup_retained',0),('startup_faults',129),('fault',1),('sample_faults',128),('startup_pending',1)]:
   s=snapshot();s[k]=v;self.assertRaises(ValueError,self.call,s=s)
 def test_control_or_voltage_class_drift_refused(self):
  for k,v in [('sample_cntl2','0xf3'),('sample_vbus_uv',5000000),('startup_vbus_uv',9500001),('startup_mode_after','0x05'),('sample_die_decic',420)]:
   s=snapshot();s[k]=v;self.assertRaises(ValueError,self.call,s=s)
 def test_no_logical_fixed9_or_excess_current_refused(self):
  for replacement in ['5000 mV 1500','9000 mV 1800']:
   rows=journal();rows[5]['MESSAGE']=rows[5]['MESSAGE'].replace('9000 mV 1500',replacement);self.assertRaises(ValueError,self.call,rows=rows)
 def test_budget_transition_inside_native_window_refused(self):
  rows=journal();rows.append(dict(rows[6],_SOURCE_MONOTONIC_TIMESTAMP='1200000'));self.assertRaises(ValueError,self.call,rows=rows)
 def test_protocol_reset_inside_native_window_refused(self):
  for text in ['TCPC hard reset','soft reset','USB detach','TCPC fault','I2C read error']:
   rows=journal();rows.append(dict(rows[6],_SOURCE_MONOTONIC_TIMESTAMP='1200000',MESSAGE=text));self.assertRaises(ValueError,self.call,rows=rows)
 def test_short_source_hold_or_missing_PC_return_refused(self):
  rows=journal();rows[6]['_SOURCE_MONOTONIC_TIMESTAMP']='10000000';self.assertRaises(ValueError,self.call,rows=rows)
  rows=journal();rows.pop();self.assertRaises(ValueError,self.call,rows=rows)
 def test_suspend_invalidates_timestamp_equivalence(self):
  rows=journal();rows.append(dict(rows[6],MESSAGE='PM: suspend entry (s2idle)'));self.assertRaises(ValueError,self.call,rows=rows)
 def test_native_failure_is_never_reinterpreted_as_retained_success(self):
  d=fixture();d['oneshot_error']=-110;self.assertRaises(ValueError,self.call,d=d)
 def test_no_automatic_candidate_reboot_second_install_or_ADC_trigger(self):
  tree=ast.parse((R/'host_flow.py').read_text());functions={f.name:ast.unparse(f) for f in tree.body if isinstance(f,ast.FunctionDef)}
  self.assertNotIn('normal-reboot',functions['install']);self.assertIn('one install only',functions['install'])
  self.assertIn('one retained capture only',functions['capture']);self.assertNotIn('time.sleep',functions['capture']);self.assertNotIn('ssh_command',functions['capture'])
  self.assertIn('rollback-accepted323-boot.img',functions['restore']);self.assertIn('.gts9-test325-original',functions['restore'])
  self.assertLess(functions['capture'].index("'kernel-json'"),functions['capture'].index('candidate_identity(raw)'))

class CleanupTests(unittest.TestCase):
 def setUp(self):
  from unittest.mock import patch
  self.patch=patch
  spec=importlib.util.spec_from_file_location('retained325_flow_test',R/'host_flow.py');self.f=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.f)
 def test_successful_capture_always_restores_before_return(self):
  calls=[]
  with self.patch.object(self.f,'capture',side_effect=lambda:calls.append('capture') or {'verdict':'OFF'}),self.patch.object(self.f,'restore',side_effect=lambda:calls.append('restore')),self.patch.object(self.f,'read',return_value={'rollback_required':True}):
   self.assertEqual(self.f.capture_and_restore()['capture']['verdict'],'OFF')
  self.assertEqual(calls,['capture','restore'])
 def test_failed_capture_restores_then_preserves_first_error(self):
  calls=[]
  with self.patch.object(self.f,'capture',side_effect=ValueError('native timeout')),self.patch.object(self.f,'restore',side_effect=lambda:calls.append('restore')),self.patch.object(self.f,'read',return_value={'rollback_required':True}):
   with self.assertRaisesRegex(ValueError,'native timeout'):self.f.capture_and_restore()
  self.assertEqual(calls,['restore'])
 def test_already_restored_replay_never_reboots_again(self):
  with self.patch.object(self.f,'capture',side_effect=ValueError('one capture only')),self.patch.object(self.f,'restore') as restore,self.patch.object(self.f,'read',return_value={'rollback_required':False}):
   self.assertRaises(ValueError,self.f.capture_and_restore);restore.assert_not_called()

if __name__=='__main__':unittest.main()
