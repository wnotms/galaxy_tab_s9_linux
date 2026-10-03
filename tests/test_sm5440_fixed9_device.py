"""Fixed9 diagnostic provenance and real runner lifecycle; mocked transports only."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import test_sm5440_module_staging as staging

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reference/boot-tests/test-317-fixed9-off-context-device'
spec=importlib.util.spec_from_file_location('fixed317_test_runner',R/'host_flow.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.configure()
g=m.gate
BOOT='1234567890abcdef1234567890abcdef'

def raw(d):return ''.join(k+'='+str(v)+'\n' for k,v in d.items())

def fixture(latch=False):
    s=dict(format='sm5440-passive-v1',registers_are_cached=1,independently_calibrated=0,
        pump_enable_supported=0,condition_test=1,condition_attempted=1,context_phase=10,
        context_error=0,context_cleanup_error=0,enhiz_restore_pending=0,last_sample_error=0,
        sample_valid=1,fault=0,stopped=0,startup_pending=0,context_settings_pending=0,
        context_lease_retained=1,context_controls_state=2,context_controls_attempted=7,
        context_controls_off_verified=1,context_controls_operation_error=0,
        context_controls_restore_error=0,context_controls_witness_valid=1,
        context_instance=1,context_source_generation=2,context_budget_generation=3,
        context_lease=4,context_budget_ma=1500,context_capacity=30,context_pack_uv=3800000,
        context_pack_decic=310,context_started_ms=1000,context_completed_ms=2900,
        context_pack_started_ms=2800,context_pack_completed_ms=2810,context_readiness_checks=1,
        context_controls_before='00 00 00',context_controls_witness='00 '*9+'00',
        context_controls_status_before='00 00 20 00',context_controls_status_after='00 00 20 00',
        context_inactive_revblk=int(latch))
    samples=[('context_initial',1,1100),('context_before',1,1100),
             ('context_handoff',2,1500),('condition',3,1900)]
    if latch:
        samples=[('context_initial',1,1100),('context_confirmation',2,1300),
                 ('context_before',3,1500),('context_handoff',4,1900),('condition',5,2300)]
    for label,seq,start in samples:
        fields=dict(valid=0 if label=='condition' else 1,mode_before=1,mode_after=1,
            online=1,vbus_uv=9000000,ibus_ua=0,vbat_uv=3800000,die_decic=300,
            int4_wait=1,restore_error=0,status='00 00 20 00',faults=128 if label=='context_initial' and latch else 0,
            int='00 00 02 01' if label=='context_initial' and latch else '00 00 00 01',
            acquired_ms=start,adc_read_completed_ms=start+100,completed_ms=start+120,
            acquisition_seq=seq,cntl2=1,vbuscntl=2,vbatcntl=3,prtncntl=4)
        s.update({label+'_'+k:v for k,v in fields.items()})
    s.update(condition_pre_status_valid=1,condition_pre_status='00 00 20 00',
        condition_cntl6_before_valid=1,condition_cntl6_during_valid=1,condition_cntl6_restored_valid=1,
        condition_cntl6_before=137,condition_cntl6_during=9,condition_cntl6_restored=137,
        condition_gauge_attempted=1,condition_condition_error=0,condition_gauge_ret=0,
        condition_gauge_uv=3802500,condition_gauge_started_ms=s['condition_adc_read_completed_ms'],
        condition_gauge_completed_ms=s['condition_completed_ms'])
    p=dict(format='sm5714-current-port-v1',ret=0,online=1,usb_type=8,
        charge_requested=1,budget_mv=9000,budget_ma=1500,voltage_uv=9000000,current_ua=1500000,
        instance=1,source_generation=2,budget_generation=3,started_ms=3000,completed_ms=3001)
    msg=('sm5440-passive 0-0063: startup voltage pair seq={condition_acquisition_seq} '
         'ADC-start={condition_acquired_ms}ms ADC-read={condition_adc_read_completed_ms}ms '
         'VBAT={condition_vbat_uv}uV gauge-start={condition_gauge_started_ms}ms '
         'gauge-end={condition_gauge_completed_ms}ms gauge-ret=0 gauge={condition_gauge_uv}uV').format(**s)
    kernel=json.dumps(dict(_BOOT_ID=BOOT,MESSAGE=msg))+'\n'
    return s,p,kernel

def identity():
    s,p,k=fixture()
    sec=dict(boot=BOOT,**{'boot-end':BOOT},uname='Linux gts9 7.2.0-rc3-gts9wifi-dirty',
        cmdline=m.PLAN['runtime_cmdline'],uptime='40.1 70.0',
        identity=m.PLAN['candidate_config_sha256']+'  -\n'+m.PLAN['candidate_notes_sha256']+'  /sys/kernel/notes',
        battery='POWER_SUPPLY_HEALTH=Good\nPOWER_SUPPLY_PRESENT=1\nPOWER_SUPPLY_CAPACITY=30\n'
                'POWER_SUPPLY_VOLTAGE_NOW=3800000\nPOWER_SUPPLY_TEMP=310\nPOWER_SUPPLY_VOLTAGE_MAX_DESIGN=4440000',
        services='active\nactive\nactive',roles='[sink]\n[device]',dcc='absent',failed='',
        network='14: usb0    inet 169.254.42.1/16',snapshot=raw(s),source=raw(p),
        tcpm='POWER_SUPPLY_ONLINE=1\nPOWER_SUPPLY_VOLTAGE_NOW=9000000\nPOWER_SUPPLY_CURRENT_NOW=1500000',
        **{'pack-thermal':'sm5714-battery\nenabled\n31000'})
    return ''.join('@@'+name+'\n'+value+'\n' for name,value in sec.items()),k

class EvidenceTests(unittest.TestCase):
    def check(self,s,p,k):return g.context(raw(s),k,BOOT,raw(p))

    def test_fixed_capability_is_not_actual_pps_and_no_charge_grant(self):
        s,p,k=fixture()
        for label in (6,8,9,10):
            p['usb_type']=label;verdict=self.check(s,p,k)
            self.assertEqual(verdict['conversion_seq'],3)
            self.assertFalse(verdict['charging_authorized']);self.assertFalse(verdict['physical_freshness_grant'])
        for label in (0,7):
            p['usb_type']=label
            with self.assertRaises(ValueError):self.check(s,p,k)
        p['usb_type']=8;p['online']=2
        with self.assertRaises(ValueError):self.check(s,p,k)

    def test_initial_inactive_latch_needs_two_new_healthy_conversions(self):
        s,p,k=fixture(True);self.assertTrue(self.check(s,p,k)['inactive_initial_revblk_retained'])
        for key,value in [('context_confirmation_acquisition_seq',1),('context_before_faults',128),
                          ('context_confirmation_cntl2',99),('context_initial_status','00 00 22 00')]:
            copy=dict(s,**{key:value})
            with self.subTest(key=key),self.assertRaises(ValueError):self.check(copy,p,k)

    def test_raw_condition_is_not_published_valid_flag(self):
        s,p,k=fixture();self.check(s,p,k)
        for key,value in [('condition_valid',1),('sample_valid',0)]:
            with self.assertRaises(ValueError):self.check(dict(s,**{key:value}),p,k)

    def test_hardware_fault_and_uncertain_cleanup_refused(self):
        s,p,k=fixture()
        for key,value in [('condition_status','00 00 22 00'),('condition_faults',128),
            ('condition_ibus_ua',30000),('condition_vbus_uv',9500001),('condition_mode_after',5),
            ('condition_pre_status_valid',0),('condition_pre_status','00 00 60 00'),
            ('condition_cntl6_restored',9),('enhiz_restore_pending',1),('condition_restore_error',-5),
            ('context_cleanup_error',-5),('context_settings_pending',1),('context_lease_retained',0),
            ('context_controls_witness_valid',0),('context_controls_off_verified',0),('context_error',-5)]:
            with self.subTest(key=key),self.assertRaises(ValueError):self.check(dict(s,**{key:value}),p,k)

    def test_source_epoch_and_timing_not_restamped(self):
        s,p,k=fixture()
        for key,value in [('instance',2),('source_generation',3),('budget_generation',4),
                          ('started_ms',2800),('completed_ms',3501),('current_ua',1800000)]:
            with self.subTest(key=key),self.assertRaises(ValueError):self.check(s,dict(p,**{key:value}),k)
        for key,value in [('condition_completed_ms',2600),('condition_gauge_started_ms',1800),
                          ('context_pack_completed_ms',3400),('context_readiness_checks',41)]:
            with self.subTest(key=key),self.assertRaises(ValueError):self.check(dict(s,**{key:value}),p,k)

    def test_journal_missing_empty_mixed_duplicate_or_changed_pair_refused(self):
        s,p,k=fixture()
        for data in ('','{}\n',k+k,k.replace(BOOT,'2'*32),k.replace('3802500uV','3902500uV')):
            with self.subTest(data=data),self.assertRaises((ValueError,KeyError)):self.check(s,p,data)

    def test_pack_and_comparison_bounds(self):
        s,p,k=fixture()
        for key,value in [('context_capacity',80),('context_pack_decic',380),('context_pack_uv',4300000),
                          ('condition_gauge_ret',-5),('condition_gauge_uv',3900001)]:
            with self.subTest(key=key),self.assertRaises(ValueError):self.check(dict(s,**{key:value}),p,k)

    def test_actual_switching_handoff_readback(self):
        d=dict(boot_id_before=BOOT,boot_id_after=BOOT,register_data_writes=False,
            only_atomic_pointer_reads=True,bound_driver='sm5714-battery',
            stable_registers={'0x0d':'1','0x0e':'0','0x13':'0','0x14':'5','0x15':'0','0x18':'134','0x1a':'45'})
        self.assertFalse(g.handoff_controls(json.dumps(d),BOOT)['ordinary_reenabled'])
        for reg,val in [('0x13','8'),('0x15','16'),('0x1a','44'),('0x0e','128'),('0x18','135')]:
            copy=dict(d,stable_registers=dict(d['stable_registers'],**{reg:val}))
            with self.assertRaises(ValueError):g.handoff_controls(json.dumps(copy),BOOT)

class IdentityTests(unittest.TestCase):
    def setUp(self):m.configure()
    def test_candidate_requires_same_packet_boot_config_real_thermal_and_fixed_mode(self):
        text,_=identity();self.assertEqual(m.candidate_identity(text)[1],BOOT)
        for old,new in [('@@boot-end\n'+BOOT,'@@boot-end\n'+'2'*32),
                        (m.PLAN['candidate_config_sha256'],'0'*64),('[device]','[host]'),
                        ('@@dcc\nabsent','@@dcc\npresent'),('enabled\n31000','disabled\n31000'),
                        ('POWER_SUPPLY_ONLINE=1','POWER_SUPPLY_ONLINE=2'),
                        ('POWER_SUPPLY_VOLTAGE_NOW=9000000','POWER_SUPPLY_VOLTAGE_NOW=5000000')]:
            with self.subTest(new=new),self.assertRaises(ValueError):m.candidate_identity(text.replace(old,new))

class LifecycleTests(unittest.TestCase):
    def setUp(self):
        m.configure();temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.r=Path(temp.name)
        for name,value in [('R',self.r),('verify_inputs',mock.Mock())]:
            ctx=mock.patch.object(m,name,value);ctx.start();self.addCleanup(ctx.stop)
        rec=mock.Mock(folder=self.r);self.rec=rec
        ctx=mock.patch.object(m.p,'Recorder',return_value=rec);ctx.start();self.addCleanup(ctx.stop)
        ctx=mock.patch.object(m.time,'sleep');self.sleep=ctx.start();self.addCleanup(ctx.stop)

    def preflight(self,age=0):
        (self.r/'preflight').mkdir(exist_ok=True)
        m.write(self.r/'preflight/summary.json',dict(verdict='READY_FOR_REGISTERED_ONE_BOOT',authenticated_wifi=True,
            collected_at_epoch=m.time.time()-age,boot_id=BOOT,wifi='10.1.1.1'))

    def test_install_stops_in_twrp_without_candidate_reboot(self):
        self.preflight();self.rec.adb.return_value=('',0)
        with mock.patch.object(m.base,'identity'),mock.patch.object(m.h,'enter_recovery'),\
            mock.patch.object(m.base,'transfer'),mock.patch.object(m.h,'require_partitions'),\
            mock.patch.object(m.h,'verify_modules'),mock.patch.object(m.h,'write_boot') as boot,\
            mock.patch.object(m.h,'clear_unmount') as clear:
            result=m.install()
        self.assertTrue(result['rollback_required']);self.assertIn('awaiting-owner',result['phase'])
        boot.assert_called_once();clear.assert_called_once();self.rec.host_adb.assert_not_called()
        with self.assertRaises(ValueError):m.install()

    def test_stale_preflight_and_missing_wifi_refuse_before_device(self):
        self.preflight(301)
        with self.assertRaises(ValueError):m.install()
        self.rec.adb.assert_not_called()
        self.preflight();pre=m.read(self.r/'preflight/summary.json');pre['authenticated_wifi']=False
        m.write(self.r/'preflight/summary.json',pre)
        with self.assertRaises(ValueError):m.install()
        self.rec.adb.assert_not_called()

    def test_first_fault_stops_without_endpoint_or_new_conversion(self):
        m.write(self.r/'mutation-state.json',dict(rollback_required=True,phase='candidate-installed-awaiting-owner-fixed9-boot'))
        self.preflight();text,k=identity();text=text.replace('POWER_SUPPLY_TEMP=310','POWER_SUPPLY_TEMP=450')
        with mock.patch.object(m,'ssh_command',return_value=(text,0)) as ssh:
            with self.assertRaises(ValueError):m.capture()
        self.assertEqual([c.args[1] for c in ssh.call_args_list],['readiness-00','first-failure-kernel'])
        self.sleep.assert_not_called();self.assertTrue(m.read(self.r/'mutation-state.json')['rollback_required'])
        self.assertTrue(m.read(self.r/'first-failure.json')['stopped'])

    def test_one_capture_two_same_boot_boundaries_and_no_retry(self):
        self.preflight();(self.r/'preflight/boots-before.txt').write_text('0 '+'2'*32+' boot\n')
        m.write(self.r/'mutation-state.json',dict(rollback_required=True,phase='candidate-installed-awaiting-owner-fixed9-boot'))
        text,k=identity();calls=[]
        def ssh(rec,name,command,**kw):
            calls.append(name)
            return ({'kernel-json':k,'boots-after':'-1 '+'2'*32+' boot\n0 '+BOOT+' boot\n','handoff-controls':'{}'}.get(name,text),0)
        pre=m.read(self.r/'preflight/summary.json');pre['boot_id']='2'*32;m.write(self.r/'preflight/summary.json',pre)
        with mock.patch.object(m,'ssh_command',side_effect=ssh),mock.patch.object(m.base.old,'scan_journal',return_value={}),\
            mock.patch.object(g,'handoff_controls',return_value={}):
            result=m.capture()
        self.assertFalse(result['pump_ON']);self.assertEqual(calls.count('kernel-json'),2)
        self.sleep.assert_called_once_with(15);self.assertIn('unconditional-restore',m.read(self.r/'mutation-state.json')['phase'])
        with self.assertRaises(ValueError):m.capture()

    def test_restore_verifies_allfive_original181_and_once_normal_reboot(self):
        m.write(self.r/'mutation-state.json',dict(rollback_required=True,candidate_boot_id=BOOT))
        def adb(name,command,**kwargs):
            if name=='target-boot-id':return BOOT,0
            if name=='module-layout':return 'saved',0
            return '',0
        self.rec.adb.side_effect=adb
        with mock.patch.object(m.h,'enter_recovery'),mock.patch.object(m.base,'transfer'),\
            mock.patch.object(m.base,'restoration_layout',return_value=m.PACKAGE['candidate_partitions']['boot']),\
            mock.patch.object(m.h,'verify_modules') as mods,mock.patch.object(m.h,'write_boot') as boot,\
            mock.patch.object(m.h,'require_partitions') as parts,mock.patch.object(m.h,'clear_unmount'),\
            mock.patch.object(m.base,'admission',return_value=({'boot_id':'3'*32},'')):
            m.restore()
        mods.assert_called_once();boot.assert_called_once();parts.assert_called_once_with('',m.PACKAGE['baseline_partitions'])
        self.rec.host_adb.assert_called_once();self.assertFalse(m.read(self.r/'mutation-state.json')['rollback_required'])
        self.assertEqual(len([c for c in self.rec.adb.call_args_list if c.args[0]=='restore-modules']),1)
        with self.assertRaises(ValueError):m.restore()

    def test_unrecognized_manual_recovery_refuses_before_transfer(self):
        m.write(self.r/'mutation-state.json',dict(rollback_required=True));self.rec.adb.return_value=('other-board uid=0',0)
        with mock.patch.object(m.base,'transfer') as transfer,self.assertRaises(ValueError):m.restore(True)
        transfer.assert_not_called();self.rec.host_adb.assert_not_called()

    def test_ssh_uses_authenticated_fixed_address_strict_host_key(self):
        self.preflight();self.rec.command.return_value=('',0)
        m.ssh_command(self.rec,'identity','true')
        args=self.rec.command.call_args.args[1]
        self.assertIn('StrictHostKeyChecking=yes',args);self.assertIn('HostKeyAlias=gts9-test317',args)
        self.assertIn('root@10.1.1.1',args)

class SealingTests(unittest.TestCase):
    def test_input_drift_and_unpushed_registration_stop(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);ref=root/'registration';ref.mkdir();(root/'input').write_bytes(b'valid')
            (ref/'INPUTS.json').write_text(json.dumps({'input':hashlib.sha256(b'valid').hexdigest()}))
            with mock.patch.object(m,'ROOT',root),mock.patch.object(m,'R',ref),mock.patch.object(m.base,'verify_stage'):
                m.verify_inputs()
                with mock.patch.object(m.subprocess,'check_output',side_effect=['test','new','old']),self.assertRaises(ValueError):m.verify_inputs(True)
                (root/'input').write_bytes(b'drift')
                with self.assertRaises(ValueError):m.verify_inputs()

class ModuleTransactionTests(staging.ModuleStagingTests):
    def setUp(self):
        ctx=mock.patch.object(staging,'HELPER',R/'module-swap.sh');ctx.start();self.addCleanup(ctx.stop)
        super().setUp()

    def test_actual_release_root_candidate_installs_and_restores(self):
        # Exercise the actual renamed helper using exact-181 synthetic files.
        import io
        import tarfile
        archive=self.work/'candidate.tar.gz';expected={}
        with tarfile.open(archive,'w:gz') as tf:
            for n in range(181):
                name=f'new-{n:03}.ko';data=('candidate '+name).encode()
                expected[name]=hashlib.sha256(data).hexdigest()
                item=tarfile.TarInfo(staging.RELEASE+'/'+name);item.size=len(data)
                tf.addfile(item,io.BytesIO(data))
        new=self.manifest('new.sha256',expected)
        result=self.call('install',new,archive);self.assertEqual(result.returncode,0,result.stderr.decode())
        self.assertEqual(self.current_hashes(),expected)
        self.assertEqual(self.current_hashes(self.base/'.gts9-test317-original'),self.old)
        result=self.call('restore',self.old_manifest);self.assertEqual(result.returncode,0,result.stderr.decode())
        self.assertEqual(self.current_hashes(),self.old)
        self.assertEqual(self.current_hashes(self.base/'.gts9-test317-tested'),expected)

    def test_existing_backup_is_preserved(self):
        saved=self.base/'.gts9-test317-original';saved.mkdir();(saved/'retained').write_text('keep')
        result=self.call('install',self.old_manifest,self.archive(staging.RELEASE+'/new.ko'))
        self.assertNotEqual(result.returncode,0);self.assertEqual((saved/'retained').read_text(),'keep')
        self.assertEqual(self.current_hashes(),self.old)

if __name__=='__main__':unittest.main()
