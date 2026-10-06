#!/usr/bin/env python3
import copy,importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
R=Path(__file__).resolve().parent

def load(name,p):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
G=load('test332_gate',R/'gate.py');H=load('test332_flow',R/'host_flow.py');P=json.loads((R/'registration.json').read_text())
BOOT='a'*32
class Gates(unittest.TestCase):
    def setUp(self):
        self.s={'boot':BOOT,'boot-end':BOOT,'uname':'7.2.0-rc3-gts9wifi-dirty','cmdline':P['cmdline_flag']+' '+P['runtime_cmdline'],'fixed-check':'Y','identity':P['candidate_config_sha256']+' -\n'+P['candidate_notes_sha256']+' notes','battery':'POWER_SUPPLY_PRESENT=1\nPOWER_SUPPLY_HEALTH=Good\nPOWER_SUPPLY_VOLTAGE_MAX_DESIGN=4440000\nPOWER_SUPPLY_CAPACITY=67\nPOWER_SUPPLY_VOLTAGE_NOW=4116000\nPOWER_SUPPLY_TEMP=322\nPOWER_SUPPLY_CURRENT_NOW=986000','pack-thermal':'sm5714-battery\nenabled\n32200','usb':'POWER_SUPPLY_ONLINE=1\nPOWER_SUPPLY_USB_TYPE=[SDP]\nPOWER_SUPPLY_INPUT_CURRENT_LIMIT=1800000','tcpm':'POWER_SUPPLY_ONLINE=1\nPOWER_SUPPLY_USB_TYPE=[PD]\nPOWER_SUPPLY_VOLTAGE_NOW=5000000\nPOWER_SUPPLY_VOLTAGE_MAX=5000000\nPOWER_SUPPLY_CURRENT_MAX=1800000','dcc':'absent','failed':'','services':'active\nactive\nactive','roles':'[sink]\n[device]','network':'usb0    inet 169.254.42.1/16','direct-default':'N','driver':'../../../drivers/sm5440-fedora'}
        self.pump=dict(boot_before=BOOT,boot_after=BOOT,driver='sm5440-fedora',register=16,value=3,config_data_written=False)
    def reject(self,key,value):
        self.s[key]=value
        with self.assertRaises(ValueError):G.identity(self.s,P,'candidate')
    def test_default_off_above_direct_soc_is_ordinary_only(self):self.assertEqual(G.identity(self.s,P,'candidate')[1]['soc'],67);self.assertFalse(P['PPS']);self.assertFalse(P['pump_ON'])
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
        self.pump['driver']='sm5440-fedora'
        self.assertEqual(G.pump(json.dumps(self.pump),BOOT,'baseline')['driver'],'sm5440-fedora')
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
    def test_fixed_check_missing_or_duplicate_flag_is_rejected(self):
        self.reject('cmdline',P['runtime_cmdline'])
        self.reject('cmdline',P['cmdline_flag']+' '+P['cmdline_flag']+' '+P['runtime_cmdline'])
    def test_fixed_check_parameter_must_be_enabled(self):self.reject('fixed-check','N')
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
        self.s['cmdline']='   '.join(self.s['cmdline'].split())
        G.identity(self.s,P,'candidate')
    def test_cmdline_reordering_rejected(self):
        tokens=self.s['cmdline'].split();tokens[1],tokens[2]=tokens[2],tokens[1]
        self.reject('cmdline',' '.join(tokens))
    def test_cmdline_missing_duplicate_rejected(self):
        tokens=self.s['cmdline'].split();self.assertGreater(tokens.count('nokaslr'),1)
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
            self.assertEqual((base/'.gts9-test332-original/0').read_bytes(),b'old')
            result=self.swap(root,'restore',root/'original.sha')
            self.assertEqual(result.returncode,0,result.stderr.decode())
            self.assertEqual((current/'0').read_bytes(),b'old')
            self.assertEqual((base/'.gts9-test332-tested/0').read_bytes(),b'new')
            self.assertEqual((other/'untouched').read_text(),'historical')
    def test_existing331_slot_rejects_before_current_rename(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);base,current,other,archive=self.fixture(root)
            (base/'.gts9-test332-original').mkdir()
            result=self.swap(root,'install',root/'candidate.sha',archive,root/'original.sha')
            self.assertNotEqual(result.returncode,0)
            self.assertEqual((current/'0').read_bytes(),b'old')
            self.assertFalse((base/'.gts9-test332-stage').exists())

