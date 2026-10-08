"""Test348 duration enrollment, guardian lifecycle and offline deployment gates."""
import copy
import hashlib
import subprocess
import importlib.util
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock,patch
import test_sm5440_bounded_direct as old
import test_sm5440_duration_evidence as duration

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reference/boot-tests/test-348-confirmed-c1-twenty-minute'
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
f=load('flow348_tests',R/'host_flow.py');f.configure()
g=load('guard348_tests',R/'guard.py')
op=load('operations348_tests',R/'operations.py')


class TwentyMinuteTests(unittest.TestCase):
    def test_correct_unique_parameters_and_duration_are_required(self):
        good=dict(once='Y',**{'once-duration':'1200000'})
        flags=f.PLAN['cmdline_flags']
        self.assertEqual(f.validate_candidate_mode(['root=x']+flags,good),['root=x'])
        for tokens,sec in ((flags[:1],good),(flags+flags[:1],good),
                           (flags+['sm5440_fedora.direct_charge=1'],good),
                           (flags+['sm5440_fedora.direct_charge_once_ms=30000'],good),
                           (flags,dict(once='N',**{'once-duration':'1200000'})),
                           (flags,dict(once='Y',**{'once-duration':'30000'})),
                           (flags,dict(once='Y'))):
            with self.subTest(tokens=tokens,sec=sec),self.assertRaises(ValueError):
                f.validate_candidate_mode(tokens,sec)

    def test_unapproved_registration_cannot_stage_install_arm_or_activate(self):
        with patch.dict(f.PLAN,execution_authorized=False):self.assertFalse(f.authorized())
        with (patch.dict(f.PLAN,execution_authorized=False),patch.object(f,'verify_inputs'),patch.object(f.base,'verify_stage') as stage,
              patch.object(f.p,'Recorder') as recorder):
            for action in (f.stage,f.install,f.start,f.adopt):
                with self.subTest(action=action.__name__),self.assertRaises(ValueError):action()
            stage.assert_not_called();recorder.assert_not_called()

    def test_enrollment_rejects_prior30s_or_missing_explicit_owner_scope(self):
        scope=dict(test='Test348',PPS=True,pump_ON=True,pump_window_max_ms=1200000,
                   input_cap_ma=1800,hardware_programming_ma=1700,
                   registration_sha256='bad',execution_authorized=True,owner_instruction='Approve Test3481200s')
        with patch.object(f,'read',return_value=scope),patch.dict(f.PLAN,execution_authorized=True),patch.object(Path,'read_bytes',return_value=b'frozen fixture'):
            self.assertFalse(f.authorized())  # frozen registration binding mismatch
            for key,value in (('pump_window_max_ms',30000),('execution_authorized',False),
                              ('owner_instruction',''),('hardware_programming_ma',1800)):
                rejected=dict(scope,**{key:value})
                with patch.object(f,'read',return_value=rejected):self.assertFalse(f.authorized())

    def test_guardian_only_accepts_long_native_witness(self):
        long=duration.long_journal(1200000);proof=g.native_proof(long,old.BOOT,required=True)
        self.assertEqual((proof['window_ms'],proof['refreshes']),(1200000,240))
        with self.assertRaises(ValueError):
            g.native_proof(duration.legacy.journal(),old.BOOT,required=True)
        parser=(ROOT/'scripts/sm5440_bounded_evidence.py').read_text()
        with self.assertRaises(ValueError):
            g.native_proof(duration.long_journal(300000),old.BOOT,required=True)
        copied=(R/'guard.py').read_text()
        body=parser[parser.index('def native_proof('):].replace('def native_proof(','def duration_native_proof(',1).strip()
        self.assertIn(body,copied)  # shared pure parser bytes, no weakened fork

    def test_guardian_false_scope_rejects_before_hardware_is_opened(self):
        plan=dict(f.PLAN,boot_id=old.BOOT,execution_authorized=False)
        with (patch.object(Path,'read_bytes',return_value=b'config'),
              patch.object(g.gzip,'decompress',return_value=b'config'),
              patch.object(Path,'read_text',return_value='cmdline'),
              patch.object(g,'Hardware') as hardware):
            with self.assertRaisesRegex(ValueError,'authorized1200s'):g.run(plan,Path('/unused'))
            hardware.assert_not_called()

    def test_twenty_minute_uses_full_window_then_cleans_up_once(self):
        hw=Mock();hw.sample.return_value=old.sample()
        # Plain Mock fabricates activation methods; remove it for a registered
        # already-activated observation, so no simulated rebind is requested.
        del hw.activation
        calls=[];clock=[0.0]
        def sleep(seconds):clock[0]+=seconds
        def journal():return []
        proof=g.native_proof(duration.long_journal(1200000),old.BOOT,required=True)
        with patch.object(g,'native_proof',side_effect=lambda rows,boot:proof if clock[0]>=1200 else None):
            def sample():
                s=old.sample(on=clock[0]<1200)
                if clock[0]>=1200:s['tcpm']['POWER_SUPPLY_VOLTAGE_NOW']='9000000'
                return s
            hw.sample.side_effect=sample
            result=g.observe(hw,journal,lambda *x:calls.append(x),old.BOOT,
                             clock=lambda:clock[0],sleep=sleep)
        self.assertEqual(result['verdict'],'BOUNDED_NATIVE_RETURN_PASS')
        self.assertEqual(clock[0],1200)
        hw.stop.assert_called_once();hw.bind_once.assert_not_called()

    def test_guardian_native_error_latches_and_cleans_up_without_restart(self):
        hw=Mock();del hw.activation
        with patch.object(g,'native_proof',side_effect=ValueError('native STOP')):
            with self.assertRaisesRegex(ValueError,'native STOP'):
                g.observe(hw,lambda:[],lambda *x:None,old.BOOT)
        hw.stop.assert_called_once();hw.bind_once.assert_not_called()

    def test_cleanup_failure_keeps_primary_and_cleanup_separate(self):
        hw=Mock();del hw.activation;hw.stop.side_effect=ValueError('OFF failure')
        with patch.object(g,'native_proof',side_effect=ValueError('primary')):
            with self.assertRaises(g.CleanupFailure) as caught:
                g.observe(hw,lambda:[],lambda *x:None,old.BOOT)
        self.assertIn('primary',caught.exception.primary_error)
        self.assertIn('OFF failure',caught.exception.cleanup_error)
        hw.stop.assert_called_once()

    def test_first_non_clean_forbids_post_charge_and_repeat_observer(self):
        mock=Mock();mock.R=R;mock.PLAN=f.PLAN
        with patch.object(op,'enrolled',return_value=({},{})):
            with patch.object(Path,'exists',return_value=True):
                for phase in ('charge','discharge'):
                    with self.assertRaises(ValueError):op.observe(mock,phase)
                with self.assertRaises(ValueError):op.pc_return(mock)
        mock.p.Recorder.assert_not_called()

    def test_monitor_timeout_keeps_live_handle_and_never_restarts(self):
        start=dict(boot_id=old.BOOT,transport=dict(wifi='10.0.0.1'))
        state=dict(phase='owner-confirmed-single-activation',guardian_folder='/tmp/gts9-test348-monitor',guardian_pid=123)
        mock=Mock();mock.wifi_command.return_value=(json.dumps(dict(finished=False,alive=True,summary=None,stderr='')),0)
        mock.R=R;clock=iter((0,1301))
        mock.p.Recorder.return_value.folder=Path('/mock-evidence')
        with patch.object(op,'enrolled',return_value=(start,state)),patch.object(op.time,'monotonic',side_effect=lambda:next(clock)):
            result=op.monitor(mock)
        self.assertEqual(result['verdict'],'LIVE_GUARDIAN_OBSERVATION_PENDING')
        self.assertFalse(result['restart_allowed']);self.assertEqual(result['guardian_pid'],123)
        mock.start.assert_not_called();mock.restore.assert_not_called()

    def test_monitor_finished_stop_or_missing_handle_are_terminal_without_retry(self):
        start=dict(boot_id=old.BOOT,transport=dict(wifi='10.0.0.1'))
        state=dict(phase='owner-confirmed-single-activation',guardian_folder='/tmp/gts9-test348-monitor',guardian_pid=123)
        for status in (dict(finished=True,alive=False,summary=dict(verdict='STOP_FIRST_NON_CLEAN'),stderr=''),
                       dict(finished=False,alive=False,summary=None,stderr='')):
            mock=Mock();mock.R=R;mock.wifi_command.return_value=(json.dumps(status),0)
            mock.p.Recorder.return_value.folder=Path('/mock-evidence')
            with patch.object(op,'enrolled',return_value=(start,state)),patch.object(op,'record_failure') as failed:
                result=op.monitor(mock)
            self.assertIn('STOP',result['verdict']);failed.assert_called_once()
            mock.start.assert_not_called()

    def test_monitor_transport_timeout_is_unknown_not_native_failure_or_restart(self):
        start=dict(boot_id=old.BOOT,transport=dict(wifi='10.0.0.1'))
        state=dict(phase='owner-confirmed-single-activation',guardian_folder='/tmp/gts9-test348-monitor',guardian_pid=123)
        mock=Mock();mock.R=R;mock.p.Recorder.return_value.folder=Path('/mock-evidence')
        mock.wifi_command.side_effect=TimeoutError('probe timeout')
        with patch.object(op,'enrolled',return_value=(start,state)),patch.object(op,'record_failure') as failed:
            result=op.monitor(mock)
        self.assertEqual(result['verdict'],'GUARDIAN_CURRENT_STATE_UNKNOWN_TRANSPORT_FAILURE')
        self.assertFalse(result['native_failure_claim']);self.assertFalse(result['restart_allowed'])
        failed.assert_not_called();mock.start.assert_not_called();mock.restore.assert_not_called()

    def test_status_only_tracks_enrolled_pid_and_guardian_path(self):
        state=dict(guardian_folder='/tmp/gts9-test348-monitor',guardian_pid=123)
        command=op.status_command(state)
        self.assertIn('/proc/123/cmdline',command);self.assertIn('/tmp/gts9-test348-monitor/guard.py',command)
        for bad in (dict(state,guardian_pid=1),dict(state,guardian_folder='/tmp/other')):
            with self.assertRaises(ValueError):op.status_command(bad)

    def test_post_return_module_and_duration_checks_are_present(self):
        code=(R/'observe-post-return.py').read_text()
        self.assertIn('from bounded348_guard import native_proof',code)
        self.assertIn("parameters/direct_charge_once_ms')!='1200000'",code)
        self.assertEqual((f.PLAN['charge_seconds'],f.PLAN['discharge_seconds']),(30,15))
        self.assertIn('.gts9-test348-original',(R/'module-swap.sh').read_text())
        self.assertNotIn('.gts9-test345-original',(R/'module-swap.sh').read_text())

    def test_activation_soc60_cap_does_not_relax_runtime_safety(self):
        self.assertEqual((f.PLAN['preparation_soc_max'],f.PLAN['activation_soc_max']),(60,60))
        self.assertEqual((f.PLAN['hardware_input_setpoint_ma'],f.PLAN['physical_ibus_max_ua']),(1700,1800000))
        for section,key,value in (('adc','ibus_ua',1800625),('adc','die_decic',850),
                                  ('battery','POWER_SUPPLY_TEMP','420')):
            s=old.sample();s[section][key]=value
            with self.assertRaises(ValueError):g.check_sample(s)

    def test_actual_activation_refuses_soc61_but_accepts60(self):
        s=old.sample(on=False)
        s.update(roles=['sink','device'],pack_mode='enabled',pack_temp_mc=28000,
                 registers={0x10:1},usb=dict(POWER_SUPPLY_ONLINE='1',POWER_SUPPLY_INPUT_CURRENT_LIMIT='1500000'))
        s['tcpm'].update(POWER_SUPPLY_CURRENT_MAX='1500000',POWER_SUPPLY_VOLTAGE_NOW='9000000')
        rows=[old.row('Linux boot',0)]
        marker=dict(boot_id=old.BOOT,token='token',owner_confirmed_C1=True)
        s['battery']['POWER_SUPPLY_CAPACITY']='60'
        g.preparation_proof(rows,old.BOOT,s,False,marker,'token')
        s['battery']['POWER_SUPPLY_CAPACITY']='61'
        with self.assertRaisesRegex(ValueError,'SOC ceiling'):
            g.preparation_proof(rows,old.BOOT,s,False,marker,'token')

    def test_guardian_sysfs_duration_mismatch_refuses_before_i2c(self):
        import hashlib,gzip
        config=b'# CONFIG_HVC_DCC is not set\n';notes=b'notes'
        plan=dict(f.PLAN,execution_authorized=True,boot_id=old.BOOT,machine_id='mid',
                  candidate_config_sha256=hashlib.sha256(config).hexdigest(),
                  candidate_notes_sha256=hashlib.sha256(notes).hexdigest(),owner_confirmed_C1=True,owner_reply='connected',activation_token='token',activation_marker=dict(boot_id=old.BOOT,token='token',owner_confirmed_C1=True))
        data={'/proc/config.gz':gzip.compress(config),'/sys/kernel/notes':notes}
        text={'/proc/cmdline':plan['runtime_cmdline']+' '+' '.join(plan['cmdline_flags']),'/etc/machine-id':'mid'}
        prefix='/sys/module/sm5440_fedora/parameters/'
        text.update({prefix+'direct_charge_once':'Y',prefix+'direct_charge_once_ms':'30000'})
        text.update({prefix+x:'N' for x in ('direct_charge','fixed_return_check','pps_return_check')})
        with (patch.object(Path,'read_bytes',lambda p:data[str(p)]),
              patch.object(Path,'read_text',lambda p:text[str(p)]),patch.object(g,'Hardware') as hw):
            with self.assertRaisesRegex(ValueError,'exclusive test mode'):
                g.run(plan,Path('/unused'))
            hw.assert_not_called()

    def observation_entries(self,phase='charge'):
        original=json.loads((ROOT/'reference/boot-tests/test-345-final-refresh-reserve'/phase/'summary.json').read_text())
        endpoint=copy.deepcopy(original['endpoint'])
        endpoint.update(boot=old.BOOT,boot_end=old.BOOT,monotonic=31,uptime=400)
        rows=duration.long_journal(1200000);raw='\n'.join(json.dumps(x) for x in rows)
        proof=g.native_proof(rows,old.BOOT,required=True)
        samples=[]
        for t in range(32):
            d=copy.deepcopy(endpoint);d.update(kind='sample',monotonic=t);samples.append(d)
        result=dict(kind='verdict',verdict='PASS',phase=phase,observation_seconds=31,
                    native=proof,endpoint=endpoint)
        return [dict(kind='armed'),dict(kind='journal-before',raw=raw),*samples,
                dict(kind='journal-after',raw=raw),dict(kind='systemd-failed',raw=''),result]

    def test_post_observer_requires_native_duration_transport_and_full_evidence(self):
        plan=dict(f.PLAN,boot_id=old.BOOT)
        entries=self.observation_entries()
        with patch.object(op,'classify',return_value={}):
            result,raw,_=op.accepted(f,entries,0,'charge',plan)
            self.assertEqual(result['verdict'],'PASS')
            self.assertIn('max_ms=1200000',raw)
            variants=[(entries,255),
                      ([x for x in entries if x['kind']!='journal-after'],0),
                      ([x for x in entries if x['kind']!='armed'],0),
                      ([*entries,copy.deepcopy(entries[-1])],0)]
            for mutated,rc in variants:
                with self.assertRaises(ValueError):op.accepted(f,mutated,rc,'charge',plan)
            for field,value in (('native',{}),('observation_seconds',29.9)):
                mutated=copy.deepcopy(entries);mutated[-1][field]=value
                with self.assertRaises(ValueError):op.accepted(f,mutated,0,'charge',plan)

    def test_post_discharge_and_sample_faults_cannot_be_labeled_pass(self):
        plan=dict(f.PLAN,boot_id=old.BOOT)
        with patch.object(op,'classify',return_value={}):
            result,_,_=op.accepted(f,self.observation_entries('discharge'),0,'discharge',plan)
            self.assertEqual(result['verdict'],'PASS')
            for key,value in (('boot','b'*32),('pump',5),('monotonic',4.1)):
                entries=self.observation_entries();entries[3][key]=value
                with self.assertRaises(ValueError):op.accepted(f,entries,0,'charge',plan)
            entries=self.observation_entries('discharge')
            entries[-1]['endpoint']['battery']['POWER_SUPPLY_CURRENT_NOW']='1'
            with self.assertRaises(ValueError):op.accepted(f,entries,0,'discharge',plan)

