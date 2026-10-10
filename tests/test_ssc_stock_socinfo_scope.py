import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_stock_socinfo_compare import native, packet, RECOVERY_BOOT, NATIVE_BOOT

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('stock394_scope',
    ROOT/'reference/boot-tests/test-394-stock-socinfo/host_flow.py')
F = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(F)


class StockSocinfoScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.before = {'boot_id': NATIVE_BOOT, 'native_socinfo': native()}
        (self.folder/'preflight').mkdir()
        (self.folder/'preflight/summary.json').write_text(json.dumps(
            dict(epoch=F.time.time(), snapshot=self.before)))
        self.calls = []
        self.observe_error = None
        self.addCleanup(setattr, F.p, 'SERIAL', 'gts9wifi-0001')

    def fake_recorder(self, folder):
        scope = self
        class Rec:
            def __init__(self):
                self.folder = folder
                folder.mkdir(exist_ok=True)
            def adb(self, name, command, **kwargs):
                scope.calls.append(name)
                if name == 'stock-socinfo':
                    if scope.observe_error:
                        raise ValueError(scope.observe_error)
                    return packet(), 0
                return '', 0
        return Rec()

    def execute(self, *, return_error=None, recovery_boot=RECOVERY_BOOT):
        def returned(*args):
            self.calls.append('normal-return')
            if return_error:
                raise ValueError(return_error)
            return dict(verdict='UNCHANGED370_DESKTOP_RETURNED', boot_id='cccccccc-dddd-eeee-ffff-000000000000')
        with patch.object(F, 'R', self.folder), patch.object(F, 'verify'), \
                patch.object(F, 'snapshot', return_value=self.before), \
                patch.object(F.p, 'Recorder', side_effect=self.fake_recorder), \
                patch.object(F.BASE.h.recovery, 'wait_recovery', return_value={}), \
                patch.object(F.ADMISSION, 'admit', return_value={'samples':[{'boot_id':recovery_boot}]}), \
                patch.object(F, 'return_to_baseline', side_effect=returned):
            return F.run()

    def test_registered_sequence_one_read_and_normal_return(self):
        result = self.execute()
        self.assertEqual(self.calls, ['helper-check', 'BCB-request', 'ordinary-reboot',
            'recovery-dmesg', 'recovery-persistent', 'stock-socinfo', 'normal-return'])
        self.assertEqual(result['observation']['verdict'], 'STOCK_SOCINFO_EXACT_MATCH')
        self.assertFalse(result['sensor_acceptance'])
        for name in ('kernel_rebuilt','image_write','registry_write','DSP_started','PPS','pump_ON'):
            self.assertFalse(result[name])
        self.assertFalse(json.loads((self.folder/'execution-state.json').read_text())['return_required'])

    def test_read_failure_stops_without_replay_and_returns(self):
        self.observe_error = 'missing stock sysfs'
        with self.assertRaisesRegex(ValueError, 'first failure'):
            self.execute()
        self.assertEqual(self.calls.count('stock-socinfo'), 1)
        self.assertEqual(self.calls.count('normal-return'), 1)
        result = json.loads((self.folder/'summary.json').read_text())
        self.assertEqual(result['observation_error'], self.observe_error)
        self.assertIsNone(result['return_error'])

    def test_return_failure_leaves_explicit_manual_recovery_state(self):
        with self.assertRaisesRegex(ValueError, 'first failure'):
            self.execute(return_error='rescue lost')
        self.assertEqual(self.calls.count('normal-return'), 1)
        self.assertTrue(json.loads((self.folder/'execution-state.json').read_text())['return_required'])
        self.assertEqual(json.loads((self.folder/'summary.json').read_text())['return_error'], 'rescue lost')

    def test_unchanged_boot_never_captures_or_blindly_returns(self):
        with self.assertRaisesRegex(ValueError, 'unchanged'):
            self.execute(recovery_boot=NATIVE_BOOT)
        self.assertNotIn('stock-socinfo', self.calls)
        self.assertNotIn('normal-return', self.calls)
        self.assertTrue(json.loads((self.folder/'execution/entry-error.json').read_text())['no_blind_reboot'])

    def test_old_preflight_consumes_no_physical_command(self):
        target = self.folder/'preflight/summary.json'
        value = json.loads(target.read_text()); value['epoch'] = 0
        target.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.execute()
        self.assertEqual(self.calls, [])

    def test_consumed_attempt_cannot_run_again(self):
        (self.folder/'execution').mkdir()
        with self.assertRaisesRegex(ValueError, 'consumed'):
            self.execute()
        self.assertEqual(self.calls, [])

    def test_unpushed_registration_stops_before_device(self):
        with patch.object(F.subprocess, 'check_output', side_effect=[
                'test\n', '111\n', '222\n']):
            # Check actual verify with a minimal owned manifest, no shell/device.
            (self.folder/'INPUTS.json').write_text('{}')
            with patch.object(F, 'R', self.folder), self.assertRaisesRegex(ValueError, 'pushed'):
                F.verify(pushed=True)


if __name__ == '__main__':
    unittest.main()