if __name__=='__main__':unittest.main()

class FixedEvidence(unittest.TestCase):
    def setUp(self):
        self.endpoint={'boot':BOOT,'uptime':120.0,'pump':1,'config_data_written':False,'battery':{'POWER_SUPPLY_CURRENT_NOW':'1200000','POWER_SUPPLY_HEALTH':'Good','POWER_SUPPLY_TEMP':'323'},'usb':{'POWER_SUPPLY_ONLINE':'1','POWER_SUPPLY_USB_TYPE':'Unknown [PD]','POWER_SUPPLY_INPUT_CURRENT_LIMIT':'1500000'},'tcpm':{'POWER_SUPPLY_ONLINE':'1','POWER_SUPPLY_VOLTAGE_NOW':'9000000','POWER_SUPPLY_CURRENT_MAX':'1500000'}}
        self.messages=['sm5440-fedora 0-0063: fixed return verified: source=2 lease=7 vbus=9272000uV samples=3 range=9272..9283mV settled=100ms raw_ibus=0 pump_off=1','sm5440-fedora 0-0063: fixed return check complete: lease=0 PPS=0 pump_ON=0']
    def raw(self,duplicate=False,missing=False,short=False):
        journal='\n'.join(json.dumps({'_BOOT_ID':BOOT,'__MONOTONIC_TIMESTAMP':str(90000000+i),'MESSAGE':m}) for i,m in enumerate(self.messages))
        records=[dict(kind='sample',**self.endpoint),dict(kind='verdict',verdict='PASS',boot=BOOT,observation_seconds=29 if short else 30.5,endpoint=self.endpoint),dict(kind='complete-journal',returncode=0,data='' if missing else journal)]
        if duplicate:records.append(records[-1])
        return '\n'.join(map(json.dumps,records))
    def test_prefixed_native_proof_and_complete_full_journal_pass(self):
        d=G.fixed_result(self.raw(),BOOT);self.assertEqual(d['proof']['vbus_uv'],9272000);self.assertFalse(d['PPS']);self.assertFalse(d['pump_ON'])
    def test_missing_duplicate_or_empty_journal_stops(self):
        for kwargs in [{'missing':True},{'duplicate':True},{'short':True}]:
            with self.assertRaises(ValueError):G.fixed_result(self.raw(**kwargs),BOOT)
    def test_duplicate_or_out_of_window_or_unstable_proof_stops(self):
        original=self.messages[:]
        for value in [original[0].replace('9272000','9450001'),original[0].replace('9283mV','9390mV'),original[0].replace('samples=3','samples=2'),original[0].replace('settled=100','settled=99')]:
            self.messages=[value,original[1]]
            with self.assertRaises(ValueError):G.fixed_result(self.raw(),BOOT)
        self.messages=original+[original[0]]
        with self.assertRaises(ValueError):G.fixed_result(self.raw(),BOOT)
    def test_hardware_failure_cannot_be_overridden_by_pass_record(self):
        self.messages.append('sm5440-fedora 0-0063: fixed return check failed: -110; lease=7')
        with self.assertRaises(ValueError):G.fixed_result(self.raw(),BOOT)
    def test_endpoint_on_or_no_switching_charge_stops(self):
        for field,value in [('pump',5),('boot','b'*32)]:
            original=self.endpoint[field];self.endpoint[field]=value
            with self.assertRaises(ValueError):G.fixed_result(self.raw(),BOOT)
            self.endpoint[field]=original
        self.endpoint['battery']['POWER_SUPPLY_CURRENT_NOW']='-1'
        with self.assertRaises(ValueError):G.fixed_result(self.raw(),BOOT)
    def test_actual_pps_endpoint_is_not_fixed_return(self):
        self.endpoint['tcpm']['POWER_SUPPLY_ONLINE']='2'
        with self.assertRaises(ValueError):G.fixed_result(self.raw(),BOOT)
