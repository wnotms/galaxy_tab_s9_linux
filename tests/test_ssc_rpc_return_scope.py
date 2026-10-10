import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'reference/boot-tests/test-388-ssc-rpc-return-content'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


H = load('ssc388_host', R / 'host_flow.py')
M = load('ssc388_runtime', R / 'runtime.py')
L = load('ssc388_lifecycle', ROOT / 'userspace/sensors/ssc_lifecycle.py')


D = load('ssc388_overlay', R / 'desktop.py')

class RuntimeStartupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.d = json.loads((ROOT / 'reference/boot-tests/test-377-ssc-userspace-pd-mapper/runtime-discovery/boundary.txt').read_text())
        self.d['cmdline'] = H.PLAN['runtime_cmdline']
        self.plan = H.PLAN | {'boot_id': self.d['boot_id']}
        self.active = set()
        self.commands = []
        for name, key in [('usr/local/lib/gts9-test388/hexagonrpcd', 'trace_sha256'),
                          ('usr/lib/aarch64-linux-gnu/libhexagonrpc.so.0.4', 'trace_library_sha256')]:
            p = self.root / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(name.encode())
            self.plan[key] = M.sha(p)
        p = self.root / 'usr/bin/stdbuf'; p.parent.mkdir(parents=True, exist_ok=True); p.touch()
        self.runner = M.Runtime(self.plan, lambda: self.d, lambda _: {}, self.root,
                                self.invoke, start_rpc=L.start_rpc)
        self.runner.save(dict(phase='prepared-inactive', started=False,
                              boot_id=self.d['boot_id']))

    def invoke(self, argv, **kwargs):
        self.commands.append(argv)
        if argv[1] == 'show':
            return '/usr/bin/stdbuf -oL -eL /usr/local/lib/gts9-test388/hexagonrpcd'
        if argv[1] == 'start':
            state = json.loads(self.runner.path(M.STATE).read_text())
            self.assertEqual(state['rpc_requested'][-1], argv[-1])
            self.assertTrue(self.runner.path(M.GATE).exists())
            self.active.add(argv[-1]); return ''
        return 'active' if argv[-1] in self.active else 'inactive'

    def test_actual_runtime_starts_both_roles_root_first_no_mapper(self):
        self.runner.start()
        starts = [c for c in self.commands if c[1] == 'start']
        self.assertEqual(starts, [['systemctl', 'start', L.ROOT_PD],
                                  ['systemctl', 'start', L.SENSOR_PD]])

    def test_100_percent_soc_permitted_for_passive_discovery(self):
        self.d['battery']['POWER_SUPPLY_CAPACITY'] = '100'
        self.runner.start()
        self.assertEqual(self.active, set(L.RPC_UNITS))

    def test_new_boot_or_live_desktop_blocks_before_start(self):
        for mutate in ('boot', 'desktop'):
            saved = copy.deepcopy(self.d)
            if mutate == 'boot': self.d['boot_id'] = '22222222-2222-2222-2222-222222222222'
            else: self.d['services']['gdm'] = 'active'
            with self.assertRaises(ValueError): self.runner.start()
            self.assertFalse(self.active)
            self.d = saved

    def test_trace_drift_blocks_before_gate(self):
        self.runner.path('/usr/local/lib/gts9-test388/hexagonrpcd').write_bytes(b'changed')
        with self.assertRaises(ValueError): self.runner.start()
        self.assertFalse(self.runner.path(M.GATE).exists())
        self.assertFalse(self.active)

    def test_missing_helper_blocks_without_runtime_start(self):
        self.runner.start_rpc = None
        with self.assertRaises(ValueError): self.runner.start()
        self.assertFalse(self.active)
        self.assertFalse(self.runner.path(M.GATE).exists())

    def test_second_runtime_start_refused(self):
        self.runner.start()
        with self.assertRaises(ValueError): self.runner.start()
        self.assertEqual(len([c for c in self.commands if c[1] == 'start']), 2)


class OverlayTransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'root';self.incoming=Path(self.tmp.name)/'incoming'
        (self.root/'etc').mkdir(parents=True);self.incoming.mkdir()
        (self.root/'etc/machine-id').write_text(D.MACHINE+'\n')
        self.manifest=json.loads((R/'desktop-manifest.json').read_text())
        for row in self.manifest.values():
            (self.incoming/row['incoming']).write_bytes((ROOT/row['source']).read_bytes())
    def install(self):return D.install(self.root,self.incoming,self.manifest)
    def test_real_registered_eight_file_install_and_complete_restore(self):
        self.assertEqual(set(self.manifest),D.ALLOWED)
        result=self.install();self.assertEqual(result['files'],8)
        for name,row in self.manifest.items():
            p=self.root/name;self.assertEqual(D.digest(p.read_bytes()),row['sha256'])
            self.assertEqual(p.stat().st_mode&0o777,row['mode'])
        result=D.restore(self.root);self.assertFalse(result['services_started'])
        for name in self.manifest:self.assertFalse((self.root/name).exists())
        self.assertFalse((self.root/D.STATE).exists())
        self.assertEqual((self.root/'etc/machine-id').read_text(),D.MACHINE+'\n')
    def test_unregistered_diagnostic_path_is_rejected_before_mutation(self):
        self.manifest['usr/local/lib/gts9-test388/rpmsg_diagnostic.py']=next(iter(self.manifest.values()))
        with self.assertRaisesRegex(ValueError,'file set'):self.install()
        self.assertFalse((self.root/D.STATE).exists())
    def test_missing_one_file_is_not_silently_accepted(self):
        self.manifest.pop(next(iter(self.manifest)))
        with self.assertRaises(ValueError):self.install()
        self.assertFalse((self.root/D.STATE).exists())
    def test_wrong_machine_cannot_write(self):
        (self.root/'etc/machine-id').write_text('other')
        with self.assertRaises(ValueError):self.install()
        self.assertFalse((self.root/D.STATE).exists())
    def test_corrupt_incoming_bytes_rejected_before_ledger(self):
        row=next(iter(self.manifest.values()));(self.incoming/row['incoming']).write_bytes(b'corrupt')
        with self.assertRaises(ValueError):self.install()
        self.assertFalse((self.root/D.STATE).exists())
    def test_unowned_existing_target_rejected_without_overwrite(self):
        name=next(iter(self.manifest));p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'foreign')
        with self.assertRaises(ValueError):self.install()
        self.assertEqual(p.read_bytes(),b'foreign');self.assertFalse((self.root/D.STATE).exists())
    def test_no_second_install_into_owned_ledger(self):
        self.install()
        with self.assertRaises(ValueError):self.install()
    def test_restore_checks_all_files_before_removing_any(self):
        self.install();name=sorted(self.manifest)[-1];(self.root/name).write_bytes(b'foreign-new')
        with self.assertRaises(ValueError):D.restore(self.root)
        self.assertTrue(all((self.root/n).exists() for n in self.manifest))
        self.assertTrue((self.root/D.STATE).exists())
    def test_partial_install_can_restore_without_deleting_foreign_files(self):
        original=D.atomic;fail=sorted(self.manifest)[2]
        def atomic(path,data,mode=0o600):
            if path==self.root/fail:raise OSError('injected copy fault')
            return original(path,data,mode)
        with patch.object(D,'atomic',side_effect=atomic):
            with self.assertRaises(OSError):self.install()
        D.restore(self.root)
        self.assertFalse((self.root/D.STATE).exists());self.assertTrue(all(not (self.root/n).exists() for n in self.manifest))
    def test_qualified_original_file_bytes_mode_and_mtime_restored(self):
        name=sorted(self.manifest)[0];p=self.root/name;p.parent.mkdir(parents=True);p.write_bytes(b'original');p.chmod(0o600)
        before=p.stat();self.manifest[name]['original_sha256']=D.digest(b'original')
        self.install();D.restore(self.root)
        self.assertEqual(p.read_bytes(),b'original');self.assertEqual(p.stat().st_mode&0o777,0o600)
        self.assertEqual(p.stat().st_mtime_ns,before.st_mtime_ns)
    def test_target_parent_symlink_escape_rejected(self):
        outside=Path(self.tmp.name)/'outside';outside.mkdir();(self.root/'usr').symlink_to(outside)
        with self.assertRaises(ValueError):self.install()
        self.assertFalse((self.root/D.STATE).exists());self.assertEqual(list(outside.iterdir()),[])
    def test_restore_without_ledger_is_non_mutating(self):
        result=D.restore(self.root);self.assertEqual(result['verdict'],'NO_DESKTOP_LEDGER_NO_MUTATION')


