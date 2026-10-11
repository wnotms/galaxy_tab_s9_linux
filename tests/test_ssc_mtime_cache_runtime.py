import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'reference/boot-tests/test-401-fedora-mtime-cache'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


H = load('ssc401_host', R / 'host_flow.py')
M = load('ssc401_runtime', R / 'runtime.py')
L = load('ssc401_lifecycle', ROOT / 'userspace/sensors/ssc_sensor_first_lifecycle.py')


D = load('ssc401_overlay', R / 'desktop.py')

class RuntimeStartupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.d = json.loads((ROOT / 'reference/boot-tests/test-377-ssc-userspace-pd-mapper/runtime-discovery/boundary.txt').read_text())
        self.d['cmdline'] = H.PLAN['runtime_cmdline']
        self.plan = H.PLAN | {'boot_id': self.d['boot_id']}
        self.active = set()
        self.commands = []
        for name, key in [('usr/local/lib/gts9-test401/hexagonrpcd', 'trace_sha256'),
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
            return '/usr/bin/stdbuf -oL -eL /usr/local/lib/gts9-test401/hexagonrpcd'
        if argv[1] == 'start':
            state = json.loads(self.runner.path(M.STATE).read_text())
            self.assertEqual(state['rpc_requested'][-1], argv[-1])
            self.assertTrue(self.runner.path(M.GATE).exists())
            self.active.add(argv[-1]); return ''
        return 'active' if argv[-1] in self.active else 'inactive'

    def test_actual_runtime_starts_both_roles_sensor_first_no_mapper(self):
        self.runner.start()
        starts = [c for c in self.commands if c[1] == 'start']
        self.assertEqual(starts, [['systemctl', 'start', L.SENSOR_PD],
                                  ['systemctl', 'start', L.ROOT_PD]])

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
        self.runner.path('/usr/local/lib/gts9-test401/hexagonrpcd').write_bytes(b'changed')
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

    def test_registration_order_mismatch_stops_before_gate(self):
        self.plan['rpc_launch_order']=[L.ROOT_PD,L.SENSOR_PD]
        with self.assertRaisesRegex(ValueError,'unregistered sensor-first'):
            self.runner.start()
        self.assertFalse(self.active)
        self.assertFalse(self.runner.path(M.GATE).exists())

BOOT = '11111111-1111-4111-8111-111111111111'


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        (self.folder / 'mutation-state.json').write_text(json.dumps(dict(phase='accepted-candidate-kept-text', boot_id=BOOT.replace('-', ''))))
        (self.folder / 'runtime-packages.json').write_text('[]')
        self.rec = Mock(); self.rec.folder = self.folder / 'runtime-discovery'
        self.d = dict(boot_id=BOOT, uptime=40, failed_units=[], battery={})
        wanted = ['runtime.py','capture.py','map-socinfo.py','qrtr-native-snapshot.py',
                  'native-mapper-snapshot.py','servreg-domain-snapshot.py','servreg-state-snapshot.py','servreg-listener-snapshot.py',
                  'ssc_sensor_first_lifecycle.py','registry_mutation_evidence.py','rpc_return_evidence.py','runtime-packages.json','runtime-overrides.json']
        for name, value in dict(R=self.folder, snapshot=Mock(return_value=self.d),
                                native_gate=Mock(), transport_admit=Mock(),
                                verify_stage=Mock(return_value={n:dict(sha256='a'*64) for n in wanted}),
                                trace_inventory=Mock(), runtime=Mock(), native_mapper=Mock(),
                                qrtr=Mock(return_value=dict(services=[], boot_id=BOOT, complete=True)),
                                servreg=Mock(return_value=dict(boot_id=BOOT, complete=True)),
                                notifier=Mock(side_effect=[dict(domain_state='DOWN'),dict(domain_state='UP')]),
                                registry_snapshot=Mock(side_effect=lambda rec,boot,phase: {'phase':phase}),
                                collect_raw_runtime=Mock(return_value='raw-callbacks'),
                                collect_runtime=Mock(return_value=dict(contents={'complete':True},metadata_coverage_complete=True)), trace_collect=Mock(return_value={'provider': {'complete': True, 'SSC_publication_proved': False}}),
                                scan=Mock(return_value=dict(fault_counts={})), restore=Mock()).items():
            p = patch.object(H, name, value); p.start(); self.addCleanup(p.stop)
        def recorder(folder):
            folder.mkdir()
            return self.rec
        p = patch.object(H.p, 'Recorder', side_effect=recorder); p.start(); self.addCleanup(p.stop)
        p = patch.object(H.time, 'monotonic', side_effect=[0, 31, 32]); p.start(); self.addCleanup(p.stop)

    def test_two_queries_one_start_and_restore_without_false_acceptance(self):
        d = H.discover()
        self.assertEqual(d['before_state'], 'DOWN'); self.assertEqual(d['after_state'], 'UP')
        self.assertFalse(d['sensor_acceptance']); self.assertFalse(d['SSC_service_present'])
        self.assertEqual(d['verdict'], 'SSC_ABSENT')
        self.assertIsNone(d['accelerometer_sample'])
        self.assertEqual(H.notifier.call_count, 2)
        self.assertEqual([c.args[1] for c in H.runtime.call_args_list], ['prepare','start','deactivate'])
        H.restore.assert_called_once()
        self.assertTrue(all(c.args[2] == BOOT for c in H.runtime.call_args_list))
        self.assertFalse(any(c.args[0] == 'accelerometer' for c in self.rec.adb.call_args_list))
        H.collect_runtime.assert_called_once_with(self.rec,'raw-callbacks',{'phase':'before'},{'phase':'after'})
        self.assertEqual([c.args[2]for c in H.registry_snapshot.call_args_list],['before','after'])

    def test_snapshots_bracket_launch_and_stop_before_replay(self):
        events=[]
        H.runtime.side_effect=lambda rec,mode,boot: events.append(mode)
        H.registry_snapshot.side_effect=lambda rec,boot,phase: events.append('snapshot-'+phase) or {'phase':phase}
        H.collect_raw_runtime.side_effect=lambda *a: events.append('raw') or 'raw-callbacks'
        H.collect_runtime.side_effect=lambda *a: events.append('replay') or dict(contents={'complete':True},metadata_coverage_complete=True)
        H.discover()
        self.assertEqual(events,['prepare','snapshot-before','start','raw','deactivate','snapshot-after','replay'])

    def test_before_snapshot_failure_prevents_start_and_restores(self):
        H.registry_snapshot.side_effect=ValueError('snapshot missing')
        with self.assertRaisesRegex(ValueError,'snapshot missing'):H.discover()
        self.assertNotIn('start',[c.args[1]for c in H.runtime.call_args_list])
        H.restore.assert_called_once()

    def test_after_snapshot_failure_preserves_first_and_restores(self):
        H.registry_snapshot.side_effect=lambda rec,boot,phase: {'phase':phase} if phase=='before' else (_ for _ in ()).throw(ValueError('final missing'))
        with self.assertRaisesRegex(ValueError,'final missing'):H.discover()
        self.assertEqual([c.args[1]for c in H.runtime.call_args_list].count('start'),1)
        H.collect_runtime.assert_not_called();H.restore.assert_called_once()

    def test_ssc_publication_without_sample_is_not_sensor_acceptance(self):
        H.qrtr.return_value=dict(services=[dict(service=400)],boot_id=BOOT,complete=True)
        self.rec.adb.return_value=('',0)
        d=H.discover()
        self.assertEqual(d['verdict'],'SSC_PRESENT_NO_SAMPLE')
        self.assertFalse(d['sensor_acceptance'])
        self.assertEqual(sum(c.args[0]=='accelerometer' for c in self.rec.adb.call_args_list),1)
        H.restore.assert_called_once()

    def test_real_sample_separately_reported_without_rotation_acceptance(self):
        H.qrtr.return_value=dict(services=[dict(service=400)],boot_id=BOOT,complete=True)
        self.rec.adb.side_effect=lambda n,*a,**k: ('Accelerometer sensor measurement: X=0 Y=0 Z=9.81 m/s²',0) if n=='accelerometer' else ('',0)
        d=H.discover()
        self.assertEqual(d['verdict'],'SSC_PRESENT_WITH_SAMPLE')
        self.assertEqual(d['accelerometer_sample']['z'],9.81)
        self.assertFalse(d['physical_rotation_tested']);self.assertFalse(d['sensor_acceptance'])
        H.restore.assert_called_once()

    def test_initial_unknown_stops_before_rpc_and_restores(self):
        H.notifier.side_effect = ValueError('unknown')
        with self.assertRaises(ValueError): H.discover()
        self.assertNotIn('start', [c.args[1] for c in H.runtime.call_args_list])
        H.restore.assert_called_once()
        self.assertTrue((self.folder / 'first-runtime-failure.json').exists())
        self.assertEqual(H.notifier.call_count, 1)

    def test_second_unknown_no_retry_and_restores(self):
        H.notifier.side_effect = [dict(domain_state='UNINIT'), ValueError('unknown')]
        with self.assertRaises(ValueError): H.discover()
        self.assertEqual(H.notifier.call_count, 2)
        self.assertEqual([c.args[1] for c in H.runtime.call_args_list].count('start'), 1)
        H.restore.assert_called_once()

    def test_journal_collection_failure_restores(self):
        H.collect_runtime.side_effect = ValueError('journal')
        with self.assertRaises(ValueError): H.discover()
        H.restore.assert_called_once()

    def test_unknown_rescue_marks_manual_recovery_without_another_start(self):
        H.notifier.side_effect = ValueError('query')
        H.restore.side_effect = ValueError('ADB gone')
        with self.assertRaises(ValueError): H.discover()
        d = json.loads((self.folder / 'recovery-required.json').read_text())
        self.assertTrue(d['manual_TWRP_required'])
        H.restore.assert_called_once()

    def test_completed_attempt_cannot_be_replayed(self):
        self.rec.folder.mkdir()
        with self.assertRaises(ValueError): H.discover()
        H.runtime.assert_not_called(); H.notifier.assert_not_called(); H.restore.assert_not_called()

    def test_new_failed_unit_during_observation_stops_and_restores(self):
        with patch.object(H.time, 'monotonic', side_effect=[0, 0]), \
                patch.object(H, 'snapshot', side_effect=[self.d, dict(self.d, failed_units=['fault.service'])]):
            with self.assertRaises(ValueError): H.discover()
        self.assertEqual(H.notifier.call_count, 1)
        H.restore.assert_called_once()

    def test_failed_rpc_unit_stops_without_restart(self):
        self.rec.adb.side_effect = lambda name, *a, **k: ('active\nfailed', 0) if name.startswith('ssc-units') else ('', 0)
        with patch.object(H.time, 'monotonic', side_effect=[0, 0]):
            with self.assertRaises(ValueError): H.discover()
        self.assertEqual([c.args[1] for c in H.runtime.call_args_list].count('start'), 1)
        H.restore.assert_called_once()


    def test_first_provider_collection_failure_stops_without_recollection(self):
        H.trace_collect.side_effect = ValueError('provider collection')
        with self.assertRaises(ValueError): H.discover()
        self.assertEqual(H.trace_collect.call_count, 1)
        self.assertEqual([c.args[1] for c in H.runtime.call_args_list].count('start'), 1)
        H.restore.assert_called_once()



class FirmwareRecoveryWrapperTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        self.rec = Mock(folder=Path(t.name))
        self.calls = []
        def adb(name, command, **kwargs):
            self.calls.append((name, command))
            if name == 'firmware-terminal-ledger':
                return json.dumps(dict(phase='restored', files={str(i): {} for i in range(52)})), 0
            if name in ('firmware-install', 'firmware-restore', 'firmware-cleanup'):
                verdict={'firmware-install':'COMPLETE_FEDORA_PAIR_INSTALLED_OFFLINE',
                         'firmware-restore':'EXACT_ORIGINAL_PAIR_RESTORED',
                         'firmware-cleanup':'RESTORED_OWNED_BACKUPS_REMOVED'}[name]
                return json.dumps(dict(verdict=verdict,firmware_files=52)), 0
            if name.endswith('-ledger'):
                return json.dumps(dict(phase='installed',files={})), 0
            return '',0
        self.rec.adb.side_effect = adb
        self.actual_adb = adb

    def test_install_verifies_tools_before_readonly_proc_and_chroot(self):
        H.firmware(self.rec,'install')
        names=[n for n,_ in self.calls]
        self.assertLess(names.index('firmware-install-tool-hashes'), names.index('firmware-install-proc'))
        self.assertLess(names.index('firmware-install-proc'), names.index('firmware-install'))
        commands=dict(self.calls)
        self.assertIn('mount -o remount,bind,ro',commands['firmware-install-proc'])
        self.assertIn('/tmp/gts9-test401-fw/proc',commands['firmware-install'])
        self.assertIn('chroot /mnt/debian /usr/bin/python3',commands['firmware-install'])
        self.assertIn('umount /mnt/debian/tmp/gts9-test401-fw/proc',commands['firmware-install-scratch-cleanup'])
        self.assertIn('.owner',commands['firmware-install-scratch-cleanup'])
        self.assertFalse(any('reboot' in cmd or 'remoteproc' in cmd for _,cmd in self.calls))

    def test_bind_failure_skips_firmware_execution_but_cleans_owned_scratch(self):
        def fail(name,*args,**kwargs):
            if name=='firmware-install-proc':raise ValueError('bind failed')
            return self.actual_adb(name,*args,**kwargs)
        self.rec.adb.side_effect=fail
        with self.assertRaisesRegex(ValueError,'bind failed'):H.firmware(self.rec,'install')
        names=[n for n,_ in self.calls]
        self.assertNotIn('firmware-install',names)
        self.assertIn('firmware-install-scratch-cleanup',names)

    def test_first_tool_failure_preserved_when_cleanup_also_fails(self):
        def fail(name,*args,**kwargs):
            if name=='firmware-install':raise ValueError('first transaction fault')
            if name.endswith('scratch-cleanup'):raise TimeoutError('cleanup transport timeout')
            return self.actual_adb(name,*args,**kwargs)
        self.rec.adb.side_effect=fail
        with self.assertRaisesRegex(ValueError,'first transaction fault'):H.firmware(self.rec,'install')
        self.assertEqual(json.loads((self.rec.folder/'firmware-install-first-failure.json').read_text())['error'],'first transaction fault')
        self.assertTrue((self.rec.folder/'firmware-install-scratch-failure.json').exists())

    def test_cleanup_failure_stops_successful_install(self):
        def fail(name,*args,**kwargs):
            if name.endswith('scratch-cleanup'):return '',1
            return self.actual_adb(name,*args,**kwargs)
        self.rec.adb.side_effect=fail
        with self.assertRaisesRegex(ValueError,'cleanup incomplete'):H.firmware(self.rec,'install')
        self.assertTrue(json.loads((self.rec.folder/'firmware-install-scratch-failure.json').read_text())['root_unmount_forbidden'])

    def test_terminal_ledger_archived_before_backup_cleanup(self):
        H.firmware(self.rec,'cleanup')
        names=[n for n,_ in self.calls]
        self.assertLess(names.index('firmware-terminal-ledger'),names.index('firmware-cleanup'))
        self.assertTrue((self.rec.folder/'firmware-terminal-ledger.json').exists())

    def test_unqualified_terminal_ledger_blocks_backup_cleanup(self):
        def fail(name,*args,**kwargs):
            if name=='firmware-terminal-ledger':return json.dumps(dict(phase='installed',files={})),0
            return self.actual_adb(name,*args,**kwargs)
        self.rec.adb.side_effect=fail
        with self.assertRaisesRegex(ValueError,'terminal firmware restoration'):H.firmware(self.rec,'cleanup')
        self.assertFalse(any(n=='firmware-cleanup' for n,_ in self.calls))

    def test_unknown_operation_has_no_device_calls(self):
        with self.assertRaises(ValueError):H.firmware(self.rec,'enable')
        self.rec.adb.assert_not_called()

    def test_firmware_before_asset_install_and_after_asset_restore(self):
        # Supplement actual filesystem integration in the qualified transaction
        # tests with the registered orchestration's explicit mutation ordering.
        source=(R/'host_flow.py').read_text()
        install=source[source.index('def install():'):source.index('def stage():')]
        restore=source[source.index('def restore('):source.index('def install():')]
        self.assertLess(install.index("firmware(rec, 'install')"),install.index("assets(rec, 'install')"))
        self.assertLess(restore.index("assets(rec, 'restore')"),restore.index("firmware(rec, 'restore')"))
        self.assertLess(restore.index("firmware(rec, 'restore')"),restore.index("firmware(rec, 'cleanup')"))
        self.assertLess(restore.index("firmware(rec, 'cleanup')"),restore.index('h.clear_unmount(rec)'))


