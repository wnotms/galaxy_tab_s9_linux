import importlib.util,unittest,copy
from pathlib import Path
R=Path(__file__).resolve().parent

def load(name,p):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
T=load('fixtures334',R/'test_host.py');M=load('restore334',R/'restoration.py')
class Restoration(unittest.TestCase):
    def setUp(self):
        f=T.Gates();f.setUp();self.s=copy.deepcopy(f.s);self.s.update({'cmdline':T.P['runtime_cmdline'],'fixed-check':'absent','identity':T.P['baseline_config_sha256']+' -\n'+T.P['baseline_notes_sha256']+' notes'})
        self.s['usb']=self.s['usb'].replace('[PD]','[SDP]').replace('1500000','1800000');self.s['tcpm']=self.s['tcpm'].replace('9000000','5000000').replace('1500000','1800000')
        self.s['battery']=self.s['battery'].replace('CAPACITY=67','CAPACITY=80')
    def test_normal_eighty_percent_is_allowed_only_for_restore(self):
        self.assertEqual(M.restored_identity(self.s,T.P,'baseline')[1]['soc'],80)
        with self.assertRaises(ValueError):T.G.identity(self.s,T.P,'baseline')
    def test_candidate_cannot_use_restore_gate(self):
        with self.assertRaises(ValueError):M.restored_identity(self.s,T.P,'candidate')
    def test_over_design_voltage_still_stops(self):
        self.s['battery']=self.s['battery'].replace('4116000','4440001')
        with self.assertRaises(ValueError):M.restored_identity(self.s,T.P,'baseline')
    def test_kernel_or_check_flag_drift_still_stops(self):
        for key,value in [('fixed-check','Y'),('identity','0'*64+' -\n'+'1'*64+' notes')]:
            saved=self.s[key];self.s[key]=value
            with self.assertRaises(ValueError):M.restored_identity(self.s,T.P,'baseline')
            self.s[key]=saved
    def test_pack_or_service_failure_still_stops(self):
        for key,value in [('pack-thermal','sm5714-battery\ndisabled\n32200'),('failed','upower.service failed')]:
            saved=self.s[key];self.s[key]=value
            with self.assertRaises(ValueError):M.restored_identity(self.s,T.P,'baseline')
            self.s[key]=saved
