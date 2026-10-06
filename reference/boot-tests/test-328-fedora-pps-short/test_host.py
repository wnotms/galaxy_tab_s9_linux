#!/usr/bin/env python3
import importlib.util,json,unittest
from pathlib import Path
from unittest.mock import patch
r=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('flow328',r/'host_flow.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f);f.configure()
class IdentityTests(unittest.TestCase):
 def setUp(self):
  self.raw=(r/'preflight/current-state.txt').read_text();self.flag=f.PACKAGE['cmdline_flag']
 def on(self):
  return self.raw.replace('@@cmdline\n','@@cmdline\n'+self.flag+' ').replace('@@direct-default\nN','@@direct-default\nY')
 def test_current_baseline(self):f.identity(self.raw,False)
 def test_boot_opt_in(self):f.identity(self.on(),True)
 def test_missing_opt_in(self):
  with self.assertRaises(ValueError):f.identity(self.raw,True)
 def test_repeated_flag(self):
  with self.assertRaises(ValueError):f.identity(self.on().replace(self.flag,self.flag+' '+self.flag),True)
 def test_param_off_with_flag(self):
  with self.assertRaises(ValueError):f.identity(self.on().replace('@@direct-default\nY','@@direct-default\nN'),True)
 def test_wrong_boot(self):
  with self.assertRaises(ValueError):f.identity(self.on(),True,'a'*32)
 def test_wrong_notes(self):
  with self.assertRaises(ValueError):f.identity(self.on().replace(f.PLAN['candidate_notes_sha256'],'a'*64),True)
 def test_soc80_entry_blocked(self):
  with self.assertRaises(ValueError):f.identity(self.on().replace('CAPACITY=79','CAPACITY=80'),True)
 def test_final_soc80_permitted_without_new_pps(self):f.identity(self.raw.replace('CAPACITY=79','CAPACITY=80'),False,final=True)
 def test_no_new_modules_archive(self):self.assertFalse(any(n.endswith('tar.gz') for n in f.STAGED))
 def test_source_unchanged(self):
  self.assertEqual(f.PACKAGE['baseline_partitions']['vendor_boot'],f.PACKAGE['candidate_partitions']['vendor_boot'])
  self.assertEqual(f.PLAN['baseline_config_sha256'],f.PLAN['candidate_config_sha256'])
if __name__=='__main__':unittest.main()
