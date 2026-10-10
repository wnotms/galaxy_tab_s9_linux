import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'reference/boot-tests/test-399-ssc-smp2p-provider'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


H = load('ssc399_host', R / 'host_flow.py')
M = load('ssc399_runtime', R / 'runtime.py')
L = load('ssc399_lifecycle', ROOT / 'userspace/sensors/ssc_sensor_first_lifecycle.py')


D = load('ssc399_overlay', R / 'desktop.py')

class RuntimeStartupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.d = json.loads((ROOT / 'reference/boot-tests/test-377-ssc-userspace-pd-mapper/runtime-discovery/boundary.txt').read_text())
        self.d['cmdline'] = H.PLAN['runtime_cmdline']
        self.plan = H.PLAN | {'boot_id': self.d['boot_id']}
        self.active = set()
        self.commands = []
        for name, key in [('usr/local/lib/gts9-test399/hexagonrpcd', 'trace_sha256'),
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
            return '/usr/bin/stdbuf -oL -eL /usr/local/lib/gts9-test399/hexagonrpcd'
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
        self.runner.path('/usr/local/lib/gts9-test399/hexagonrpcd').write_bytes(b'changed')
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
