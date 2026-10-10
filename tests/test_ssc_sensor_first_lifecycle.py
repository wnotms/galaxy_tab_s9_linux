import copy
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ssc_sensor_first_lifecycle', ROOT / 'userspace/sensors/ssc_sensor_first_lifecycle.py')
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.state = dict(phase='prepared-inactive', started=False)
        self.saved = []
        self.running = set()
        self.starts = []
        self.invoke = Mock(side_effect=self.command)

    def persist(self, state):
        self.saved.append(copy.deepcopy(state))

    def command(self, argv, **kwargs):
        unit = argv[-1]
        if argv[1] == 'start':
            # At every externally visible start, the exact unit intent is
            # durable. This covers lost replies as well as successful starts.
            self.assertTrue(self.saved[-1]['started'])
            self.assertEqual(self.saved[-1]['rpc_requested'][-1], unit)
            self.starts.append(unit)
            self.running.add(unit)
            return ''
        return 'active' if unit in self.running else 'inactive'

    def start(self):
        return S.start_rpc(self.invoke, self.state, self.persist)

    def test_both_named_domains_started_once_sensor_first(self):
        self.start()
        self.assertEqual(self.starts, [S.SENSOR_PD, S.ROOT_PD])
        self.assertEqual(self.state['rpc_active'], list(S.RPC_UNITS))
        self.assertFalse(any('--no-block' in c.args[0] for c in self.invoke.call_args_list))

    def test_no_proxy_mapper_or_remoteproc_start(self):
        self.start()
        self.assertEqual(set(self.starts), set(S.RPC_UNITS))

    def test_second_start_refused(self):
        self.start()
        with self.assertRaises(ValueError):
            self.start()
        self.assertEqual(len(self.starts), 2)

    def test_unknown_or_preexisting_active_state_refuses_mutation(self):
        for status in ('active', 'activating', 'failed', 'unknown', ''):
            with self.subTest(status=status):
                invoke = Mock(return_value=status)
                with self.assertRaises(ValueError):
                    S.start_rpc(invoke, self.state, self.persist)
                self.assertFalse(self.state['started'])
                self.assertFalse(self.saved)

    def test_sensor_timeout_consumes_attempt_root_not_started(self):
        def timeout(argv, **kwargs):
            if argv[1] == 'start':
                raise subprocess.TimeoutExpired(argv, 15)
            return self.command(argv, **kwargs)
        self.invoke.side_effect = timeout
        with self.assertRaises(subprocess.TimeoutExpired):
            self.start()
        self.assertEqual(self.saved[-1]['rpc_requested'], [S.SENSOR_PD])
        self.assertTrue(self.state['started'])
        with self.assertRaises(ValueError):
            self.start()

    def test_sensor_skipped_or_exited_never_inferred_as_handoff(self):
        self.invoke.side_effect = lambda *a, **kw: 'inactive'
        with self.assertRaisesRegex(ValueError, 'did not activate'):
            self.start()
        self.assertEqual(self.state['rpc_requested'], [S.SENSOR_PD])
        self.assertEqual(self.state['rpc_active'], [])

    def test_root_failure_preserves_sensor_intent_for_cleanup(self):
        def fail(argv, **kwargs):
            if argv[1] == 'start' and argv[-1] == S.ROOT_PD:
                raise ValueError('I2C/transport fault')
            return self.command(argv, **kwargs)
        self.invoke.side_effect = fail
        with self.assertRaises(ValueError):
            self.start()
        self.assertEqual(self.state['rpc_requested'], list(S.RPC_UNITS))
        self.assertEqual(self.state['rpc_active'], [S.SENSOR_PD])

    def test_persist_failure_sends_no_start(self):
        persist = Mock(side_effect=OSError('disk full'))
        with self.assertRaises(OSError):
            S.start_rpc(self.invoke, self.state, persist)
        self.assertFalse(self.starts)


if __name__ == '__main__':
    unittest.main()
