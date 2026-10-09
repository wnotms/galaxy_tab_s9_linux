import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'reference/boot-tests/test-383-ssc-bounded-boot-history'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


H = load('ssc383_host', R / 'host_flow.py')
M = load('ssc383_runtime', R / 'runtime.py')
L = load('ssc383_lifecycle', ROOT / 'userspace/sensors/ssc_lifecycle.py')


class RuntimeStartupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.d = json.loads((ROOT / 'reference/boot-tests/test-377-ssc-userspace-pd-mapper/runtime-discovery/boundary.txt').read_text())
        self.d['cmdline'] = H.PLAN['runtime_cmdline']
        self.plan = H.PLAN | {'boot_id': self.d['boot_id']}
        self.active = set()
        self.commands = []
        for name, key in [('usr/local/lib/gts9-test383/hexagonrpcd', 'trace_sha256'),
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
            return '/usr/bin/stdbuf -oL -eL /usr/local/lib/gts9-test383/hexagonrpcd'
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
        self.runner.path('/usr/local/lib/gts9-test383/hexagonrpcd').write_bytes(b'changed')
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


class DomainGateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.rec = Mock(folder=self.folder)
        self.boot = '11111111-1111-1111-1111-111111111111'
        self.inventory = dict(boot_id=self.boot, complete=True, services=[dict(service=64, instance=257, node=7, port=16385)])
        self.response = dict(boot_id=self.boot, complete=True, sensor_domain_present=True)
        self.rec.adb.side_effect = [('', 0), (json.dumps(self.response), 0)]

    def test_one_verified_endpoint_then_one_read_only_query(self):
        H.servreg(self.rec, self.boot, self.inventory)
        command = self.rec.adb.call_args_list[-1].args[1]
        self.assertIn('--node 7 --port 16385 --layout linux-7.2 --seconds 2', command)
        self.assertNotIn('systemctl', command)

    def test_duplicate_mapper_stops_without_query(self):
        self.inventory['services'].append(dict(service=64, instance=257, node=7, port=16388))
        with self.assertRaises(ValueError): H.servreg(self.rec, self.boot, self.inventory)
        self.rec.adb.assert_not_called()

    def test_missing_mapper_stops_without_query(self):
        self.inventory['services'] = []
        with self.assertRaises(ValueError): H.servreg(self.rec, self.boot, self.inventory)
        self.rec.adb.assert_not_called()

    def test_incomplete_or_wrong_boot_inventory_stops(self):
        for field, value in [('complete', False), ('boot_id', '22222222-2222-2222-2222-222222222222')]:
            with self.assertRaises(ValueError): H.servreg(self.rec, self.boot, self.inventory | {field: value})
        self.rec.adb.assert_not_called()

    def test_partial_negative_or_stale_answer_not_accepted(self):
        for field, value in [('complete', False), ('sensor_domain_present', False), ('boot_id', '22222222-2222-2222-2222-222222222222')]:
            self.rec.adb.side_effect = [('', 0), (json.dumps(self.response | {field: value}), 0)]
            with self.assertRaises(ValueError): H.servreg(self.rec, self.boot, self.inventory)

    def test_scoped_inputs_no_new_kernel_charging_or_mapper_package(self):
        self.assertEqual(H.PACKAGE['write_partitions'], ['vendor_boot'])
        self.assertEqual(H.PLAN['candidate_config_sha256'], H.PLAN['baseline_config_sha256'])
        self.assertFalse(H.PLAN['PPS']); self.assertFalse(H.PLAN['pump_ON'])
        packages = H.read(R / 'runtime-packages.json')
        self.assertNotIn('pd-mapper', [p['package'] for p in packages])
        self.assertEqual(H.PLAN['servreg_query_seconds'], 2)


class MetadataCollectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.rec = Mock(folder=self.folder)
        self.boot = '11111111-1111-1111-1111-111111111111'
        self.path = '/vendor/etc/sensors/config/test.json'
        self.reference = {'entries': [dict(virtual_path=self.path, archive_size=3,
            archive_mtime_seconds=1640995200, cache_mtime_seconds=1640995200, mtime_matches=True)]}
        self.row = dict(_BOOT_ID=self.boot, _SYSTEMD_UNIT=H.stat_evidence.UNIT,
                        __MONOTONIC_TIMESTAMP='2000000',
                        MESSAGE='stat(' + self.path + ') -> size=3 mtime=1640995200.000000000')

    def collect(self, required=True):
        self.rec.adb.side_effect = [(json.dumps(self.row), 0), ('state', 0)]
        def read(path):
            return self.reference if path.name == 'registry-metadata.json' else {'boot_id': self.boot}
        with patch.object(H, 'read', side_effect=read):
            H.collect_runtime(self.rec, require_metadata=required)

    def test_current_sensor_metadata_persisted_before_unit_snapshot(self):
        self.collect()
        evidence = json.loads((self.folder / 'rpc-stat-metadata.json').read_text())
        self.assertTrue(evidence['complete'])
        self.assertEqual(self.rec.adb.call_count, 2)

    def test_missing_metadata_stops_and_keeps_first_evidence(self):
        self.row['MESSAGE'] = 'stat(' + self.path + ')'
        with self.assertRaises(ValueError): self.collect()
        self.assertFalse(json.loads((self.folder / 'rpc-stat-metadata.json').read_text())['complete'])
        self.assertTrue((self.folder / 'rpc-stat-metadata-error.json').exists())
        self.assertEqual(self.rec.adb.call_count, 1)

    def test_other_boot_cannot_be_accepted(self):
        self.row['_BOOT_ID'] = '22222222-2222-2222-2222-222222222222'
        with self.assertRaises(ValueError): self.collect()
        self.assertTrue((self.folder / 'rpc-stat-metadata-error.json').exists())

    def test_failure_collection_retains_incomplete_result_for_analysis(self):
        self.row['MESSAGE'] = 'Starting...'
        self.collect(required=False)
        self.assertFalse(json.loads((self.folder / 'rpc-stat-metadata.json').read_text())['complete'])
        self.assertEqual(self.rec.adb.call_count, 2)





class EnrollmentTests(unittest.TestCase):
    def test_enrollment_is_exact_accepted_boot_not_a_future_waiver(self):
        enrollment = H.read(R / 'ENROLLMENT.json')
        self.assertFalse(enrollment['future_error_waiver'])
        self.assertEqual(enrollment['previous_hardware_attempts'], 1)
        self.assertEqual(enrollment['boot_id'], H.PLAN['before_boot_id'])
        self.assertEqual(enrollment['new_priority3_rows'], 0)
        previous = H.read(ROOT / 'reference/boot-tests/test-379-ssc-rpc-stat/summary.json')
        self.assertEqual(previous['verdict'], 'STOP_PREFLIGHT_NEW_EP0_DIAGNOSTIC_NOT_DEPLOYED')
        enrolled = H.PLAN['baseline_observation']
        self.assertEqual(H.sha(ROOT / enrolled['path']), enrolled['sha256'])

    def test_repeated_ep0_after_enrollment_still_stops(self):
        original = (ROOT / H.PLAN['baseline_observation']['path']).read_text()
        rows = [json.loads(x) for x in original.splitlines()]
        ep0 = rows[-1] | {'PRIORITY': '3', 'MESSAGE': 'dwc3-qcom a600000.usb: request deadbeef was not queued to ep0out'}
        added = ep0 | {'__CURSOR': 'new-independent-error-cursor'}
        with tempfile.TemporaryDirectory() as temporary:
            rec = Mock(folder=Path(temporary))
            rec.adb.return_value = (original + json.dumps(added) + '\n', 0)
            with self.assertRaisesRegex(ValueError, 'new kernel error'):
                H.preflight_scan(rec, {'boot_id': H.PLAN['before_boot_id']})

    def test_amended_voltage_host_runtime_and_charger_identity(self):
        d = json.loads((ROOT / 'reference/boot-tests/test-377-ssc-userspace-pd-mapper/runtime-discovery/boundary.txt').read_text())
        d['cmdline'] = H.PLAN['runtime_cmdline']
        plan = H.PLAN | {'boot_id': d['boot_id']}
        for value in ('4440000', '4447000', '4450000'):
            d['battery']['POWER_SUPPLY_VOLTAGE_NOW'] = value
            H.identity(d, 'candidate')
            M.validate(d, plan)
        for value in ('4450001', '3399999'):
            d['battery']['POWER_SUPPLY_VOLTAGE_NOW'] = value
            with self.assertRaises(ValueError): H.identity(d, 'candidate')
            with self.assertRaises(ValueError): M.validate(d, plan)
        d['battery']['POWER_SUPPLY_VOLTAGE_NOW'] = '4447000'
        for field, value in [('POWER_SUPPLY_HEALTH', 'Unknown'), ('POWER_SUPPLY_TEMP', '420'),
                             ('POWER_SUPPLY_PRESENT', '0'), ('POWER_SUPPLY_VOLTAGE_MAX_DESIGN', '4450000')]:
            saved = d['battery'][field]; d['battery'][field] = value
            with self.assertRaises(ValueError): H.identity(d, 'candidate')
            with self.assertRaises(ValueError): M.validate(d, plan)
            d['battery'][field] = saved


class TraceGateTests(unittest.TestCase):
    def test_baseline_and_candidate_cmdlines_are_distinct(self):
        d = json.loads((ROOT / 'reference/boot-tests/test-377-ssc-userspace-pd-mapper/runtime-discovery/boundary.txt').read_text())
        for phase, key in [('candidate', 'runtime_cmdline'), ('baseline', 'baseline_runtime_cmdline')]:
            d['cmdline'] = H.PLAN[key]
            H.identity(d, phase)
            d['cmdline'] = H.PLAN['baseline_runtime_cmdline' if phase == 'candidate' else 'runtime_cmdline']
            with self.assertRaises(ValueError): H.identity(d, phase)

    def test_loss_or_wrong_boot_cannot_complete_collection(self):
        boot = '11111111-1111-1111-1111-111111111111'
        valid = dict(boot_id=boot, trace_stopped=True, complete=True, trace='raw event')
        with tempfile.TemporaryDirectory() as tmp:
            rec = Mock(folder=Path(tmp))
            rec.adb.return_value = (json.dumps(valid), 0)
            H.trace_collect(rec, boot)
            self.assertEqual((Path(tmp) / 'glink-complete.trace').read_text(), 'raw event')
            for field, value in [('complete', False), ('trace_stopped', False), ('boot_id', '22222222-2222-2222-2222-222222222222')]:
                rec.adb.return_value = (json.dumps(valid | {field: value}), 0)
                with self.assertRaises(ValueError): H.trace_collect(rec, boot, 'invalid')
                self.assertFalse((Path(tmp) / 'invalid.trace').exists())

    def test_exact_boot_trace_budget_and_owned_overlay(self):
        glink = load('glink_scope_helper', ROOT / 'userspace/sensors/glink_trace_382.py')
        self.assertEqual(H.PLAN['trace_boot_args'], glink.BOOT_ARGS)
        self.assertEqual(H.PLAN['trace_boot_deadline_seconds'], glink.BOOT_DEADLINE)
        self.assertEqual(H.PLAN['trace_max_bytes'], glink.MAX_BYTES)
        desktop = load('glink_overlay', R / 'desktop.py')
        manifest = H.read(R / 'desktop-manifest.json')
        self.assertEqual(set(manifest), set(desktop.ALLOWED))
        self.assertEqual(len(manifest), 8)
        for row in manifest.values(): self.assertEqual(H.sha(ROOT / row['source']), row['sha256'])


class OwnedOverlayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'root'; self.incoming = Path(self.tmp.name) / 'incoming'
        (self.root / 'etc').mkdir(parents=True); self.incoming.mkdir()
        self.desktop = load('owned381_overlay_test', R / 'desktop.py')
        (self.root / 'etc/machine-id').write_text(self.desktop.MACHINE)
        self.manifest = H.read(R / 'desktop-manifest.json')
        for row in self.manifest.values():
            (self.incoming / row['incoming']).write_bytes((ROOT / row['source']).read_bytes())
        self.unrelated = self.root / 'etc/systemd/system/gts9-usb-typec-lifecycle.service'
        self.unrelated.parent.mkdir(parents=True); self.unrelated.write_text('keep')

    def test_all_eight_owned_files_install_and_restore_without_touching_usb(self):
        self.assertEqual(self.desktop.install(self.root, self.incoming, self.manifest)['files'], 8)
        self.desktop.restore(self.root)
        for name in self.manifest: self.assertFalse((self.root / name).exists())
        self.assertEqual(self.unrelated.read_text(), 'keep')

    def test_partial_copy_restorable_and_changed_owned_content_not_removed(self):
        original = self.desktop.atomic
        def fault(path, *args, **kwargs):
            if path.name == 'glink_trace.py': raise OSError('injected disk failure')
            return original(path, *args, **kwargs)
        with patch.object(self.desktop, 'atomic', side_effect=fault):
            with self.assertRaises(OSError): self.desktop.install(self.root, self.incoming, self.manifest)
        self.desktop.restore(self.root)
        self.desktop.install(self.root, self.incoming, self.manifest)
        owned = self.root / 'usr/local/lib/gts9-test383/glink_trace.py'; owned.write_text('unknown')
        with self.assertRaises(ValueError): self.desktop.restore(self.root)
        self.assertTrue(owned.exists()); self.assertEqual(self.unrelated.read_text(), 'keep')


class ADBAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.d = json.loads((ROOT / 'reference/boot-tests/test-377-ssc-userspace-pd-mapper/runtime-discovery/boundary.txt').read_text())
        self.d['cmdline'] = H.PLAN['runtime_cmdline']
        self.d['network'] = '14: usb0 inet 169.254.42.1/16'
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.rec = Mock(folder=Path(self.tmp.name))
        self.rec.host_adb.return_value = ('device\r\n', 0)
        self.reply = '\n'.join([H.PLAN['machine_id'], self.d['boot_id'], '0', self.d['boot_id']])+'\n'
        self.rec.adb.return_value = (self.reply, 0)

    def test_no_wifi_admits_only_actual_adb_identity_no_ssh_claim(self):
        result = H.transport_admit(self.rec, 'transport', self.d)
        self.assertTrue(result['ADB']); self.assertFalse(result['SSH_tested'])
        self.assertFalse(result['host_NCM_tested']); self.assertIsNone(result['authenticated_WiFi'])
        self.assertEqual(result['wifi_ipv4'], [])
        self.rec.command.assert_not_called(); self.rec.ps.assert_not_called()

    def test_offline_transport_blocks_before_shell(self):
        self.rec.host_adb.return_value = ('offline', 0)
        with self.assertRaises(ValueError): H.transport_admit(self.rec, 'transport', self.d)
        self.rec.adb.assert_not_called()

    def test_wrong_machine_nonroot_or_new_boot_cannot_admit(self):
        for replacement in [self.reply.replace(H.PLAN['machine_id'], '0'*32),
                            self.reply.replace('\n0\n', '\n1000\n'),
                            self.reply.rsplit('\n', 2)[0]+'\n22222222-2222-2222-2222-222222222222\n']:
            self.rec.adb.return_value = (replacement, 0)
            with self.assertRaises(ValueError): H.transport_admit(self.rec, 'transport', self.d)

    def test_adb_exception_preserved(self):
        self.rec.adb.side_effect = TimeoutError('ADB shell timeout')
        with self.assertRaises(TimeoutError): H.transport_admit(self.rec, 'transport', self.d)

    def test_boot_readiness_does_not_wait_for_wifi(self):
        self.rec.adb.return_value = (self.d['boot_id']+'\nactive\nactive\nactive\n14: usb0 inet 169.254.42.1/16\n', 0)
        H.wait_debian(self.rec)
        self.assertEqual(self.rec.adb.call_count, 1)


class FirstCandidateEvidenceTests(unittest.TestCase):
    def test_first_readable_failed_candidate_recorded_for_historical_collection(self):
        d=json.loads((ROOT/'reference/boot-tests/test-377-ssc-userspace-pd-mapper/runtime-discovery/boundary.txt').read_text())
        d['cmdline']=H.PLAN['runtime_cmdline'];d['failed_units']='owned watcher failed'
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);H.write(folder/'mutation-state.json',dict(phase='installed-awaiting-one-boot',rollback_required=True))
            rec=Mock();rec.adb.return_value=(json.dumps(d),0)
            with patch.object(H,'R',folder):
                with self.assertRaises(ValueError):H.snapshot(rec,'boundary','candidate')
            self.assertEqual(H.read(folder/'mutation-state.json')['boot_id'],d['boot_id'])

    def test_later_wrong_boot_does_not_replace_first_failed_boot(self):
        d=json.loads((ROOT/'reference/boot-tests/test-377-ssc-userspace-pd-mapper/runtime-discovery/boundary.txt').read_text())
        first=d['boot_id'];d['cmdline']=H.PLAN['runtime_cmdline'];d['boot_id']='22222222-2222-2222-2222-222222222222'
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);H.write(folder/'mutation-state.json',dict(boot_id=first,rollback_required=True))
            rec=Mock();rec.adb.return_value=(json.dumps(d),0)
            with patch.object(H,'R',folder):
                with self.assertRaises(ValueError):H.snapshot(rec,'boundary','candidate',first)
            self.assertEqual(H.read(folder/'mutation-state.json')['boot_id'],first)