class ConfirmedStartTests(unittest.TestCase):
    def owner(self,**updates):
        return dict(test='Test348',boot_id=old.BOOT,owner_reply='已接 USB-C1',received_epoch=990,**updates)

    def test_missing_stale_future_or_wrong_boot_confirmation_rejected(self):
        good=self.owner()
        with patch.object(f.time,'time',return_value=1000):
            with patch.object(f,'read',return_value=good):self.assertEqual(f.confirmation({'boot_id':old.BOOT}),good)
            for key,value in (('received_epoch',879),('received_epoch',1001),('received_epoch',True),('received_epoch',float('nan')),('owner_reply',''),('boot_id','wrong'),('test','Test346')):
                with patch.object(f,'read',return_value=dict(good,**{key:value})),self.assertRaises(ValueError):f.confirmation({'boot_id':old.BOOT})
            with patch.object(f,'read',side_effect=FileNotFoundError),self.assertRaises(FileNotFoundError):f.confirmation({'boot_id':old.BOOT})

    def test_no_process_launched_before_owner_confirmation(self):
        with (patch.object(f,'verify_inputs'),patch.object(f,'authorized',return_value=True),
              patch.object(f,'read',side_effect=[dict(phase='prepared-OFF-unbound'),dict(boot_id=old.BOOT)]),
              patch.object(f,'confirmation',side_effect=ValueError('missing fresh reply')),
              patch.object(f.p,'Recorder') as rec,patch.object(f,'wifi_command') as remote):
            with self.assertRaises(ValueError):f.start()
            rec.assert_not_called();remote.assert_not_called()

    def test_immediate_device_admission_binds_once_without_manual_wait(self):
        hw=Mock();hw.token='token';s=old.sample(on=False)
        s.update(roles=['sink','device'],pack_mode='enabled',pack_temp_mc=28000,registers={0x10:1},usb=dict(POWER_SUPPLY_ONLINE='1',POWER_SUPPLY_INPUT_CURRENT_LIMIT='1500000'))
        s['tcpm'].update(POWER_SUPPLY_CURRENT_MAX='1500000',POWER_SUPPLY_VOLTAGE_NOW='9000000')
        hw.activation.return_value=dict(boot_id=old.BOOT,token='token',owner_confirmed_C1=True);hw.sample.return_value=s;hw.is_bound.return_value=False
        sleep=Mock();g.activate_confirmed(hw,lambda:[old.row('Linux boot',0)],Mock(),old.BOOT,Mock(),sleep)
        hw.bind_once.assert_called_once();sleep.assert_not_called();hw.ready.assert_not_called()
        self.assertNotIn('manual handoff expired',(R/'guard.py').read_text())
        for key,value in (('POWER_SUPPLY_CAPACITY','61'),('POWER_SUPPLY_TEMP','420')):
            hw.reset_mock();bad=copy.deepcopy(s);bad['battery'][key]=value;hw.sample.return_value=bad
            with self.assertRaises(ValueError):g.activate_confirmed(hw,lambda:[old.row('Linux boot',0)],Mock(),old.BOOT,Mock(),sleep)
            hw.bind_once.assert_not_called()
        hw.sample.return_value=s;hw.activation.return_value=None
        with self.assertRaises(ValueError):g.activate_confirmed(hw,lambda:[],Mock(),old.BOOT,Mock(),sleep)
        hw.bind_once.assert_not_called()

    def test_launch_ambiguity_retains_state_and_rejects_another_start(self):
        import time
        with tempfile.TemporaryDirectory() as directory:
            r=Path(directory);(r/'guard.py').write_text((R/'guard.py').read_text())
            state=dict(phase='prepared-OFF-unbound',rollback_required=True,candidate_boot_id=old.BOOT)
            start=dict(boot_id=old.BOOT,transport=dict(wifi='10.0.0.1'))
            (r/'mutation-state.json').write_text(json.dumps(state));(r/'startup-summary.json').write_text(json.dumps(start))
            (r/'owner-C1-confirmation.json').write_text(json.dumps(dict(test='Test348',boot_id=old.BOOT,owner_reply='connected',received_epoch=time.time())))
            remote=Mock(side_effect=[('{}',0),('',0),TimeoutError('launch SSH response lost')])
            with patch.object(f,'R',r),patch.object(f,'verify_inputs'),patch.object(f,'authorized',return_value=True),patch.object(f,'wifi_command',remote):
                with self.assertRaises(TimeoutError):f.start()
                self.assertEqual(json.loads((r/'mutation-state.json').read_text())['phase'],'start-requested-unknown-status')
                count=remote.call_count
                with self.assertRaises(ValueError):f.start()
                self.assertEqual(remote.call_count,count)
                command=remote.call_args.args[-1]
                self.assertIn('/pid',command);self.assertIn('nohup',command)

    def test_adopt_reads_original_pid_and_never_launches_or_binds(self):
        state=dict(phase='start-requested-unknown-status',guardian_folder='/tmp/gts9-test348-monitor',rollback_required=True)
        start=dict(boot_id=old.BOOT,transport=dict(wifi='10.0.0.1'))
        with (patch.object(f,'verify_inputs'),patch.object(f,'authorized',return_value=True),
              patch.object(f,'read',side_effect=[state,start]),patch.object(f,'write') as write,
              patch.object(f,'wifi_command',return_value=('{"pid":123}',0)) as remote,
              patch.object(f.p,'Recorder')):
            result=f.adopt()
            self.assertEqual((result['guardian_pid'],result['phase']),(123,'owner-confirmed-single-activation'))
            command=remote.call_args.args[-1]
            self.assertNotIn('nohup',command);self.assertNotIn('/bind',command)
            self.assertIn('/proc/',command);self.assertIn('p/"pid"',command)

    def test_persistent_trust_uses_only_registered_key_and_refuses_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'known-hosts'
            with patch.dict(f.PLAN,known_hosts=str(p)):
                f.ensure_trust();expected=f.PLAN['alias']+' '+f.PLAN['host_ed25519_key']+'\n'
                self.assertEqual(p.read_text(),expected);self.assertEqual(p.stat().st_mode&0o777,0o600)
                f.ensure_trust();p.write_text('different-key\n')
                with self.assertRaises(ValueError):f.ensure_trust()
                self.assertEqual(p.read_text(),'different-key\n')
                p.unlink();p.symlink_to(Path(directory)/'absent')
                with self.assertRaises(ValueError):f.ensure_trust()

    def test_confirmation_metadata_is_required_before_device_i2c(self):
        import gzip,hashlib
        config=b'# CONFIG_HVC_DCC is not set\n'
        plan=dict(f.PLAN,execution_authorized=True)
        with patch.object(Path,'read_bytes',return_value=gzip.compress(config)),patch.object(Path,'read_text',return_value=''),patch.object(g,'Hardware') as hardware:
            with self.assertRaisesRegex(ValueError,'owner-confirmed C1'):g.run(plan,Path('/unused'))
            hardware.assert_not_called()

    def test_valid_scope_binds_frozen_inputs_and_owner_grant(self):
        import hashlib
        frozen=b'registered347'
        scope=dict(test='Test348',PPS=True,pump_ON=True,pump_window_max_ms=1200000,
                   input_cap_ma=1800,hardware_programming_ma=1700,execution_authorized=True,
                   owner_instruction='Approve one Test3481200s',registration_sha256=hashlib.sha256(frozen).hexdigest())
        with patch.object(f,'read',return_value=scope),patch.object(Path,'read_bytes',return_value=frozen),patch.dict(f.PLAN,execution_authorized=True):
            self.assertTrue(f.authorized())
        with patch.object(f,'read',return_value=scope),patch.object(Path,'read_bytes',return_value=frozen),patch.dict(f.PLAN,execution_authorized=False):
            self.assertFalse(f.authorized())

    def test_failed_prelaunch_admission_cannot_be_replayed(self):
        with tempfile.TemporaryDirectory() as directory:
            r=Path(directory);(r/'guard.py').write_text((R/'guard.py').read_text())
            state=dict(phase='prepared-OFF-unbound');start=dict(boot_id=old.BOOT,transport=dict(wifi='10.0.0.1'))
            (r/'mutation-state.json').write_text(json.dumps(state));(r/'startup-summary.json').write_text(json.dumps(start))
            remote=Mock(side_effect=ValueError('sensor invalid'))
            with (patch.object(f,'R',r),patch.object(f,'verify_inputs'),patch.object(f,'authorized',return_value=True),
                  patch.object(f,'confirmation',return_value=self.owner()),patch.object(f,'wifi_command',remote)):
                with self.assertRaises(ValueError):f.start()
                self.assertTrue((r/'guardian-start').exists())
                with self.assertRaises(ValueError):f.start()
                self.assertEqual(remote.call_count,1)

