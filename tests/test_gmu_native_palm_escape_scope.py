"""Independent Test370: exact module transactions, boot gates and old fault retention."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reference/boot-tests/test-370-gmu-native-palm-escape'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


H=load('gmu370_flow_tests',R/'host_flow.py')
D=load('gmu370_overlay_tests',R/'desktop.py')
OLD=load('gmu370_old_transaction_fixtures',ROOT/'tests/test_ssc_trace_scope.py')


class OverlayTests(OLD.DesktopOverlayTests):
    def setUp(self):
        p=patch.object(OLD,'D',D);p.start();self.addCleanup(p.stop)
        super().setUp()


class GateTests(unittest.TestCase):
    def packet(self,phase='candidate'):
        value=OLD.TraceFlowTests().packet(phase)
        value.update(config_sha256=H.PLAN[phase+'_config_sha256'],
                     notes_sha256=H.PLAN[phase+'_notes_sha256'])
        value['adsp'][0]['state']='offline'
        return value

    def test_candidate_text_and_baseline_desktop_gates(self):
        p=self.packet();H.identity(p,'candidate',p['boot_id'])
        p['services']['gdm']='active'
        with self.assertRaises(ValueError):H.identity(p,'candidate')
        H.identity(p,'candidate',allow_desktop=True)
        p=self.packet('baseline');p['services']['gdm']='active';H.identity(p,'baseline')

    def test_palm_pair_does_not_require_superseded_standalone_pen_unit(self):
        p=self.packet();p['services'].update(gdm='active',**{'gts9-palm':'active','gts9-pen':'inactive'})
        H.desktop_health(p)
        for unit in ('gdm','gts9-palm','gts9-pen'):
            bad=copy.deepcopy(p);bad['services'][unit]='failed'
            with self.assertRaises(ValueError):H.desktop_health(bad)

    def test_wrong_notes_boot_and_dcc_stop(self):
        for key,value in (('notes_sha256','old'),('boot_id','wrong'),('dcc_absent',False)):
            p=self.packet();p[key]=value
            with self.assertRaises(ValueError):H.identity(p,'candidate')

    def test_no_adsp_activation_pump_or_unsafe_battery(self):
        for change in ('adsp','pump','hot','SOC','VBAT'):
            p=self.packet()
            if change=='adsp':p['adsp'][0]['state']='running'
            elif change=='pump':p['direct_default']='Y'
            else:p['battery'][{'hot':'POWER_SUPPLY_TEMP','SOC':'POWER_SUPPLY_CAPACITY','VBAT':'POWER_SUPPLY_VOLTAGE_NOW'}[change]]={'hot':'420','SOC':'86','VBAT':'4440000'}[change]
            with self.assertRaises(ValueError):H.identity(p,'candidate')

    def original(self):
        return [json.loads(line) for line in H.BASELINE_JOURNAL.read_text().splitlines()]

    def raw(self,rows):return '\n'.join(json.dumps(row) for row in rows)

    def pair(self):
        rows=self.original();base=copy.deepcopy(rows[-1]);start=int(base['__MONOTONIC_TIMESTAMP'])+1000
        first=dict(base,MESSAGE='platform 3d6a000.gmu: [drm:a6xx_hfi_wait_for_msg_interrupt] *ERROR* Message HFI_H2F_MSG_GX_BW_PERF_VOTE id 9 timed out waiting for response',__CURSOR='extra-timeout',__MONOTONIC_TIMESTAMP=str(start),PRIORITY='3')
        second=dict(base,MESSAGE='platform 3d6a000.gmu: [drm:a6xx_hfi_send_msg] *ERROR* Unexpected message id 9 on the response queue',__CURSOR='extra-response',__MONOTONIC_TIMESTAMP=str(start+1000),PRIORITY='3')
        return rows,first,second

    def test_old_failed_boot_is_preserved_not_called_clean(self):
        rows=self.original();result=H.baseline_errors(self.raw(rows),rows[0]['_BOOT_ID'])
        self.assertFalse(result['clean']);self.assertEqual(result['additional_GMU_pairs'],[])

    def test_bounded_existing_gmu_pair_is_recorded_unresolved(self):
        rows,first,second=self.pair();result=H.baseline_errors(self.raw(rows+[first,second]),first['_BOOT_ID'])
        self.assertFalse(result['clean']);self.assertEqual(result['additional_GMU_pairs'][0]['id'],9)

    def test_missing_old_row_unknown_error_cpu_fault_and_malformed_pair_stop(self):
        rows,first,second=self.pair();boot=first['_BOOT_ID']
        cases=[rows[1:],rows+[first],rows+[dict(first,MESSAGE='BUG: new fault')],
               rows+[dict(first,MESSAGE='unknown kernel error'),second],
               rows+[first,dict(second,MESSAGE=second['MESSAGE'].replace('id 9','id 8'))],
               rows+[first,dict(second,__MONOTONIC_TIMESTAMP=str(int(first['__MONOTONIC_TIMESTAMP'])+100001))]]
        for case in cases:
            with self.assertRaises(ValueError):H.baseline_errors(self.raw(case),boot)

    def test_candidate_never_inherits_gmu_error_allowance(self):
        rows,first,second=self.pair();rec=Mock();rec.adb.return_value=(self.raw(rows+[first,second]),0)
        with self.assertRaisesRegex(ValueError,'GPU HFI error'):H.scan(rec,first['_BOOT_ID'],45000)

    def test_empty_mixed_boot_duplicate_and_missing_metadata_stop(self):
        rows=self.original();first=rows[0];boot=first['_BOOT_ID']
        for raw in ('',self.raw([first,first]),self.raw([dict(first,_BOOT_ID='0'*32)]),self.raw([dict(first,__CURSOR='')])):
            with self.assertRaises(ValueError):H.kernel_rows(raw,boot)

    def test_restore_checks370_module_ownership_before_boot_write(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(H,'R',Path(tmp)):
            (Path(tmp)/'mutation-state.json').write_text(json.dumps(dict(rollback_required=True)))
            rec=Mock();rec.folder=Path(tmp)
            def adb(name,command,**kwargs):
                if name=='twrp-identity':return 'gts9wifi Linux 4.19 uid=0',0
                if name=='partitions-before':return 'fixture',0
                if name=='restore-modules':
                    self.assertIn('.gts9-test370-original',command)
                    self.assertIn(H.PACKAGE['candidate_build_link'],command)
                    self.assertNotIn('.gts9-test366-original',command)
                    raise ValueError('wrong original backup')
                return '',0
            rec.adb.side_effect=adb
            with patch.object(H.p,'Recorder',return_value=rec),patch.object(H,'transfer'),patch.object(H,'restore_layout',return_value=H.PACKAGE['candidate_partitions']),patch.object(H,'write_partition') as write:
                with self.assertRaises(ValueError):H.restore(True)
                write.assert_not_called()

    def test_first_failure_preserved_and_install_cannot_replay(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(H,'R',Path(tmp)):
            H.stop(ValueError('first'));H.stop(ValueError('second'))
            self.assertEqual(json.loads((Path(tmp)/'first-failure.json').read_text())['error'],'first')
            with patch.object(H,'verify_inputs'),patch.object(H,'verify_stage'),patch.object(H.h,'enter_recovery') as enter:
                with self.assertRaisesRegex(ValueError,'no replay'):H.install()
                enter.assert_not_called()

    def test_registration_freezes_one_boot_no_sensor_or_charging_enable(self):
        self.assertEqual(H.PLAN['attempts'],1)
        for key in ('PPS','pump_ON','charging_limits_changed','runtime_daemons_started'):self.assertFalse(H.PLAN[key])
        delta=[k for k,v in H.PACKAGE['candidate_partitions'].items() if v!=H.PACKAGE['baseline_partitions'][k]]
        self.assertEqual(delta,['boot']);self.assertEqual(len(D.ALLOWED),6)
        self.assertFalse(any('gts9-pen' in name for name in D.ALLOWED))
        self.assertFalse(any('hexagonrpc' in name or 'sensor' in name for name in D.ALLOWED))
        self.assertEqual(H.PLAN['candidate_notes_sha256'],'5c0e82337affafefff586613d4a84c4f1388c9716ce251fe69d3c70aad18a518')
        with self.assertRaises(ValueError):H.write_partition(Mock(),'vendor_boot','vendor_boot.img','0'*64,'1'*64)

    def test_live_module_gate_uses_exact_registered_link_layout(self):
        rec=Mock()
        H.modules(rec,'candidate',True)
        command=rec.adb.call_args.args[1]
        self.assertIn(H.PACKAGE['candidate_build_link'],command)
        self.assertIn('test "$(find . -type l | wc -l)" = 1',command)
        H.modules(rec,'baseline',False)
        self.assertIn('test "$(find . -type l | wc -l)" = 0',rec.adb.call_args.args[1])

    def test_current_frozen_inputs_and_artifacts_qualify_before_staging(self):
        H.verify_inputs()
        bad=copy.deepcopy(H.PACKAGE)
        bad['artifacts']['boot.img']['sha256']='0'*64
        with patch.object(H,'PACKAGE',bad):
            with self.assertRaisesRegex(ValueError,'artifact drift'):H.verify_inputs()


class ModuleTransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'root';(self.root/'etc').mkdir(parents=True)
        (self.root/'etc/machine-id').write_text(H.PLAN['machine_id'])
        self.base=self.root/'usr/lib/modules';self.current=self.base/H.PLAN['release'];self.current.mkdir(parents=True)
        self.candidate=Path(self.tmp.name)/'incoming'/H.PLAN['release'];self.candidate.mkdir(parents=True)
        for i in range(181):
            (self.current/f'file{i}').write_bytes(('old'+str(i)).encode())
            (self.candidate/f'file{i}').write_bytes(('new'+str(i)).encode())
        (self.candidate/'build').symlink_to(H.PACKAGE['candidate_build_link'])
        self.old=self.manifest(self.current,'rollback-modules.sha256')
        self.new=self.manifest(self.candidate,'candidate-modules.sha256')
        self.archive=Path(self.tmp.name)/'modules.tar.gz';self.pack()

    def manifest(self,directory,name):
        p=Path(self.tmp.name)/name
        p.write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.name+'\n' for f in sorted(directory.iterdir()) if f.is_file() and not f.is_symlink()))
        return p

    def pack(self):
        with tarfile.open(self.archive,'w:gz') as archive:archive.add(self.candidate,arcname=H.PLAN['release'])

    def install(self):
        return subprocess.run(['sh',str(R/'module-swap.sh'),str(self.root),'install',str(self.new),str(self.archive),str(self.old)],capture_output=True,text=True)

    def restore(self):
        command=H.recovery.command(str(self.root),H.PLAN['release'],H.PLAN['namespace'],str(self.old),str(self.new),H.PLAN['machine_id'])
        return subprocess.run(['sh','-c',command],capture_output=True,text=True)

    def test_real_archive_install_and_namespace_restore(self):
        result=self.install();self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue((self.base/'.gts9-test370-original').is_dir())
        self.assertEqual((self.current/'file0').read_bytes(),b'new0')
        result=self.restore();self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual((self.current/'file0').read_bytes(),b'old0')
        self.assertFalse((self.current/'build').exists())

    def test_wrong_build_link_refused_before_original_rename(self):
        (self.candidate/'build').unlink();(self.candidate/'build').symlink_to('/wrong-provider');self.pack()
        self.assertNotEqual(self.install().returncode,0)
        self.assertEqual((self.current/'file0').read_bytes(),b'old0')
        self.assertFalse((self.base/'.gts9-test370-original').exists())

    def test_corrupt_original_or_candidate_refuses_recovery_without_rename(self):
        self.assertEqual(self.install().returncode,0)
        saved=self.base/'.gts9-test370-original/file0';saved.write_bytes(b'unknown')
        self.assertNotEqual(self.restore().returncode,0)
        self.assertEqual((self.current/'file0').read_bytes(),b'new0')
        self.assertFalse((self.base/'.gts9-test370-tested').exists())

    def test_partial_install_before_original_rename_keeps_baseline(self):
        stage=self.base/'.gts9-test370-stage';stage.mkdir()
        (stage/'partial').write_text('unfinished copy')
        result=self.restore();self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual((self.current/'file0').read_bytes(),b'old0')


if __name__=='__main__':unittest.main()