class BoundedBootHistoryTests(unittest.TestCase):
    def listing(self, ids):
        return 'IDX BOOT ID FIRST ENTRY LAST ENTRY\n' + ''.join(str(i-len(ids)+1)+' '+b+' Tue 2026-10-10 01:00:00 CST Tue 2026-10-10 01:01:00 CST\n' for i,b in enumerate(ids))

    def verdict(self, before, after):
        return H.h.g.evidence.attribute('a'*32,'b'*32,self.listing(before),self.listing(after))

    def test_bounded_listing_keeps_boot_id_change_and_unique_successor(self):
        self.assertEqual(self.verdict(['0'*32,'1'*32,'2'*32,'3'*32,'a'*32],['1'*32,'2'*32,'3'*32,'a'*32,'b'*32]),'attributed')

    def test_unexplained_boot_still_stops(self):
        self.assertEqual(self.verdict(['a'*32],['a'*32,'c'*32,'b'*32]),'unexpected_boot_or_history')

    def test_too_many_boots_old_id_absent_stops(self):
        self.assertEqual(self.verdict(['a'*32],['0'*32,'1'*32,'2'*32,'3'*32,'b'*32]),'previous_boot_missing')

    def test_no_reboot_and_empty_or_duplicate_history_cannot_pass(self):
        e=H.h.g.evidence
        self.assertEqual(e.attribute('a'*32,'a'*32,self.listing(['a'*32]),self.listing(['a'*32])),'boot_id_unchanged')
        for listing in ['',self.listing(['a'*32,'a'*32])]:
            with self.assertRaises(ValueError):e.attribute('a'*32,'b'*32,self.listing(['a'*32]),listing)

    def test_query_is_device_bounded_and_qualified_vendor_observer_reused(self):
        self.assertEqual(H.PLAN['boot_history_command'],'timeout 8 journalctl --list-boots -n 5 --no-pager')
        old=H.read(ROOT/'reference/boot-tests/test-382-ssc-glink-geometry/PACKAGE.json')
        self.assertEqual(H.PACKAGE['artifacts'],old['artifacts'])
        self.assertEqual(H.PLAN['trace_instance'],'gts9_test382')
        self.assertEqual(H.PLAN['ssc_readiness_seconds'],60)


if __name__ == '__main__':
    unittest.main()
