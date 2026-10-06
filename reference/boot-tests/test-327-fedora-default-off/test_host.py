#!/usr/bin/env python3
import copy,importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
R=Path(__file__).resolve().parent

def load(name,p):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
G=load('test327_gate',R/'gate.py');H=load('test327_flow',R/'host_flow.py');P=json.loads((R/'registration.json').read_text())
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
if __name__=='__main__':unittest.main()
