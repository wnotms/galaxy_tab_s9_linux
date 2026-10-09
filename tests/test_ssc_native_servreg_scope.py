import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'reference/boot-tests/test-378-ssc-native-servreg'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


H = load('ssc378_host', R / 'host_flow.py')
M = load('ssc378_runtime', R / 'runtime.py')
L = load('ssc378_lifecycle', ROOT / 'userspace/sensors/ssc_lifecycle.py')


class RuntimeStartupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.d = json.loads((ROOT / 'reference/boot-tests/test-377-ssc-userspace-pd-mapper/runtime-discovery/boundary.txt').read_text())
        self.plan = H.PLAN | {'boot_id': self.d['boot_id']}
        self.active = set()
        self.commands = []
        for name, key in [('usr/local/lib/gts9-test378/hexagonrpcd', 'trace_sha256'),
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
            return '/usr/bin/stdbuf -oL -eL /usr/local/lib/gts9-test378/hexagonrpcd'
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
        self.runner.path('/usr/local/lib/gts9-test378/hexagonrpcd').write_bytes(b'changed')
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


if __name__ == '__main__':
    unittest.main()
