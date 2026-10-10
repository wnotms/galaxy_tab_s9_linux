import importlib.util
import contextlib
import io
import json
from pathlib import Path
import tempfile
import shlex
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'reference/boot-tests/test-393-standard-pdr-listener'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


H = load('ssc393_host', R / 'host_flow.py')
D = load('ssc393_overlay', R / 'desktop.py')
BOOT = '11111111-1111-4111-8111-111111111111'


class RegistrationTests(unittest.TestCase):
    def test_actual_capture_runtime_identity_matches_normalized_stored_uuid(self):
        runtime = load('ssc393_real_runtime', R / 'runtime.py')
        captured = json.loads((R.parent / 'test-391-sensor-pd-state/candidate-acceptance/current-state.txt').read_text())
        stored = captured['boot_id'].replace('-', '')
        # Reproduce Test391 first gate with the real candidate capture.
        with self.assertRaisesRegex(ValueError, 'identity'):
            runtime.validate(captured, H.PLAN | {'boot_id': stored})
        runtime.validate(captured, H.PLAN | {'boot_id': str(H.UUID(stored))})
        with self.assertRaises(ValueError):
            runtime.validate(captured, H.PLAN | {'boot_id': BOOT})

    def test_new_observable_boundary_and_no_hardware_change(self):
        self.assertEqual(H.PLAN['notifier_register_enable'], 1)
        self.assertEqual(H.PLAN['notifier_unregister_enable'], 0)
        self.assertEqual(H.PLAN['notifier_max_cycles'], 2)
        self.assertEqual(H.PLAN['notifier_register_seconds'], 2)
        self.assertEqual(H.PLAN['notifier_cleanup_seconds'], 2)
        self.assertEqual(H.PLAN['ssc_readiness_seconds'], 30)
        self.assertFalse(H.PLAN['PPS']); self.assertFalse(H.PLAN['pump_ON'])
        self.assertFalse(H.PACKAGE['kernel_rebuilt']); self.assertFalse(H.PACKAGE['modules_changed'])
        self.assertEqual(H.PACKAGE['modules'], 181)
        old = json.loads((R.parent / 'test-390-ssc-missing-file-status/PACKAGE.json').read_text())
        for key in ('artifacts', 'baseline_partitions', 'candidate_partitions'):
            self.assertEqual(H.PACKAGE[key], old[key])

    def test_real_renamed_overlay_transaction_restores_all_eight(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'root'; incoming = Path(folder) / 'in'
            (root / 'etc').mkdir(parents=True); incoming.mkdir()
            (root / 'etc/machine-id').write_text(D.MACHINE + '\n')
            manifest = json.loads((R / 'desktop-manifest.json').read_text())
            self.assertEqual(set(manifest), D.ALLOWED)
            self.assertEqual(len(manifest), 8)
            for row in manifest.values():
                (incoming / row['incoming']).write_bytes((ROOT / row['source']).read_bytes())
            D.install(root, incoming, manifest)
            D.restore(root)
            self.assertTrue(all(not (root / name).exists() for name in manifest))


class NotifierTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.rec = Mock(); self.rec.folder = Path(self.tmp.name)
        self.state = dict(boot_id=BOOT, complete=True, domain_state='UP',
                          registered_acknowledged=True, unregister_acknowledged=True, socket_closed=True, listener_registered=False, DSP_started=False)
        self.rec.adb.side_effect = lambda name, *args, **kwargs: (json.dumps(self.state), 0)

    def test_raw_json_retained_and_standard_listener_cli(self):
        d = H.notifier(self.rec, 'state', BOOT, {'fresh': 1}, {'fresh': 2})
        self.assertEqual(d['domain_state'], 'UP')
        self.assertEqual(json.loads((self.rec.folder / 'state.json').read_text()), self.state)
        argv = self.rec.adb.call_args_list[-1].args[1]
        self.assertIn('servreg-listener-snapshot.py', argv)
        self.assertNotIn('--seconds', argv)
        self.assertEqual(self.rec.adb.call_args_list[-1].kwargs['timeout'], 8)
        self.assertNotIn('enable=1', argv)

    def test_missing_state_error_or_changed_boot_stops(self):
        for changes in ({'complete': False}, {'domain_state': 'LOCATOR_ERROR'},
                        {'boot_id': '22222222-2222-4222-8222-222222222222'},
                        {'registered_acknowledged': False}, {'unregister_acknowledged': False}, {'socket_closed': False}, {'listener_registered': True}, {'DSP_started': True}):
            old = self.state.copy(); self.state.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                H.notifier(self.rec, 'state', BOOT, {}, {})
            self.state = old

    def test_real_helper_cli_accepts_actual_host_generated_argv(self):
        listener = load('ssc393_listener_cli', ROOT / 'userspace/sensors/servreg-listener-snapshot.py')
        inv = {'boot_id': BOOT, 'complete': True, 'services': []}
        dom = {'boot_id': BOOT, 'complete': True, 'domains': []}
        def adb(name, command, **kwargs):
            argv = shlex.split(command)
            if name.endswith('-inputs'):
                self.assertEqual(argv[:2], ['python3', '-c'])
                exec(compile(argv[2], '<owned-input-writer>', 'exec'), {})
                return '', 0
            self.assertTrue(argv[1].endswith('servreg-listener-snapshot.py'))
            with patch.object(sys, 'argv', [argv[1], *argv[2:]]), \
                    patch.object(listener, 'query', return_value=self.state) as query, \
                    contextlib.redirect_stdout(io.StringIO()) as stdout:
                status = listener.main()
                query.assert_called_once_with(inv, dom, expected_boot=BOOT)
            return stdout.getvalue(), status
        self.rec.adb.side_effect = adb
        with patch.object(H, 'TMP', str(self.rec.folder)):
            self.assertEqual(H.notifier(self.rec, 'state', BOOT, inv, dom), self.state)


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
                  'ssc_lifecycle.py','runtime-packages.json','runtime-overrides.json']
        for name, value in dict(R=self.folder, snapshot=Mock(return_value=self.d),
                                native_gate=Mock(), transport_admit=Mock(),
                                verify_stage=Mock(return_value={n:dict(sha256='a'*64) for n in wanted}),
                                trace_inventory=Mock(), runtime=Mock(), native_mapper=Mock(),
                                qrtr=Mock(return_value=dict(services=[], boot_id=BOOT, complete=True)),
                                servreg=Mock(return_value=dict(boot_id=BOOT, complete=True)),
                                notifier=Mock(side_effect=[dict(domain_state='DOWN'),dict(domain_state='UP')]),
                                collect_runtime=Mock(), trace_collect=Mock(),
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
        self.assertIsNone(d['accelerometer_sample'])
        self.assertEqual(H.notifier.call_count, 2)
        self.assertEqual([c.args[1] for c in H.runtime.call_args_list], ['prepare','start','deactivate'])
        H.restore.assert_called_once()
        self.assertTrue(all(c.args[2] == BOOT for c in H.runtime.call_args_list))
        self.assertFalse(any(c.args[0] == 'accelerometer' for c in self.rec.adb.call_args_list))
        H.collect_runtime.assert_called_once_with(self.rec, 'discovery-', require_metadata=True)

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


if __name__ == '__main__':
    unittest.main()
