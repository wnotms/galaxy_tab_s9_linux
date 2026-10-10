import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import test_smp2p_trace as fixture

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'reference/boot-tests/test-400-fedora-adsp-comparison'
OLD = ROOT / 'reference/boot-tests/test-399-ssc-smp2p-provider'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


H = load('ssc400_host', R / 'host_flow.py')
D = load('ssc400_overlay', R / 'desktop.py')


class ProviderRegistrationTests(unittest.TestCase):
    def test_only_complete_firmware_changes_over399_hardware_pair(self):
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
        self.assertEqual(build['firmware_files'], 52)
        self.assertEqual(build['changed_files'], 19)
        self.assertTrue(build['PD_maps_unchanged'])
        self.assertFalse(build['kernel_build_executed'])
        for name in ('dtb', 'bootconfig'):
            self.assertEqual(H.sha(ROOT/'out/boot-bundle-ssc-fedora-adsp/source'/name),
                             H.sha(ROOT/'out/boot-bundle-ssc-fedora-adsp/verify'/name))
        self.assertEqual(H.PLAN['runtime_cmdline'], json.loads((OLD/'registration.json').read_text())['runtime_cmdline'])

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
        self.assertIn('/gts9-test400/glink_trace.py collect --boot-id ' + self.boot, argv)
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
        self.assertIn('/tmp/gts9-test400-fw/proc',commands['firmware-install'])
        self.assertIn('chroot /mnt/debian /usr/bin/python3',commands['firmware-install'])
        self.assertIn('umount /mnt/debian/tmp/gts9-test400-fw/proc',commands['firmware-install-scratch-cleanup'])
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


class FirmwareCallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=(OLD/'runtime-discovery/discovery-unit-journal.txt').read_text()
        cls.boot=json.loads((OLD/'runtime-discovery/summary.json').read_text())['boot_id']
        cls.metadata=json.loads((R/'registry-metadata.json').read_text())
        cls.manifest=json.loads((R/'asset-manifest.json').read_text())

    def inspect(self,raw=None):
        return H.callback_evidence.inspect(self.raw if raw is None else raw,self.boot,self.metadata,self.manifest)

    def test_actual399_callbacks_remain_valid_with_exact_full_coverage(self):
        d=self.inspect()
        self.assertTrue(d['complete']); self.assertFalse(d['old_call_totals_required'])
        self.assertEqual(d['metadata']['observed_entries'],35)
        self.assertTrue(d['registry_coverage_complete'])
        self.assertEqual(d['status']['observed_known_missing_count'],1)
        self.assertFalse(d['SSC_publication_proved'])

    def test_unrequested_metadata_stays_visible_without_old_total_gate(self):
        rows=[json.loads(s) for s in self.raw.splitlines()]
        rows=[r for r in rows if not r.get('MESSAGE','').startswith('stat(')]
        d=self.inspect('\n'.join(json.dumps(r) for r in rows))
        self.assertTrue(d['complete'])
        self.assertFalse(d['metadata_coverage_complete'])
        self.assertEqual(d['metadata']['observed_entries'],0)
        self.assertEqual(len(d['metadata']['missing']),35)

    def test_actual_metadata_mismatch_is_still_a_failure(self):
        rows=[json.loads(s) for s in self.raw.splitlines()]
        paths={e['virtual_path'] for e in self.metadata['entries']}
        pattern=H.callback_evidence.stat.STAT
        row=next(r for r in rows if (m:=pattern.fullmatch(r.get('MESSAGE',''))) and m[1] in paths)
        row['MESSAGE']=row['MESSAGE'].replace('mtime=','mtime=1')
        d=self.inspect('\n'.join(json.dumps(r) for r in rows))
        self.assertFalse(d['complete']); self.assertTrue(d['metadata']['faults'])

    def test_wrong_boot_and_empty_journal_fail(self):
        with self.assertRaises(ValueError):
            H.callback_evidence.inspect(self.raw,'00000000-0000-0000-0000-000000000001',self.metadata,self.manifest)
        with self.assertRaises(ValueError):self.inspect('')

    def test_unknown_failed_callback_cannot_be_waived(self):
        frames=self.inspect()['returned']
        frames=copy.deepcopy(frames)
        call=next(c for s in frames['streams'] for c in s['calls'] if c.get('response_to'))
        call['status']=99
        self.assertFalse(H.callback_evidence.statuses(frames)['complete'])

    def test_missing_callback_not_exercised_is_not_claimed_as_passed(self):
        frames=copy.deepcopy(self.inspect()['returned'])
        for s in frames['streams']:s['calls']=[c for c in s['calls'] if not c['status']]
        d=H.callback_evidence.statuses(frames)
        self.assertTrue(d['complete']);self.assertFalse(d['known_missing_exercised'])

    def test_observed_known_missing_call_must_still_acknowledge_status69(self):
        frames=copy.deepcopy(self.inspect()['returned'])
        call=next(c for s in frames['streams'] for c in s['calls'] if c['status']==69)
        call['status']=0
        self.assertFalse(H.callback_evidence.statuses(frames)['complete'])

    def test_unregistered_config_stat_stops_without_false_coverage(self):
        rows=[json.loads(s) for s in self.raw.splitlines()]
        pattern=H.callback_evidence.stat.STAT
        row=next(r for r in rows if (m:=pattern.fullmatch(r.get('MESSAGE',''))) and m[1].startswith('/vendor/etc/sensors/config/'))
        row['MESSAGE']='stat(/vendor/etc/sensors/config/unregistered.json) -> size=1 mtime=1.000000000'
        d=self.inspect('\n'.join(json.dumps(r) for r in rows))
        self.assertFalse(d['complete']);self.assertFalse(d['metadata_coverage_complete'])

    def test_actual_content_corruption_stops_even_if_other_coverage_missing(self):
        c=H.callback_evidence
        real=c.returned.registry_contents
        def fail(*args):
            d=real(*args);d['faults'].append(dict(reason='injected mismatched bytes'));d['complete']=False;return d
        with patch.object(c.returned,'registry_contents',side_effect=fail):
            self.assertFalse(self.inspect()['complete'])


if __name__ == '__main__':
    unittest.main()
