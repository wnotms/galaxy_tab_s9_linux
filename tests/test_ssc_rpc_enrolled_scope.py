import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'reference/boot-tests/test-380-ssc-rpc-stat-enrolled'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


H = load('ssc380_host', R / 'host_flow.py')
M = load('ssc380_runtime', R / 'runtime.py')
L = load('ssc380_lifecycle', ROOT / 'userspace/sensors/ssc_lifecycle.py')


class RuntimeStartupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.d = json.loads((ROOT / 'reference/boot-tests/test-377-ssc-userspace-pd-mapper/runtime-discovery/boundary.txt').read_text())
        self.plan = H.PLAN | {'boot_id': self.d['boot_id']}
        self.active = set()
        self.commands = []
        for name, key in [('usr/local/lib/gts9-test380/hexagonrpcd', 'trace_sha256'),
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
            return '/usr/bin/stdbuf -oL -eL /usr/local/lib/gts9-test380/hexagonrpcd'
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
        self.runner.path('/usr/local/lib/gts9-test380/hexagonrpcd').write_bytes(b'changed')
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
    def test_enrollment_is_exact_failed_preflight_not_a_future_waiver(self):
        enrollment = H.read(R / 'ENROLLMENT.json')
        self.assertFalse(enrollment['future_error_waiver'])
        self.assertEqual(enrollment['previous_hardware_attempts'], 0)
        previous = H.read(ROOT / 'reference/boot-tests/test-379-ssc-rpc-stat/summary.json')
        self.assertEqual(previous['verdict'], 'STOP_PREFLIGHT_NEW_EP0_DIAGNOSTIC_NOT_DEPLOYED')
        enrolled = H.PLAN['baseline_observation']
        self.assertEqual(H.sha(ROOT / enrolled['path']), enrolled['sha256'])

    def test_repeated_ep0_after_enrollment_still_stops(self):
        original = (ROOT / H.PLAN['baseline_observation']['path']).read_text()
        rows = [json.loads(x) for x in original.splitlines()]
        ep0 = next(x for x in reversed(rows) if 'was not queued to ep0out' in x['MESSAGE'])
        added = ep0 | {'__CURSOR': 'new-independent-error-cursor'}
        with tempfile.TemporaryDirectory() as temporary:
            rec = Mock(folder=Path(temporary))
            rec.adb.return_value = (original + json.dumps(added) + '\n', 0)
            with self.assertRaisesRegex(ValueError, 'new kernel error'):
                H.preflight_scan(rec, {'boot_id': H.PLAN['before_boot_id']})

    def test_amended_voltage_host_runtime_and_charger_identity(self):
        d = json.loads((ROOT / 'reference/boot-tests/test-377-ssc-userspace-pd-mapper/runtime-discovery/boundary.txt').read_text())
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


if __name__ == '__main__':
    unittest.main()
