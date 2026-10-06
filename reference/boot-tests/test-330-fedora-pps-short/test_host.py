#!/usr/bin/env python3
import importlib.util,unittest
from unittest.mock import patch
from pathlib import Path
r=Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location('flow330',r/'host_flow.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.configure();f=m.f
class CmdlineTests(unittest.TestCase):
 def setUp(self):self.raw=(r.parent/'test-328-fedora-pps-short/candidate-admission/current-state.txt').read_text()
 def bad(self,raw):
  with self.assertRaises(ValueError):m.identity(raw,True)
 def test_actual_loader_single_separator(self):m.identity(self.raw,True)
 def test_whitespace_only(self):m.identity(self.raw.replace('console=tty0 ', 'console=tty0   '),True)
 def test_reordered_tokens(self):self.bad(self.raw.replace('console=tty0 msm.separate_gpu_kms=1','msm.separate_gpu_kms=1 console=tty0'))
 def test_missing_flag(self):self.bad(self.raw.replace(f.PACKAGE['cmdline_flag'],''))
 def test_duplicate_flag(self):self.bad(self.raw.replace(f.PACKAGE['cmdline_flag'],f.PACKAGE['cmdline_flag']+' '+f.PACKAGE['cmdline_flag']))
 def test_changed_flag_value(self):self.bad(self.raw.replace(f.PACKAGE['cmdline_flag'],'sm5440_fedora.direct_charge=0'))
 def test_extra_parameter(self):self.bad(self.raw.replace('console=tty0','console=tty0 panic_on_oops=1'))
 def test_changed_parameter(self):self.bad(self.raw.replace('panic=0','panic=10'))
 def test_missing_duplicate_nokaslr(self):self.bad(self.raw.replace('nokaslr ', '',1))
 def test_parameter_N(self):self.bad(self.raw.replace('@@direct-default\nY','@@direct-default\nN'))
 def test_changed_notes(self):self.bad(self.raw.replace(f.PLAN['candidate_notes_sha256'],'a'*64))
 def test_wrong_boot(self):
  with self.assertRaises(ValueError):m.identity(self.raw,True,'a'*32)
 def test_soc80_still_blocked(self):self.bad(self.raw.replace('CAPACITY=52','CAPACITY=80'))
 def test_emergency_uses_original323_identity_plan(self):
  with patch.object(m,'ORIGINAL_RESTORE',return_value='restored') as restore:
   self.assertEqual(m.restore(True),'restored');restore.assert_called_once_with(True)
   self.assertEqual(f.old.R,r.parent/'test-327-fedora-default-off')
 def test_guard_exact(self):self.assertEqual((r/'guard.py').read_bytes(),(r.parent/'test-328-fedora-pps-short/guard.py').read_bytes())
if __name__=='__main__':unittest.main()
