"""Replay the actual full passive worker with isolated fixed9 diagnostic enabled."""
import ctypes,subprocess,unittest
from pathlib import Path
from unittest.mock import patch
import test_sm5440_passive as passive_fixture
from test_sm5714_policy import function
ROOT=Path(__file__).resolve().parents[1]

class WorkerTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  src=(ROOT/'kernel/drivers/sm5440-direct.c').read_text();real_run=subprocess.run
  def compile_diagnostic(argv,*args,**kwargs):
   path=next((Path(a) for a in argv if str(a).endswith('/passive.c')),None)
   if path:
    # Extend the existing mocked I2C fixture, not a replacement worker model.
    code=path.read_text();helpers='\n'.join(function(src,'static bool '+n+'(') for n in ['sm5440_passive_fixed9_sample','sm5440_oneshot_startup_revblk','sm5440_oneshot_startup_matches'])
    code='#define CONFIG_SM5440_ADC_ONESHOT_TEST 1\n'+code
    code=code.replace('int request_wait;};','int request_wait;struct {bool attempted;} oneshot;};')
    code=code.replace('static void sm5440_poll(',helpers+'\nstatic int native_calls;\nstatic void sm5440_oneshot_cycle(struct sm5440_direct *sm){sm->oneshot.attempted=true;native_calls++;}\nstatic void sm5440_poll(',1)
    code+='''
int transition(int scenario,int *out) {
 int ignored[7];sample(0,0,0,ignored);fake_jiffies=100;
 struct sm5440_direct sm={0};current=&sm;scheduled=changed=native_calls=0;
 /* Replay Test325: inactive REVBLK at9.437V,zeroIBUS,28C,VBAT4.0795V. */
 unsigned int vbus=5341,vbat=4063;
 regs[SM5440_ADC_VBUS]=vbus>>5;regs[SM5440_ADC_VBUS+1]=(vbus&31)<<3;
 regs[0x27]=vbat>>5;regs[0x28]=(vbat&31)<<3;
 regs[0x22]=regs[0x23]=0;regs[0x26]=11;regs[2]=0x62;regs[0x0a]=0x20;
 regs[SM5440_CNTL5]=1;regs[SM5440_CNTL2]=0xf2;regs[SM5440_VBUSCNTL]=0xe7;
 regs[SM5440_VBATCNTL]=0x37;regs[SM5440_PRTNCNTL]=0xfe;
 sm5440_poll(&sm.work.work);out[0]=sm.fault;out[1]=sm.startup_confirmations;out[2]=native_calls;
 fake_jiffies+=1000;fake_boottime_ms+=1000;
 if(scenario==1)regs[2]=2;
 if(scenario==2)regs[0x0a]=0x22;
 if(scenario==3)regs[SM5440_CNTL2]^=1;
 if(scenario==4){regs[0x1e]=904>>5;regs[0x1f]=(904&31)<<3;}
 if(scenario==5)fail_at=calls+1;
 if(scenario==6)sm5440_quiesce(&sm);
 if(scenario==7)fake_jiffies=6001;
 if(scenario==8)regs[0x23]=8;
 if(scenario==9)regs[0x26]=39;
 if(scenario==10)regs[0x27]=4504>>5,regs[0x28]=(4504&31)<<3;
 sm5440_poll(&sm.work.work);out[3]=sm.fault;out[4]=sm.startup_confirmations;out[5]=native_calls;
 fake_jiffies+=1000;fake_boottime_ms+=1000;
 if(scenario==11)regs[2]=2;
 sm5440_poll(&sm.work.work);out[6]=sm.fault;out[7]=sm.startup_confirmations;out[8]=native_calls;
 out[9]=sm.startup_sample.faults;out[10]=unsafe_writes;
 int before=calls;if(sm.fault)sm5440_poll(&sm.work.work);out[11]=calls-before;
 return 0;
}
''';path.write_text(code)
   try:return real_run(argv,*args,**kwargs)
   except subprocess.CalledProcessError as exc:raise AssertionError(exc.stderr) from exc
  with patch('subprocess.run',side_effect=compile_diagnostic):passive_fixture.PassiveHardwareTests.setUpClass.__func__(cls)
  cls.lib.transition.argtypes=[ctypes.c_int,ctypes.POINTER(ctypes.c_int)]
 def run_case(self,scenario=0):
  out=(ctypes.c_int*12)();self.assertEqual(self.lib.transition(scenario,out),0);return list(out)
 def test_actual_fixed9_worker_reaches_native_only_after_two_fresh_confirmations(self):
  v=self.run_case();self.assertEqual(v[:3],[0,2,0]);self.assertEqual(v[3:6],[0,1,0]);self.assertEqual(v[6:11],[0,0,1,128,0])
 def test_generic_fault_block_does_not_reject_admitted_initial_fixed9_context(self):
  self.assertEqual(self.run_case()[:3],[0,2,0])
 def test_repeated_or_live_revblk_remains_terminal(self):
  for scenario in [1,2,11]:
   with self.subTest(scenario=scenario):v=self.run_case(scenario);self.assertEqual(v[6],1);self.assertEqual(v[8],0);self.assertEqual(v[10:],[0,0])
 def test_control_drift_voltage_class_switch_and_I2C_fail_closed(self):
  for scenario in [3,4,5]:
   with self.subTest(scenario=scenario):v=self.run_case(scenario);self.assertEqual(v[6],1);self.assertEqual(v[8],0);self.assertEqual(v[10:],[0,0])
 def test_suspend_and_deadline_never_resume_confirmation(self):
  for scenario in [6,7]:
   v=self.run_case(scenario);self.assertEqual(v[6],1);self.assertEqual(v[8],0);self.assertEqual(v[10:],[0,0])
 def test_current_temperature_and_pack_bounds_still_stop(self):
  for scenario in [8,9,10]:
   v=self.run_case(scenario);self.assertEqual(v[6],1);self.assertEqual(v[8],0);self.assertEqual(v[10:],[0,0])

if __name__=='__main__':unittest.main()
