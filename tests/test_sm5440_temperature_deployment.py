"""Only the new Test341 admission/scoping adapter; no device access."""
import copy, importlib.util, json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reference/boot-tests/test-341-temperature-unit-activation'
spec=importlib.util.spec_from_file_location('bounded_deploy',R/'host_flow.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f);f.configure()
class DeploymentTests(unittest.TestCase):
    def packet(self,candidate=False):
        raw=(R.parent/'test-338-bounded-direct-1p8a/preflight/current-state.txt').read_text()
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
    def test_unique_341_modules_install_restore(self):
        import hashlib, io, tarfile
        from unittest.mock import patch
        import test_sm5440_module_staging as old
        fixture=old.ModuleStagingTests(methodName='runTest');fixture.setUp();self.addCleanup(fixture.doCleanups)
        data={f'new-{n:03}.ko':('new '+str(n)).encode() for n in range(181)}
        archive=fixture.work/'new.tar.gz'
        with tarfile.open(archive,'w:gz') as tar:
            for name,value in data.items():
                item=tarfile.TarInfo(old.RELEASE+'/'+name);item.size=len(value);tar.addfile(item,io.BytesIO(value))
        expected={n:hashlib.sha256(v).hexdigest() for n,v in data.items()};manifest=fixture.manifest('new.sha256',expected)
        with patch.object(old,'HELPER',R/'module-swap.sh'):
            result=fixture.call('install',manifest,archive);self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue((fixture.base/'.gts9-test341-original').is_dir());self.assertFalse((fixture.base/'.gts9-test339-original').exists())
            self.assertEqual(fixture.current_hashes(),expected)
            result=fixture.call('restore',fixture.old_manifest);self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(fixture.current_hashes(),fixture.old)

    def test_scope_and_namespace(self):
        self.assertTrue(f.authorized())
        self.assertEqual(f.h.TMP,'/tmp/gts9-test341')
        self.assertIn('gts9-test341',f.h.STAGE)
        self.assertNotEqual(json.loads((R/'staged-files.json').read_text())['module-swap.sh']['sha256'],json.loads((R.parent/'test-337-async-fixed-charge-restore/staged-files.json').read_text())['module-swap.sh']['sha256'])
class LifecycleTests(unittest.TestCase):
    def test_park_refuses_prior_stop_entry_and_wrong_phase_before_unbind(self):
        from unittest.mock import patch
        import test_sm5440_bounded_direct as old
        for message in ('one-shot entry begins: fixed9=1','one-shot pump stopped: primary=-110 cleanup=0 lease=0 no_restart=1'):
            rows=[old.row('Linux boot',0),old.row(message,1000000)]
            with patch.object(f,'read',side_effect=[dict(phase='candidate-admitted'),dict(boot_id=old.BOOT,transport=dict(wifi='192.0.2.1'))]),patch.object(f.p,'Recorder'),patch.object(f,'wifi_command',return_value=('\n'.join(json.dumps(x) for x in rows),0)) as wifi:
                self.assertRaises(ValueError,f.park)
                self.assertEqual(wifi.call_count,1)
        with patch.object(f,'read',return_value=dict(phase='STOP')),patch.object(f,'wifi_command') as wifi:
            self.assertRaises(ValueError,f.park);wifi.assert_not_called()
    def test_activate_requires_actual_owner_confirmation_and_correct_phase(self):
        from unittest.mock import patch
        state=dict(phase='guardian-armed-awaiting-owner-C1')
        for confirmation in ({},dict(test='Test341',boot_id='stale',owner_reply='已接入'),dict(test='Test341',boot_id='a'*32,owner_reply='')):
            with patch.object(f,'verify_inputs'),patch.object(f,'read',side_effect=[state,dict(boot_id='a'*32),confirmation]),patch.object(f,'wifi_command') as wifi:
                self.assertRaises(ValueError,f.activate);wifi.assert_not_called()
        with patch.object(f,'verify_inputs'),patch.object(f,'read',return_value=dict(phase='owner-confirmed-single-activation')),patch.object(f,'wifi_command') as wifi:
            self.assertRaises(ValueError,f.activate);wifi.assert_not_called()
    def test_actual_marker_script_compiles_and_records_single_activation(self):
        import shlex
        from unittest.mock import patch,Mock
        start=dict(boot_id='a'*32,transport=dict(wifi='192.0.2.1'))
        state=dict(phase='guardian-armed-awaiting-owner-C1',guardian_folder='/tmp/test341')
        confirm=dict(test='Test341',boot_id=start['boot_id'],owner_reply='已接C1')
        def remote(rec,name,address,command):
            text=shlex.split(command)[2];compile(text,'remote-activate','exec')
            self.assertIn('g.preparation_proof',text);self.assertIn('open("x")',text)
            return ('{}',0)
        with patch.object(f,'verify_inputs'),patch.object(f,'read',side_effect=[state,start,confirm,dict(activation_token='unique')]),patch.object(f.p,'Recorder',return_value=Mock(folder=R/'fake')),patch.object(f,'write'),patch.object(f,'wifi_command',side_effect=remote) as remote_call:
            result=f.activate();self.assertEqual(result['phase'],'owner-confirmed-single-activation');self.assertEqual(remote_call.call_count,1)
    def test_actual_park_script_compiles_and_precedes_guardian(self):
        import shlex
        from unittest.mock import patch,Mock
        import test_sm5440_bounded_direct as old
        calls=[]
        def remote(rec,name,address,command):
            calls.append(name)
            if name=='journal-before':return (json.dumps(old.row('Linux boot',0)),0)
            compile(shlex.split(command)[2],'remote-park','exec')
            return ('{}' if name=='parked-proof' else '',0)
        with patch.object(f,'read',side_effect=[dict(phase='candidate-admitted'),dict(boot_id=old.BOOT,transport=dict(wifi='192.0.2.1'))]),patch.object(f.p,'Recorder',return_value=Mock(folder=R/'fake')),patch.object(f,'write'),patch.object(f,'wifi_command',side_effect=remote):
            self.assertEqual(f.park()['phase'],'prepared-OFF-unbound')
            self.assertEqual(calls,['journal-before','cancel-preparation-worker','parked-proof'])
if __name__=='__main__':unittest.main()