class DeploymentScopeTests(unittest.TestCase):
    def test_both_owned_roles_explicitly_opt_in_bounded_observer(self):
        for name in ('hexagonrpcd-adsp-rootpd-trace.conf', 'hexagonrpcd-adsp-sensorspd-trace.conf'):
            self.assertIn('Environment=HEXAGONRPC_RETURN_TRACE=1\n', (R / name).read_text())
        self.assertEqual(H.PLAN['return_trace_frame_bytes'], 8192)
        self.assertEqual(H.PLAN['return_trace_per_process_bytes'], 524288)
        self.assertEqual(H.PLAN['unit_journal_max_bytes'], 8388608)
        self.assertEqual(H.PLAN['trace_max_bytes'], 2097152)

    def test_corrected_daemon_with_same_library_and_exact_eight_file_scope(self):
        manifest = H.read(R / 'desktop-manifest.json')
        self.assertEqual(set(manifest), D.ALLOWED)
        trace = manifest['usr/local/lib/gts9-test388/hexagonrpcd']
        self.assertEqual(trace['source'], 'out/ssc-rpc-return/build-output/stage/usr/bin/hexagonrpcd')
        self.assertEqual(trace['sha256'], H.PLAN['trace_sha256'])
        self.assertNotEqual(H.PLAN['trace_sha256'], 'e1e9faa47f77e738f34280ff9eeb2165939358b25042bafe5981517b867f86fb')
        self.assertEqual(H.PLAN['trace_library_sha256'], '1be44d2fe0c9b5ca785ef27730fba586a7f678f82f91cfbfb01613b3dad76f6e')

    def test_no_kernel_modules_charging_or_control_driver_changes(self):
        self.assertFalse(H.PACKAGE['kernel_rebuilt'])
        self.assertFalse(H.PACKAGE['modules_changed'])
        self.assertEqual(H.PACKAGE['modules'], 181)
        self.assertEqual(H.PLAN['write_partitions'], ['vendor_boot'])
        self.assertFalse(H.PLAN['PPS'])
        self.assertFalse(H.PLAN['pump_ON'])
        self.assertNotIn('rpmsg_ctrl.ko', H.PACKAGE['artifacts'])
        self.assertEqual(H.PLAN['ssc_readiness_seconds'], 60)

    def test_recovery_admission_failure_cannot_transfer_or_write(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        folder = Path(temporary.name)
        H.write(folder / 'active-preflight.json', dict(verdict='READY_FOR_ONE_CONTROLLED_BOOT', epoch=H.time.time(), boot_id=H.PLAN['before_boot_id']))
        with patch.object(H, 'R', folder), patch.object(H, 'verify_inputs'), patch.object(H, 'verify_stage'), \
             patch.object(H.p, 'Recorder', return_value=Mock(folder=folder)), \
             patch.object(H, 'snapshot'), patch.object(H.h, 'enter_recovery'), \
             patch.object(H.recovery_admission, 'admit', side_effect=ValueError('unstable TWRP')), \
             patch.object(H.recovery_admission, 'capture_fault'), patch.object(H, 'transfer') as transfer, \
             patch.object(H, 'write_partition') as write, patch.object(H, 'restore') as restore:
            with self.assertRaisesRegex(ValueError, 'unstable TWRP'): H.install()
            transfer.assert_not_called(); write.assert_not_called(); restore.assert_called_once()
            self.assertTrue((folder / 'first-failure.json').exists())


class ReturnCollectionTests(unittest.TestCase):
    def test_unit_journal_limit_stops_before_parser(self):
        rec = Mock(); rec.adb.return_value = ('x' * 10, 0)
        with patch.object(H, 'PLAN', H.PLAN | {'unit_journal_max_bytes': 9}), \
             patch.object(H.stat_evidence, 'inspect') as parser:
            with self.assertRaisesRegex(ValueError, 'journal size'):
                H.collect_runtime(rec, require_metadata=True)
            parser.assert_not_called()

    def collect(self, frames=True, contents=True):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        folder = Path(temporary.name)
        H.write(folder / 'mutation-state.json', {'boot_id': H.PLAN['before_boot_id']})
        H.write(folder / 'registry-metadata.json', {})
        H.write(folder / 'asset-manifest.json', {})
        rec = Mock(folder=folder); rec.adb.return_value = ('raw-unit-journal', 0)
        with patch.object(H, 'R', folder), \
             patch.object(H.stat_evidence, 'inspect', return_value={'complete': True}), \
             patch.object(H.return_evidence, 'inspect', return_value={'complete': frames}), \
             patch.object(H.return_evidence, 'registry_contents', return_value={'complete': contents}):
            if not frames or not contents:
                with self.assertRaisesRegex(ValueError, 'return framing/content'):
                    H.collect_runtime(rec, require_metadata=True)
            else:
                H.collect_runtime(rec, require_metadata=True)
        return folder

    def test_complete_content_recorded_without_relabeling_as_sensor_pass(self):
        folder = self.collect()
        self.assertTrue(H.read(folder / 'rpc-return-content.json')['complete'])
        self.assertFalse((folder / 'rpc-return-error.json').exists())

    def test_missing_frames_stops_preserves_successful_stat_and_return_error(self):
        folder = self.collect(frames=False)
        self.assertTrue(H.read(folder / 'rpc-stat-metadata.json')['complete'])
        self.assertFalse(H.read(folder / 'rpc-return-error.json')['complete'])

    def test_corrupt_content_stops_despite_correct_stat(self):
        folder = self.collect(contents=False)
        self.assertFalse(H.read(folder / 'rpc-return-content.json')['complete'])


if __name__ == '__main__': unittest.main()
