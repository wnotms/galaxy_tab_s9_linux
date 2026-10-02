"""Replay retained refusal against real C predicates; no hardware access."""
import copy
import ctypes
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import sm5440_startup_refusal as m
from test_sm5714_policy import function
ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'reference/boot-tests/test-292-passive-observation/final-diagnostic'
CONFIG=ROOT/'out/kernel-x710-263-passive/config'
VALUES=['vbus_uv','vbat_uv','ibus_ua','die_decic','faults','mode_before','mode_after',
        'int4_wait','online','cntl2','vbuscntl','vbatcntl','prtncntl']
class RefusalTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.current=(E/'current-state.txt').read_text();cls.journal=(E/'kernel-json.txt').read_text();cls.config=CONFIG.read_bytes();cls.boot=json.loads((E/'summary.json').read_text())['boot_id'];art=json.loads((E.parent.parent/'test-263-sm5440-adc-snapshot/ARTIFACTS.json').read_text())['artifacts'];cls.identity=dict(boot_id=cls.boot,config_sha256=art['config']['sha256'],notes_sha256=art['kernel-notes.bin']['sha256'])
  historical=subprocess.run(['git','show','ea938b245bff3ae9e3c1828751ea149a90337992:kernel/drivers/sm5440-direct.c'],cwd=ROOT,check=True,capture_output=True,text=True).stdout
  cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup);base=Path(cls.temp.name)
  header=subprocess.run(['git','show','ea938b245bff3ae9e3c1828751ea149a90337992:kernel/drivers/sm5440-hw.h'],cwd=ROOT,check=True,capture_output=True,text=True).stdout;(base/'baseline-hw.h').write_text(header)
  code='#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;\n#define BIT(n) (1U<<(n))\n#define GENMASK(h,l) (((~0U)>>(31-(h))) & ((~0U)<<(l)))\n#include "'+str(base/'baseline-hw.h')+'"\n'+function(historical,'struct sm5440_sample {')+';\n'
  for marker in ['static bool sm5440_passive_pc_sample(','static bool sm5440_startup_matches(']:
   code+=function(historical,marker)+'\n'
  assign='\n'.join('s->'+k+'=v['+str(i)+'];' for i,k in enumerate(VALUES));code+='void assign(struct sm5440_sample *s,unsigned int *v){'+assign+'}\nint check(unsigned int *v,unsigned int *w){struct sm5440_sample s={0},t={0};assign(&s,v);assign(&t,w);return sm5440_startup_matches(&s,&t);}\nunsigned int decode(unsigned int p){u8 s[]={p,p>>8,p>>16,p>>24};return sm5440_decode_faults(s,false,0);}\nunsigned int voltage(unsigned int h,unsigned int l){return sm5440_vbat_uv(h,l);}\n'
  (base/'oracle.c').write_text(code);subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-shared','-fPIC',str(base/'oracle.c'),'-o',str(base/'oracle.so')],check=True,capture_output=True,text=True);cls.c=ctypes.CDLL(str(base/'oracle.so'));cls.c.check.argtypes=[ctypes.POINTER(ctypes.c_uint)]*2;cls.c.check.restype=ctypes.c_int;cls.c.decode.argtypes=[ctypes.c_uint];cls.c.decode.restype=ctypes.c_uint;cls.c.voltage.argtypes=[ctypes.c_uint]*2;cls.c.voltage.restype=ctypes.c_uint
 def replay(self,current=None,journal=None,config=None,identity=None):
  return m.analyze(self.current if current is None else current,self.journal if journal is None else journal,self.config if config is None else config,**(self.identity if identity is None else identity))
 def samples(self):
  sn=m.fields(m.sections(self.current)['snapshot']);return m.sample(sn,'sample'),m.sample(sn,'startup')
 def test_real_refusal_attributed_without_grant(self):
  result=self.replay();self.assertEqual(result['sample_refusal_reasons'],['VBAT_outside_startup_window']);self.assertEqual(result['decoded_VBAT_uv'],3498500);self.assertEqual(result['below_startup_lower_bound_uv'],1500);self.assertTrue(result['deadline_expiry_excluded']);self.assertEqual(result['startup_to_last_sample_ticks'],576);self.assertEqual(result['startup_to_failure_source_us'],2304099)
  for k in ['PPS_authorized','pump_ON_authorized','policy_admission','active_freshness_grant','same_fault_retry_authorized','changing_bounds_justified','synchronous_gauge_comparison']:self.assertIs(result[k],False)
  self.assertIsNone(result['physical_voltage_error_uv'])
 def test_actual_C_and_reported_failure_agree(self):
  s,i=self.samples();a=(ctypes.c_uint*len(VALUES))(*(s[k] for k in VALUES));b=(ctypes.c_uint*len(VALUES))(*(i[k] for k in VALUES));self.assertEqual(self.c.check(a,b),0);self.assertEqual(self.c.voltage(0x5a,0xa8),3498500)
 def test_predicate_reasons_match_C_at_boundaries(self):
  s,i=self.samples();s.update(vbat_uv=4000000)
  boundaries={'vbus_uv':[4499999,4500000,5500000,5500001],'vbat_uv':[3499999,3500000,4299999,4300000],'ibus_ua':[0,1,1800000],'die_decic':[224,225,419,420],'faults':[0,128],'mode_before':[0,1,4,12],'mode_after':[0,1,4,12],'online':[0,1],'int4_wait':[0,1,2,3],'cntl2':[242,243],'vbuscntl':[231,230],'vbatcntl':[55,54],'prtncntl':[254,255]}
  for field,vals in boundaries.items():
   for value in vals:
    with self.subTest(field=field,value=value):
     new=dict(s,**{field:value});a=(ctypes.c_uint*len(VALUES))(*(new[k] for k in VALUES));b=(ctypes.c_uint*len(VALUES))(*(i[k] for k in VALUES));self.assertEqual(bool(self.c.check(a,b)),not m.sample_reasons(new,i))
 def test_predicate_combined_faults_match_C(self):
  s,i=self.samples();rng=random.Random(293)
  for _ in range(512):
   s.update(vbat_uv=rng.choice([3498500,3500000,4000000,4300000]),mode_before=rng.randrange(16),mode_after=rng.randrange(16),int4_wait=rng.randrange(16),faults=rng.choice([0,1,128]),online=bool(rng.randrange(2)))
   a=(ctypes.c_uint*len(VALUES))(*(s[k] for k in VALUES));b=(ctypes.c_uint*len(VALUES))(*(i[k] for k in VALUES));self.assertEqual(bool(self.c.check(a,b)),not m.sample_reasons(s,i))
 def test_fault_decode_all_single_byte_values_match_C(self):
  for pos in range(4):
   for value in range(256):
    st=bytearray(4);st[pos]=value;self.assertEqual(m.decode_faults(st),self.c.decode(value<<(pos*8)))
 def test_raw_ADC_mismatch_refused(self):
  with self.assertRaisesRegex(ValueError,'ADC bytes'):self.replay(current=self.current.replace('sample_vbat_uv=3498500','sample_vbat_uv=3500000'))
 def test_fault_bitmap_mismatch_refused(self):
  with self.assertRaisesRegex(ValueError,'fault bitmap'):self.replay(current=self.current.replace('sample_faults=0x0','sample_faults=0x80'))
 def test_empty_journal_refused(self):
  with self.assertRaisesRegex(ValueError,'empty'):self.replay(journal='')
 def test_other_boot_journal_refused(self):
  with self.assertRaisesRegex(ValueError,'boot'):self.replay(journal=self.journal.replace(self.boot,'ab'*16))
 def test_missing_transition_refused(self):
  with self.assertRaisesRegex(ValueError,'transition'):self.replay(journal=self.journal.replace('passive startup confirmation failed','different message'))
 def test_duplicate_transition_refused(self):
  row=next(x for x in self.journal.splitlines() if 'passive startup confirmation failed' in x)
  with self.assertRaisesRegex(ValueError,'transition'):self.replay(journal=self.journal.rstrip()+'\n'+row+'\n')
 def test_deadline_or_wrap_unresolved(self):
  with self.assertRaisesRegex(ValueError,'deadline'):self.replay(current=self.current.replace('sample_stamp_jiffies=4294892946','sample_stamp_jiffies=4294895000'))
 def test_sample_journal_chronology_disagrees(self):
  with self.assertRaisesRegex(ValueError,'time disagreement'):self.replay(current=self.current.replace('sample_stamp_jiffies=4294892946','sample_stamp_jiffies=4294892996'))
 def test_config_identity_mismatch(self):
  with self.assertRaisesRegex(ValueError,'config identity'):self.replay(config=self.config+b'# altered\n')
 def test_notes_identity_mismatch(self):
  with self.assertRaisesRegex(ValueError,'notes'):self.replay(identity=dict(self.identity,notes_sha256='0'*64))
 def test_duplicate_snapshot_or_section(self):
  with self.assertRaisesRegex(ValueError,'duplicate'):self.replay(current=self.current.replace('sample_valid=1','sample_valid=1\nsample_valid=1'))
  with self.assertRaisesRegex(ValueError,'duplicate'):self.replay(current=self.current+'\n@@boot\n'+self.boot)
 def test_not_retained_successful_read_profile_refused(self):
  with self.assertRaisesRegex(ValueError,'profile'):self.replay(current=self.current.replace('last_sample_error=0','last_sample_error=-5'))
 def test_conflicting_uevent_property_refused(self):
  with self.assertRaisesRegex(ValueError,'contradictory'):self.replay(current=self.current.replace('POWER_SUPPLY_VOLTAGE_NOW=3879000','POWER_SUPPLY_VOLTAGE_NOW=3879000\nPOWER_SUPPLY_VOLTAGE_NOW=4000000',1))
 def test_vendor_integer_mV_vs_retained_microvolt_precision(self):
  h,l=0x5a,0xa8;vendor_mv=2048+(((h<<5)|(l>>3))*500)//1000
  self.assertEqual(vendor_mv,3498);self.assertEqual(self.c.voltage(h,l),3498500)
 def test_DCC_and_HZ_variant_refused(self):
  for needle,other in [(b'# CONFIG_HVC_DCC is not set',b'CONFIG_HVC_DCC=y'),(b'CONFIG_HZ=250',b'CONFIG_HZ=100')]:
   new=self.config.replace(needle,other)
   with self.assertRaisesRegex(ValueError,'HZ/DCC'):self.replay(config=new,identity=dict(self.identity,config_sha256=hashlib.sha256(new).hexdigest()),current=self.current.replace(self.identity['config_sha256'],hashlib.sha256(new).hexdigest()))
 def test_unsigned_and_register_width(self):
  with self.assertRaises(ValueError):m.unsigned('-1')
  with self.assertRaises(ValueError):m.unsigned(str(2**32))
  with self.assertRaisesRegex(ValueError,'register width'):self.replay(current=self.current.replace('sample_mode_after=0x01','sample_mode_after=256'))
if __name__=='__main__':unittest.main(verbosity=2)
