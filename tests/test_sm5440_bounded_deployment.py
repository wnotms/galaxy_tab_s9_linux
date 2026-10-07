"""Only the new Test338 admission/scoping adapter; no device access."""
import copy, importlib.util, json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reference/boot-tests/test-338-bounded-direct-1p8a'
spec=importlib.util.spec_from_file_location('bounded_deploy',R/'host_flow.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f);f.configure()
class DeploymentTests(unittest.TestCase):
    def packet(self,candidate=False):
        raw=(R/'preflight/current-state.txt').read_text()
        if candidate:
            raw=raw.replace(f.PLAN['baseline_notes_sha256'],f.PLAN['candidate_notes_sha256'])
            raw=raw.replace('@@cmdline\n','@@cmdline\n'+f.PLAN['cmdline_flag']+' ')
            raw=raw.replace('@@once\nabsent','@@once\nY')
        return raw
    def test_baseline(self):
        self.assertEqual(f.identity(self.packet(),'baseline')[1],'6dc80750ebdf41e7a4a898befdec7c63')
    def test_candidate(self):
        self.assertEqual(f.identity(self.packet(True),'candidate')[2]['soc'],58)
    def test_candidate_requires_unique_flag(self):
        self.assertRaises(ValueError,f.identity,self.packet(True).replace(f.PLAN['cmdline_flag'],'',1),'candidate')
        self.assertRaises(ValueError,f.identity,self.packet(True).replace(f.PLAN['cmdline_flag'],f.PLAN['cmdline_flag']+' '+f.PLAN['cmdline_flag'],1),'candidate')
    def test_candidate_requires_once_y(self):
        self.assertRaises(ValueError,f.identity,self.packet(True).replace('@@once\nY','@@once\nN'),'candidate')
    def test_baseline_forbids_once(self):
        self.assertRaises(ValueError,f.identity,self.packet().replace('@@once\nabsent','@@once\nY'),'baseline')
    def test_no_entry_soc_relaxation(self):
        self.assertRaises(ValueError,f.identity,self.packet(True).replace('POWER_SUPPLY_CAPACITY=58','POWER_SUPPLY_CAPACITY=80'),'candidate')
    def test_scope_and_namespace(self):
        self.assertTrue(f.authorized())
        self.assertEqual(f.h.TMP,'/tmp/gts9-test338')
        self.assertIn('gts9-test338',f.h.STAGE)
        self.assertNotEqual(json.loads((R/'staged-files.json').read_text())['module-swap.sh']['sha256'],json.loads((R.parent/'test-337-async-fixed-charge-restore/staged-files.json').read_text())['module-swap.sh']['sha256'])
if __name__=='__main__':unittest.main()
