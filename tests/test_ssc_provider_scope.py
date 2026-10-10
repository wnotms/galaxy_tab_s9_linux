import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import test_smp2p_trace as fixture

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'reference/boot-tests/test-399-ssc-smp2p-provider'
OLD = ROOT / 'reference/boot-tests/test-398-readdir-initialization'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


H = load('ssc399_host', R / 'host_flow.py')
D = load('ssc399_overlay', R / 'desktop.py')


class ProviderRegistrationTests(unittest.TestCase):
    def test_only_vendor_trace_enrollment_changes_over398_hardware_pair(self):
        old = json.loads((OLD / 'PACKAGE.json').read_text())
        before, after = old['candidate_partitions'], H.PACKAGE['candidate_partitions']
        self.assertNotEqual(before['vendor_boot'], after['vendor_boot'])
        self.assertEqual({k: v for k, v in before.items() if k != 'vendor_boot'},
                         {k: v for k, v in after.items() if k != 'vendor_boot'})
        self.assertEqual(old['baseline_partitions'], H.PACKAGE['baseline_partitions'])
        self.assertEqual(old['artifacts']['hexagonrpcd-trace'], H.PACKAGE['artifacts']['hexagonrpcd-trace'])
        self.assertEqual(H.PACKAGE['modules'], 181)
        self.assertEqual(H.PACKAGE['write_partitions'], ['vendor_boot'])
        for key in ['kernel_rebuilt', 'config_changed', 'dtb_changed', 'modules_changed']:
            self.assertFalse(H.PACKAGE[key])
        for key in ['PPS', 'pump_ON', 'charging_limits_changed']:
            self.assertFalse(H.PLAN[key])

    def test_exact_new_boot_args_and_unchanged_remaining_cmdline(self):
        old = json.loads((OLD / 'registration.json').read_text())
        self.assertEqual(H.PLAN['trace_boot_args'], fixture.g.BOOT_ARGS)
        self.assertEqual(H.PLAN['runtime_cmdline'],
                         old['runtime_cmdline'].replace(old['trace_boot_args'], fixture.g.BOOT_ARGS))
        self.assertEqual(H.PLAN['baseline_runtime_cmdline'], old['baseline_runtime_cmdline'])
        self.assertEqual(H.PLAN['trace_instance'], fixture.g.INSTANCE)
        self.assertEqual(H.PLAN['provider_event_filter'], 'none')
        self.assertEqual(H.PLAN['provider_adsp_device'], 'smp2p-adsp')
        self.assertEqual(H.PLAN['ssc_readiness_seconds'], 30)
        self.assertEqual(H.PLAN['notifier_max_cycles'], 2)
        self.assertEqual(H.PLAN['rpc_launch_order'], old['rpc_launch_order'])
        self.assertEqual(H.PLAN['trace_library_sha256'], old['trace_library_sha256'])

    def test_actual_image_headers_components_and_footer_qualified(self):
        build = json.loads((R / 'BUILD.json').read_text())
        self.assertEqual(H.sha(ROOT / H.PACKAGE['artifacts']['vendor_boot.img']['path']), build['candidate_vendor_sha256'])
        self.assertEqual(build['bytes'], 100663296)
        self.assertTrue(all(row['unchanged'] for row in build['components'].values()))
        for name, row in build['components'].items():
            self.assertEqual(H.sha(ROOT / 'out/boot-bundle-ssc-provider399/source' / name), row['sha256'])
            self.assertEqual(H.sha(ROOT / 'out/boot-bundle-ssc-provider399/verify' / name), row['sha256'])
        self.assertEqual(build['cmdline_after'], build['cmdline_before'].replace(
            json.loads((OLD / 'registration.json').read_text())['trace_boot_args'], fixture.g.BOOT_ARGS))

    def test_real_nine_file_transaction_restores_without_touching_other_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'root'
            incoming = Path(folder) / 'incoming'
            (root / 'etc').mkdir(parents=True)
            incoming.mkdir()
            (root / 'etc/machine-id').write_text(D.MACHINE + '\n')
            untouched = root / 'etc/untouched'
            untouched.write_text('original')
            manifest = json.loads((R / 'desktop-manifest.json').read_text())
            self.assertEqual(set(manifest), D.ALLOWED)
            self.assertEqual(len(manifest), 9)
            for row in manifest.values():
                (incoming / row['incoming']).write_bytes((ROOT / row['source']).read_bytes())
            self.assertEqual(D.install(root, incoming, manifest)['files'], 9)
            D.restore(root)
            self.assertTrue(all(not (root / name).exists() for name in manifest))
            self.assertEqual(untouched.read_text(), 'original')

    def test_partial_nine_file_install_is_reversible(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'root'
            incoming = Path(folder) / 'incoming'
            (root / 'etc').mkdir(parents=True)
            incoming.mkdir()
            (root / 'etc/machine-id').write_text(D.MACHINE)
            manifest = json.loads((R / 'desktop-manifest.json').read_text())
            for row in manifest.values():
                (incoming / row['incoming']).write_bytes((ROOT / row['source']).read_bytes())
            atomic = D.atomic
            calls = []

            def injected(path, *args, **kwargs):
                calls.append(path)
                if len(calls) == 5:
                    raise OSError('mock copy fault')
                return atomic(path, *args, **kwargs)

            with patch.object(D, 'atomic', side_effect=injected), self.assertRaises(OSError):
                D.install(root, incoming, manifest)
            D.restore(root)
            self.assertTrue(all(not (root / name).exists() for name in manifest))

    def test_altered_observer_source_blocks_host_verification(self):
        with patch.object(H, 'sha', return_value='0' * 64), self.assertRaises(ValueError):
            H.verify_inputs()


class HostProviderCollectionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.rec = Mock(folder=Path(temp.name))
        self.d = fixture.appended(fixture.OPEN)
        self.boot = self.d['boot_id']
        self.d['provider'] = H.provider_evidence.analyze(self.d, self.boot)

    def collect(self, d=None, status=0):
        self.rec.adb.return_value = (json.dumps(self.d if d is None else d), status)
        return H.trace_collect(self.rec, self.boot)

    def test_real_parser_rechecks_host_and_retains_raw_evidence(self):
        result = self.collect()
        self.assertTrue(result['provider']['adsp_negotiation_observed'])
        self.assertEqual((self.rec.folder / 'glink-complete.trace').read_text(), self.d['trace'])
        self.assertEqual(json.loads((self.rec.folder / 'glink-complete.json').read_text()), self.d)
        argv = self.rec.adb.call_args.args[1]
        self.assertIn('/gts9-test399/glink_trace.py collect --boot-id ' + self.boot, argv)
        self.assertFalse(self.rec.adb.call_args.kwargs['required'])

    def test_missing_or_forged_provider_summary_rejected(self):
        for mutate in ['missing', 'forged']:
            d = copy.deepcopy(self.d)
            if mutate == 'missing':
                del d['provider']
            else:
                d['provider']['adsp_negotiation_observed'] = False
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                self.collect(d)
            self.assertTrue((self.rec.folder / 'glink-complete.json').exists())

    def test_nonzero_status_or_incomplete_device_trace_saved_before_stop(self):
        with self.assertRaises(ValueError):
            self.collect(status=1)
        self.assertTrue((self.rec.folder / 'glink-complete.trace').exists())
        with self.assertRaises(ValueError):
            self.collect(self.d | {'complete': False})
        self.assertFalse(json.loads((self.rec.folder / 'glink-complete.json').read_text())['complete'])

    def test_header_loss_cannot_be_waived_by_device_boolean(self):
        d = fixture.recalculate(self.d | {'trace': self.d['trace'].replace('18/18', '17/18')})
        with self.assertRaises(ValueError):
            self.collect(d)

    def test_actual398_no_provider_event_is_not_relabelled_as_sensor_pass(self):
        d = json.loads(fixture.REAL.read_text())
        d['provider'] = H.provider_evidence.analyze(d, self.boot)
        result = self.collect(d)
        self.assertFalse(result['provider']['adsp_negotiation_observed'])
        self.assertFalse(result['provider']['SSC_publication_proved'])


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
                  'ssc_sensor_first_lifecycle.py','runtime-packages.json','runtime-overrides.json']
        for name, value in dict(R=self.folder, snapshot=Mock(return_value=self.d),
                                native_gate=Mock(), transport_admit=Mock(),
                                verify_stage=Mock(return_value={n:dict(sha256='a'*64) for n in wanted}),
                                trace_inventory=Mock(), runtime=Mock(), native_mapper=Mock(),
                                qrtr=Mock(return_value=dict(services=[], boot_id=BOOT, complete=True)),
                                servreg=Mock(return_value=dict(boot_id=BOOT, complete=True)),
                                notifier=Mock(side_effect=[dict(domain_state='DOWN'),dict(domain_state='UP')]),
                                collect_runtime=Mock(), trace_collect=Mock(return_value={'provider': {'complete': True, 'SSC_publication_proved': False}}),
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
        H.collect_runtime.assert_called_once_with(self.rec, 'discovery-', require_metadata=True)

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

if __name__ == '__main__':
    unittest.main()
