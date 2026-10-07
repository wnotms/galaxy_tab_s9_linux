"""Synthetic transaction journals and measured335 pack fixtures; no device I/O."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import gzip
import io
import types
import hashlib
import os
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from pps_off_evidence import native_proof, RoundWindow, validate_native_sample

R = ROOT/'reference/boot-tests/test-336-pps-off-roundtrip'
PLAN = json.loads((R/'registration.json').read_text())
BASE = json.loads((R.parent/'test-335-fixed9-switching-observation/device-completion-charge/summary.json').read_text())['endpoint']
PLAN['boot_id'] = BASE['boot']
BOOT = BASE['boot']


def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def journal():
    messages = [
        (0, 'Linux version 7.2.0-rc3'),
        (10000000, 'sm5440: PPS OFF negotiated: source=9 lease=1 target=8720mV/1800mA pump_ON=0'),
        (10200000, 'sm5440: PPS OFF sampled: target=8720mV/1800mA observed=9100mV range=9070..9100mV samples=3 settled=121ms raw_ibus=0 pump_ON=0'),
        (10800000, 'sm5440: fixed return verified: source=9 lease=1 vbus=9427000uV samples=3 range=9427..9427mV settled=121ms raw_ibus=0 pump_off=1'),
        (10800100, 'sm5440: PPS OFF return complete: target=8720mV/1800mA lease=0 fixed_return=1 pump_ON=0'),
    ]
    return [dict(_BOOT_ID=BOOT,__MONOTONIC_TIMESTAMP=str(t),__CURSOR='synthetic-'+str(t),MESSAGE=m,PRIORITY='6') for t,m in messages]


def packet(t, pps=False, healthy=True):
    d=copy.deepcopy(BASE)
    d.update(monotonic=t,uptime=20+t,pps_check='Y',fixed_check='N',pump=1)
    if not healthy:d['battery']['POWER_SUPPLY_CURRENT_NOW']='-473000'
    if pps:
        d['tcpm'].update(POWER_SUPPLY_ONLINE='2',POWER_SUPPLY_USB_TYPE='PD [PD_PPS]',
                         POWER_SUPPLY_VOLTAGE_NOW='8720000',POWER_SUPPLY_VOLTAGE_MIN='3300000',
                         POWER_SUPPLY_VOLTAGE_MAX='11000000',POWER_SUPPLY_CURRENT_MAX='5000000',
                         POWER_SUPPLY_CURRENT_NOW='1800000')
    return d


class NativeTests(unittest.TestCase):
    def test_complete_actual_limits_without_independent_calibration_claim(self):
        proof=native_proof(journal(),BOOT,True)
        self.assertEqual(proof['pps_observed_mv'],9100)
        self.assertTrue(proof['lease_released'])
        self.assertFalse(proof['pump_ON'])

    def test_prefix_pending_but_not_a_pass(self):
        for n in range(1,5):
            self.assertIsNone(native_proof(journal()[:n],BOOT))
            with self.assertRaises(ValueError):native_proof(journal()[:n],BOOT,True)

    def test_missing_empty_mixed_and_late_journal(self):
        for rows in [[],[dict(journal()[0],_BOOT_ID='0'*32)],journal()[1:]]:
            with self.assertRaises(ValueError):native_proof(rows,BOOT)

    def test_duplicate_order_and_timestamp(self):
        variants=[journal()+[journal()[-1]], [journal()[0],journal()[2],journal()[1]],
                  journal()[:2]+[dict(journal()[2],__MONOTONIC_TIMESTAMP='9000000')]]
        for rows in variants:
            with self.assertRaises(ValueError):native_proof(rows,BOOT)

    def test_failure_always_wins_even_after_complete(self):
        for message in ['PPS OFF return failed: step=PPS primary=-11 cleanup=-110 lease=1',
                        'PPS OFF check stopped: -110; lease=1','fixed fallback failed: -110',
                        'BUG: pump fault', 'Kernel panic', 'soft lockup',
                        'rcu: INFO: detected stalls', 'CSD non-responsive', 'pump_ON=1']:
            with self.assertRaises(ValueError):native_proof(journal()+[dict(journal()[0],MESSAGE=message)],BOOT)

    def test_wrong_target_current_source_lease_and_physical_bounds(self):
        changes=[(1,'8720mV','11000mV'),(1,'1800mA','2000mA'),(1,'source=9','source=0'),
                 (2,'raw_ibus=0','raw_ibus=1'),(2,'9070..9100','8900..9100'),
                 (2,'observed=9100','observed=9400'),(2,'settled=121','settled=99'),
                 (3,'lease=1','lease=2'),(3,'vbus=9427000','vbus=9500000'),
                 (4,'lease=0','lease=1'),(4,'8720mV','8740mV')]
        for row,old,new in changes:
            rows=journal();rows[row]['MESSAGE']=rows[row]['MESSAGE'].replace(old,new)
            with self.subTest(new=new),self.assertRaises(ValueError):native_proof(rows,BOOT,True)

    def test_source_apdo_ceiling_is_not_negotiated_current(self):
        validate_native_sample(packet(0,True),PLAN)
        d=packet(0,True);d['tcpm']['POWER_SUPPLY_CURRENT_NOW']='2000000'
        with self.assertRaises(ValueError):validate_native_sample(d,PLAN)

    def test_pps_bounds_roles_flags_pack_and_pump(self):
        for group,key,value in [('tcpm','POWER_SUPPLY_VOLTAGE_NOW','12000000'),
                                ('tcpm','POWER_SUPPLY_VOLTAGE_NOW','8730000'),
                                ('tcpm','POWER_SUPPLY_ONLINE','0'),
                                ('battery','POWER_SUPPLY_TEMP','380'),
                                ('battery','POWER_SUPPLY_CAPACITY','80'),
                                ('pack','mode','disabled')]:
            d=packet(0,True);d[group][key]=value
            with self.assertRaises(ValueError):validate_native_sample(d,PLAN)
        for key,value in [('direct','Y'),('fixed_check','Y'),('pps_check','N'),('pump',4),
                          ('boot_end','0'*32),('roles',['[source]','[host]'])]:
            d=packet(0,True);d[key]=value
            with self.assertRaises(ValueError):validate_native_sample(d,PLAN)


class WindowTests(unittest.TestCase):
    def test_pps_then_bounded_settling_then_full_30_seconds(self):
        w=RoundWindow(PLAN,0)
        self.assertEqual(w.advance(packet(0,True),journal()[:2])['state'],'WAIT_NATIVE')
        self.assertEqual(w.advance(packet(1,healthy=False),journal())['state'],'SETTLING')
        for t in range(2,33):
            result=w.advance(packet(t),journal())
            self.assertEqual(result['complete'],t==32)

    def test_first_failure_never_retries(self):
        w=RoundWindow(PLAN,0);bad=packet(0);bad['pump']=4
        with self.assertRaises(ValueError):w.advance(bad,journal())
        with self.assertRaises(ValueError):w.advance(packet(1),journal())

    def test_post_return_pps_is_failure(self):
        with self.assertRaises(ValueError):RoundWindow(PLAN,0).advance(packet(0,True),journal())

    def test_detach_and_response_gap_stop(self):
        for gap in (1,4):
            w=RoundWindow(PLAN,0);w.advance(packet(0,True),journal()[:2]);d=packet(gap,True)
            if gap==1:d['tcpm']['POWER_SUPPLY_ONLINE']='0'
            with self.assertRaises(ValueError):w.advance(d,journal()[:2])

    def test_native_deadline(self):
        d=packet(0,True);d['uptime']=331
        with self.assertRaises(TimeoutError):RoundWindow(PLAN,0).advance(d,journal()[:2])


class RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h=load('pps336_host',R/'host_flow.py')
        cls.h.configure()

    def test_import_does_not_authorize_or_contact_device(self):
        # Historical physical authorization now exists; isolate the initial
        # registration rather than assuming the archive is forever unexecuted.
        with tempfile.TemporaryDirectory() as tmp, patch.object(self.h, 'R', Path(tmp)):
            self.assertFalse(self.h.authorized())
        self.assertFalse(PLAN['execution_authorized'])

    def test_install_not_authorized_rejects_before_adb(self):
        with patch.object(self.h,'verify_inputs'),patch.object(self.h.base,'verify_stage'),patch.object(self.h,'authorized',return_value=False),patch.object(self.h.p,'Recorder') as recorder:
            with self.assertRaises(ValueError):self.h.install()
            recorder.assert_not_called()

    def test_no_default_pps_pump_activation_and_exact331_rollback(self):
        self.assertTrue(PLAN['owner_charger_before_System_boot'])
        self.assertEqual(PLAN['cmdline_flag'],'sm5440_fedora.pps_return_check=1')
        self.assertFalse(PLAN['pump_ON'])
        self.assertEqual(self.h.PACKAGE['baseline_partitions']['boot'],'025ebea4282524751bace461ce96beef85c01ea65a4d2b117106c7cdfe0ab815')

    def test_baseline_always_rejects_direct_flag(self):
        sec=self.h.h.g.baseline.sections((R.parent/'test-334-fixed-return-soc-margin/final-acceptance/current-state.txt').read_text())
        sec['direct-default']='Y'
        with self.assertRaises(ValueError):self.h.gate.identity(sec,PLAN,'baseline')

    def test_restore_soc_relaxation_never_relaxes_entry(self):
        sec=self.h.h.g.baseline.sections((R.parent/'test-334-fixed-return-soc-margin/final-acceptance/current-state.txt').read_text())
        sec['battery']=sec['battery'].replace('POWER_SUPPLY_CAPACITY=68','POWER_SUPPLY_CAPACITY=85')
        # Fixture exact SOC is checked before modifying to avoid a vacuous case.
        sec['battery']='\n'.join('POWER_SUPPLY_CAPACITY=85' if s.startswith('POWER_SUPPLY_CAPACITY=') else s for s in sec['battery'].splitlines())
        with self.assertRaises(ValueError):self.h.gate.identity(sec,PLAN,'baseline')
        self.h.gate.identity(sec,PLAN,'baseline',restoration=True)

    def test_observer_transport_failure_never_passes(self):
        with self.assertRaises(ValueError):self.h.accepted('',255,'charge',PLAN)


class ObserverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.observer=load('pps336_observer',R/'observe.py')
        cls.host=load('pps336_review',R/'host_flow.py')

    def collect(self, fault=None):
        o=self.observer
        records=[]
        packets=[packet(0,healthy=False),packet(1,healthy=False)]+[packet(t) for t in range(2,35)]
        if fault:
            packets[3][fault[0]]=fault[1]
        fake=types.SimpleNamespace(stdout=io.StringIO(''),poll=lambda:None,
                                   terminate=lambda:None,wait=lambda **kw:0)
        config=(ROOT/'out/kernel-x710-fedora-pps-off-return/config').read_bytes()
        notes=(ROOT/'out/kernel-x710-fedora-pps-off-return/kernel-notes.bin').read_bytes()
        def read_bytes(path):
            if str(path)=='/proc/config.gz':return gzip.compress(config)
            if str(path)=='/sys/kernel/notes':return notes
            raise AssertionError('unmocked file: '+str(path))
        def text(path):
            if path=='/etc/machine-id':return PLAN['machine_id']
            if path=='/proc/cmdline':return PLAN['cmdline_flag']+' '+PLAN['runtime_cmdline']
            raise AssertionError('unmocked text: '+str(path))
        raw=''.join(json.dumps(x)+'\n' for x in journal())
        def command(argv):
            if argv[0]=='journalctl':return raw
            if argv[0]=='ip':return 'usb0    inet 169.254.42.1/16'
            if argv[:2]==['systemctl','is-active']:return 'active'
            if argv[:2]==['systemctl','--failed']:return ''
            raise AssertionError('unmocked command')
        with patch.object(o.Path,'read_bytes',read_bytes),patch.object(o.Path,'exists',return_value=False),patch.object(o,'text',side_effect=text),patch.object(o,'command',side_effect=command),patch.object(o,'sample',side_effect=packets),patch.object(o,'emit',side_effect=lambda kind,**kw:records.append(dict(kind=kind,**kw))),patch.object(o.subprocess,'Popen',return_value=fake),patch.object(o.subprocess,'run',return_value=types.SimpleNamespace(returncode=1)),patch.object(o.time,'sleep'):
            rc=o.main(PLAN,'charge')
        return rc,records

    def test_real_observer_with_mocks_and_host_parser_complete_30s(self):
        rc,records=self.collect()
        self.assertEqual(rc,0)
        accepted=self.host.accepted('\n'.join(map(json.dumps,records)),rc,'charge',PLAN)
        self.assertEqual(accepted['observation_seconds'],30)
        self.assertFalse(accepted['pump_ON'])

    def test_real_observer_stops_first_pump_fault_and_does_not_resume(self):
        rc,records=self.collect(('pump',4))
        self.assertEqual(rc,1)
        self.assertEqual([x['verdict'] for x in records if x['kind']=='verdict'],['STOP'])
        self.assertEqual(len([x for x in records if x['kind']=='sample']),3)

    def test_host_rejects_fabricated_duration_duplicate_verdict_and_missing_journal(self):
        rc,records=self.collect()
        variants=[]
        d=copy.deepcopy(records)
        next(x for x in d if x['kind']=='verdict')['observation_seconds']=31
        variants.append(d)
        variants.append(records+[records[-1]])
        variants.append([x for x in records if x['kind']!='journal-after'])
        for d in variants:
            with self.assertRaises(ValueError):self.host.accepted('\n'.join(map(json.dumps,d)),rc,'charge',PLAN)


class ModuleTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.work=Path(self.temp.name);self.root=self.work/'root';self.release='7.2.0-rc3-gts9wifi-dirty'
        (self.root/'etc').mkdir(parents=True)
        (self.root/'etc/machine-id').write_text(PLAN['machine_id'])
        self.base=self.root/'usr/lib/modules';self.current=self.base/self.release;self.current.mkdir(parents=True)
        self.old=self.work/'old.sha256';self.new=self.work/'new.sha256'
        old=[];new=[];self.archive=self.work/'new.tar.gz'
        with tarfile.open(self.archive,'w:gz') as tar:
            for n in range(181):
                name=f'{n}.ko';before=b'old'+str(n).encode();after=b'new'+str(n).encode()
                (self.current/name).write_bytes(before)
                old.append(hashlib.sha256(before).hexdigest()+'  '+name+'\n')
                new.append(hashlib.sha256(after).hexdigest()+'  '+name+'\n')
                info=tarfile.TarInfo(self.release+'/'+name);info.size=len(after);tar.addfile(info,io.BytesIO(after))
        self.old.write_text(''.join(old));self.new.write_text(''.join(new))
        bindir=self.work/'bin';bindir.mkdir();sync=bindir/'sync';sync.write_text('#!/bin/sh\nexit 0\n');sync.chmod(0o755)
        self.env=dict(os.environ,PATH=str(bindir)+os.pathsep+os.environ['PATH'])

    def call(self,mode,manifest):
        return subprocess.run(['sh',str(R/'module-swap.sh'),str(self.root),mode,str(manifest),str(self.archive),str(self.old)],env=self.env,capture_output=True,timeout=10)

    def test_actual336_transaction_restores_original_without_touching_other_slots(self):
        other=self.base/'.gts9-test331-original';other.mkdir();(other/'sentinel').write_text('keep')
        result=self.call('install',self.new);self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual((self.current/'0.ko').read_bytes(),b'new0')
        self.assertTrue((self.base/'.gts9-test336-original').exists())
        result=self.call('restore',self.old);self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual((self.current/'0.ko').read_bytes(),b'old0')
        self.assertEqual((other/'sentinel').read_text(),'keep')

    def test_first_manifest_failure_keeps_original_before_rename(self):
        self.new.write_text(self.new.read_text().replace(self.new.read_text()[:64],'0'*64,1))
        self.assertNotEqual(self.call('install',self.new).returncode,0)
        self.assertEqual((self.current/'0.ko').read_bytes(),b'old0')
        self.assertFalse((self.base/'.gts9-test336-original').exists())


if __name__=='__main__':unittest.main()