class RecoveryEndpointTests(unittest.TestCase):
    def restore(self, *, rejected=False):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'mutation-state.json').write_text(json.dumps(dict(rollback_required=True,candidate_boot_id=old.BOOT)))
            rec=Mock();rec.folder=root/'rollback-install';rec.folder.mkdir()
            def adb(name, command, **kwargs):
                return ({'target-boot-id':old.BOOT,'target-boots':'history',
                         'module-layout':'saved','final-twrp-identity':'gts9wifi\n3.7.1\nLinux5.15\nuid=0\n'}.get(name,''),0)
            rec.adb.side_effect=adb
            with (patch.object(f,'R',root),patch.object(f,'verify_inputs'),
                  patch.object(f.p,'Recorder',return_value=rec),
                  patch.object(f.h,'enter_recovery'),patch.object(f.base,'transfer'),
                  patch.object(f.base,'restoration_layout',return_value=f.PACKAGE['candidate_partitions']['boot']),
                  patch.object(f.h,'verify_modules') as modules,patch.object(f.h,'write_boot') as boot,
                  patch.object(f.h,'require_partitions',side_effect=ValueError('partition mismatch') if rejected else None),
                  patch.object(f.h,'clear_unmount') as unmount):
                if rejected:
                    with self.assertRaises(ValueError):f.restore()
                    self.assertTrue(json.loads((root/'mutation-state.json').read_text())['rollback_required'])
                    unmount.assert_not_called()
                else:
                    result=f.restore()
                    self.assertEqual(result['final_endpoint'],'TWRP')
                    self.assertFalse(result['rollback_required'])
                    self.assertFalse(result['Debian_reboot_executed'])
                    self.assertFalse(result['restored_Debian_runtime_acceptance_executed'])
                    modules.assert_called_once();boot.assert_called_once();unmount.assert_called_once()
                rec.host_adb.assert_not_called()
    def test_exact_restoration_stays_in_twrp_without_debian_reboot(self):
        self.restore()
    def test_partition_failure_cannot_mark_restoration_complete(self):
        self.restore(rejected=True)

