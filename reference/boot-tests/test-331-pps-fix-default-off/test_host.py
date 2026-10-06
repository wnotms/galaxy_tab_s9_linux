#!/usr/bin/env python3
import copy,importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
R=Path(__file__).resolve().parent

def load(name,p):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
G=load('test331_gate',R/'gate.py');H=load('test331_flow',R/'host_flow.py');P=json.loads((R/'registration.json').read_text())
BOOT='a'*32
class Gates(unittest.TestCase):
    def setUp(self):
        self.s={'boot':BOOT,'boot-end':BOOT,'uname':'7.2.0-rc3-gts9wifi-dirty','cmdline':P['runtime_cmdline'],'identity':P['candidate_config_sha256']+' -\n'+P['candidate_notes_sha256']+' notes','battery':'POWER_SUPPLY_PRESENT=1\nPOWER_SUPPLY_HEALTH=Good\nPOWER_SUPPLY_VOLTAGE_MAX_DESIGN=4440000\nPOWER_SUPPLY_CAPACITY=82\nPOWER_SUPPLY_VOLTAGE_NOW=4276000\nPOWER_SUPPLY_TEMP=322\nPOWER_SUPPLY_CURRENT_NOW=986000','pack-thermal':'sm5714-battery\nenabled\n32200','usb':'POWER_SUPPLY_ONLINE=1\nPOWER_SUPPLY_USB_TYPE=[SDP]\nPOWER_SUPPLY_INPUT_CURRENT_LIMIT=1800000','tcpm':'POWER_SUPPLY_ONLINE=1\nPOWER_SUPPLY_USB_TYPE=[PD]\nPOWER_SUPPLY_VOLTAGE_NOW=5000000\nPOWER_SUPPLY_VOLTAGE_MAX=5000000\nPOWER_SUPPLY_CURRENT_MAX=1800000','dcc':'absent','failed':'','services':'active\nactive\nactive','roles':'[sink]\n[device]','network':'usb0    inet 169.254.42.1/16','direct-default':'N','driver':'../../../drivers/sm5440-fedora'}
        self.pump=dict(boot_before=BOOT,boot_after=BOOT,driver='sm5440-fedora',register=16,value=3,config_data_written=False)
    def reject(self,key,value):
        self.s[key]=value
        with self.assertRaises(ValueError):G.identity(self.s,P,'candidate')
    def test_default_off_above_direct_soc_is_ordinary_only(self):self.assertEqual(G.identity(self.s,P,'candidate')[1]['soc'],82);self.assertFalse(P['PPS']);self.assertFalse(P['pump_ON'])
    def test_boot_changed(self):self.reject('boot-end','b'*32)
    def test_identity_drift(self):self.reject('identity','0'*64+' -\n'+'1'*64+' notes')
    def test_cmdline_opt_in(self):self.reject('cmdline',P['runtime_cmdline']+' sm5440_fedora.direct_charge=1')
    def test_no_dcc(self):self.reject('dcc','present')
    def test_failed_unit(self):self.reject('failed','upower.service failed')
    def test_gadget_host_role(self):self.reject('roles','[sink]\n[host]')
    def test_new_driver_default_on(self):self.reject('direct-default','Y')
    def test_wrong_provider(self):self.reject('driver','sm5440-direct')
    def test_pack_thermal_invalid(self):self.reject('pack-thermal','sm5714-battery\ndisabled\n32200')
    def test_no_pps(self):self.reject('tcpm',self.s['tcpm'].replace('[PD]','[PD_PPS]'))
    def test_source_budget_exceeded(self):self.reject('usb',self.s['usb'].replace('1800000','1825000'))
    def test_accepted_baseline_provider(self):
        self.pump['driver']='sm5440-passive'
        self.assertEqual(G.pump(json.dumps(self.pump),BOOT,'baseline')['driver'],'sm5440-passive')
    def test_stable_off(self):self.assertEqual(G.pump(json.dumps(self.pump),BOOT,'candidate')['value'],3)
    def test_actual_pump_on(self):
        self.pump['value']=7
        with self.assertRaises(ValueError):G.pump(json.dumps(self.pump),BOOT,'candidate')
    def test_pump_boot_mismatch(self):
        self.pump['boot_after']='b'*32
        with self.assertRaises(ValueError):G.pump(json.dumps(self.pump),BOOT,'candidate')
    def test_pointer_read_only(self):
        self.pump['config_data_written']=True
        with self.assertRaises(ValueError):G.pump(json.dumps(self.pump),BOOT,'candidate')
    def test_network_packet_marker(self):
        for k in ['current_command','candidate_command']:self.assertIn('echo @@network;',P[k]);self.assertEqual(P[k].count('echo @@boot-end;'),1)
    def test_host_wifi_failure_requires_authenticated_ncm(self):
        with tempfile.TemporaryDirectory() as temp:
            rec=Mock();rec.folder=Path(temp)
            with patch.object(H.base,'wifi_rescue',side_effect=H.p.CaptureError('host no route')),patch.object(H.h,'ssh') as ssh:
                result=H.rescue(rec,self.s,BOOT)
                ssh.assert_called_once_with(rec,'ncm-rescue','169.254.42.1',BOOT)
                self.assertFalse(result['wireless_PPS_allowed'])
                self.assertFalse(result['wifi_authenticated'])
    def test_both_transports_fail_is_stop(self):
        with tempfile.TemporaryDirectory() as temp:
            rec=Mock();rec.folder=Path(temp)
            with patch.object(H.base,'wifi_rescue',side_effect=H.p.CaptureError('host no route')),patch.object(H.h,'ssh',side_effect=H.p.CaptureError('NCM fails')):
                with self.assertRaises(H.p.CaptureError):H.rescue(rec,self.s,BOOT)
    def test_first_failure_restores_once_without_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);(folder/'mutation-state.json').write_text('{"rollback_required":true}')
            with patch.object(H,'R',folder),patch.object(H,'install',side_effect=ValueError('device fault')) as install,patch.object(H,'restore') as restore:
                H.p.SERIAL='gts9wifi-0001'
                with self.assertRaises(ValueError):H.run()
                install.assert_called_once();restore.assert_called_once_with(from_recovery=False)
                self.assertTrue(json.loads((folder/'first-failure.json').read_text())['stopped'])
    def test_cmdline_whitespace_keeps_ordered_identity(self):
        self.s['cmdline']='   '.join(P['runtime_cmdline'].split())
        G.identity(self.s,P,'candidate')
    def test_cmdline_reordering_rejected(self):
        tokens=P['runtime_cmdline'].split();tokens[0],tokens[1]=tokens[1],tokens[0]
        self.reject('cmdline',' '.join(tokens))
    def test_cmdline_missing_duplicate_rejected(self):
        tokens=P['runtime_cmdline'].split();self.assertGreater(tokens.count('nokaslr'),1)
        tokens.remove('nokaslr');self.reject('cmdline',' '.join(tokens))
    def test_old_candidate_notes_rejected(self):
        self.reject('identity',P['candidate_config_sha256']+' -\n'+'5ec694b48a1234a269695e50d1293c597f045adf28992b8a70a513411a73cb41 notes')

