"""New OFF observation/parser and manual source boot lifecycle, fully offline."""
import importlib.util,unittest,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reference/boot-tests/test-324-native-oneshot-off'
spec=importlib.util.spec_from_file_location('oneshot_gate',R/'gate.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)

def fixture():
 d=dict(oneshot_attempted=1,oneshot_finished=1,oneshot_count=4,oneshot_error=0,oneshot_cleanup_error=0,oneshot_off_error=0,deadline_ms=100,calibrated=0,OCP_verified=0,pump_ON=0,oneshot_readiness_checks=1,oneshot_first_readiness_error=0)
 def raw(n):return [n>>5,(n&31)<<3]
 adc=raw(4904)+[0,0]+raw(0)+[0,0,15]+raw(3504)
 for i in range(4):
  p='sample'+str(i)+'_';t=1000+200*i
  d.update({p+'times':f'{t}/{t}/{t+20}/{t+55}',p+'result':'0/0/3/1/0/1/1/1',p+'control':'0c/0d/df',p+'events':'00 00 20 01',p+'status':'00 00 20 00',p+'adc':' '.join(f'{n:02x}' for n in adc),p+'physical':'9000000/3800000/0/300',p+'pack_before':f'{t-10}/{t-1}/3800000/500000/300',p+'pack_after':f'{t+56}/{t+60}/3800000/500000/300'})
 return d

def packet(d):return ''.join(f'{k}={v}\n' for k,v in d.items())

class EvidenceTests(unittest.TestCase):
 def test_clean_scope_does_not_grant_ON(self):
  result=g.oneshot(packet(fixture()));self.assertEqual(len(result['samples']),4);self.assertFalse(result['pump_ON']);self.assertFalse(result['calibrated']);self.assertEqual(result['full_port_verdict'],'NOT_READY')
 def test_native_terminal_and_cleanup_failures(self):
  for k in ('oneshot_error','oneshot_cleanup_error','oneshot_off_error'):
   with self.subTest(k=k):d=fixture();d[k]=-5;self.assertRaises(ValueError,g.oneshot,packet(d))
 def test_startup_no_attempt_or_partial_refused(self):
  for k,v in [('oneshot_attempted',0),('oneshot_finished',0),('oneshot_count',0),('oneshot_count',3)]:
   with self.subTest(k=k,v=v):d=fixture();d[k]=v;self.assertRaises(ValueError,g.oneshot,packet(d))
 def test_deadline_no_READY_stale_foreign_invalid(self):
  for k,v in [('sample0_times','1000/1000/1020/1101'),('sample0_result','0/0/3/0/0/1/1/1'),('sample0_result','0/0/3/1/1/1/1/1'),('sample0_result','0/0/3/1/0/1/1/0'),('sample1_times','1000/1000/1020/1055'),('sample0_pack_before','1100/1110/3800000/500000/300')]:
   with self.subTest(k=k,v=v):d=fixture();d[k]=v;self.assertRaises(ValueError,g.oneshot,packet(d))
 def test_control_fault_current_temperature_or_raw_refused(self):
  for k,v in [('sample0_control','0c/0f/df'),('sample0_events','00 00 80 01'),('sample0_status','00 00 00 00'),('sample0_physical','9000000/3800000/625/300'),('sample0_physical','9501000/3800000/0/300'),('sample0_pack_after','1056/1060/3800000/500000/420')]:
   with self.subTest(k=k,v=v):d=fixture();d[k]=v;self.assertRaises(ValueError,g.oneshot,packet(d))
 def test_missing_duplicate_evidence_refused(self):
  d=fixture();del d['sample2_adc'];self.assertRaises(KeyError,g.oneshot,packet(d));self.assertRaises(ValueError,g.oneshot,packet(fixture())+'oneshot_error=0\n')
 def test_no_automatic_candidate_reboot_or_second_install(self):
  import ast
  tree=ast.parse((R/'host_flow.py').read_text());f=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='install');body=ast.unparse(f)
  self.assertNotIn('normal-reboot',body);self.assertIn('one install only',body);self.assertIn('candidate-installed-awaiting-owner-fixed9-boot',body)
 def test_exact323_unconditional_paired_rollback(self):
  body=(R/'host_flow.py').read_text();self.assertIn('rollback-accepted323-boot.img',body);self.assertIn('.gts9-test324-original',body);self.assertIn('rollback-modules.sha256',body);self.assertNotIn('rollback-accepted311-boot.img',body)
 def test_actual323_baseline_keeps_higher_PC_grant(self):
  import gzip
  spec=importlib.util.spec_from_file_location('oneshot_flow_test',R/'host_flow.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f);f.configure()
  raw=gzip.decompress((R.parent/'test-323-pc-source-budget/endpoint/current-state.txt.gz').read_bytes()).decode().replace('\r','')
  sec,boot,battery,snapshot=f.baseline_identity(raw,'baseline')
  self.assertEqual(g.values(sec['usb'])['POWER_SUPPLY_INPUT_CURRENT_LIMIT'],'1800000')
  self.assertEqual(boot,'fca646a88cc0405c814d36cde33baa9e')

if __name__=='__main__':unittest.main()