class TwentyMinuteRegistrationTests(unittest.TestCase):
    def test_duration_outer_limits_and_original_fault_deadlines(self):
        p=f.PLAN
        self.assertEqual((p['pump_window_max_ms'],p['native_outer_seconds'],p['host_outer_seconds']),
                         (1200000,1260,1500))
        self.assertEqual((p['delivery_gap_max_ms'],p['sample_gap_max_seconds'],
                          p['readiness_max_seconds'],p['confirmation_max_age_seconds']),
                         (500,3,90,120))
        self.assertEqual((p['manual_handoff_seconds'],p['preparation_soc_max'],p['activation_soc_max']),
                         (0,60,60))
        self.assertEqual(p['final_endpoint'],'TWRP')
        with patch.dict(f.PLAN,execution_authorized=False):
            self.assertFalse(f.authorized())

    def test_closed_test347_grant_cannot_authorize_twenty_minute_test(self):
        import hashlib
        data=b'registered348'
        scope=dict(test='Test347',PPS=True,pump_ON=True,pump_window_max_ms=300000,
                   input_cap_ma=1800,hardware_programming_ma=1700,execution_authorized=True,
                   owner_instruction='prior300s scope',registration_sha256=hashlib.sha256(data).hexdigest())
        with patch.object(f,'read',return_value=scope),patch.object(Path,'read_bytes',return_value=data),patch.dict(f.PLAN,execution_authorized=True):
            self.assertFalse(f.authorized())

    def test_old300s_cmdline_cannot_be_admitted_as1200s(self):
        flags=['sm5440_fedora.direct_charge_once=1','sm5440_fedora.direct_charge_once_ms=300000']
        with self.assertRaises(ValueError):
            f.validate_candidate_mode(flags,dict(once='Y',**{'once-duration':'300000'}))