class ModuleSlots(unittest.TestCase):
    def fixture(self,root):
        import hashlib,tarfile
        base=root/'usr/lib/modules';current=base/'7.2.0-rc3-gts9wifi-dirty';current.mkdir(parents=True)
        (root/'etc').mkdir();(root/'etc/machine-id').write_text('3c2a1b8f2d624db4b5ffdc836050fcf6\n')
        other=base/'.gts9-test327-tested';other.mkdir();(other/'untouched').write_text('historical')
        candidate=root/'candidate';candidate.mkdir()
        for i in range(181):
            (current/str(i)).write_bytes(b'old');(candidate/str(i)).write_bytes(b'new')
        for folder,name in [(current,'original.sha'),(candidate,'candidate.sha')]:
            (root/name).write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(folder.iterdir())))
        archive=root/'candidate.tar.gz'
        with tarfile.open(archive,'w:gz') as tar:
            tar.add(candidate,arcname=current.name)
        return base,current,other,archive
    def swap(self,root,mode,*args):
        import subprocess
        return subprocess.run(['sh',str(R/'module-swap.sh'),str(root),mode,*map(str,args)],capture_output=True)
    def test_fresh331_swap_and_restore_leave327_untouched(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);base,current,other,archive=self.fixture(root)
            result=self.swap(root,'install',root/'candidate.sha',archive,root/'original.sha')
            self.assertEqual(result.returncode,0,result.stderr.decode())
            self.assertEqual((current/'0').read_bytes(),b'new')
            self.assertEqual((base/'.gts9-test331-original/0').read_bytes(),b'old')
            result=self.swap(root,'restore',root/'original.sha')
            self.assertEqual(result.returncode,0,result.stderr.decode())
            self.assertEqual((current/'0').read_bytes(),b'old')
            self.assertEqual((base/'.gts9-test331-tested/0').read_bytes(),b'new')
            self.assertEqual((other/'untouched').read_text(),'historical')
    def test_existing331_slot_rejects_before_current_rename(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);base,current,other,archive=self.fixture(root)
            (base/'.gts9-test331-original').mkdir()
            result=self.swap(root,'install',root/'candidate.sha',archive,root/'original.sha')
            self.assertNotEqual(result.returncode,0)
            self.assertEqual((current/'0').read_bytes(),b'old')
            self.assertFalse((base/'.gts9-test331-stage').exists())

if __name__=='__main__':unittest.main()
