"""Fresh registration: hardware gates precede host wait; no auth retry."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import sm5440_ready_admission as ready
import sm5440_passive_admission as admission
from test_sm5440_passive_admission import FakeRecorder, BOOT, CONFIG, NOTES


class ReadyAdmissionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.r = ready.ReadyRecorder(Path(temp.name))
        self.fake = FakeRecorder(self.r.folder)
        self.wait_calls = 0
        self.auth_argv = []
        self.wait_error = None
        for method in ('adb', 'ps'):
            context = patch.object(ready.p.Recorder, method, side_effect=getattr(self.fake, method))
            context.start(); self.addCleanup(context.stop)
        context = patch.object(ready.p.Recorder, 'command', side_effect=self.command)
        context.start(); self.addCleanup(context.stop)
        context = patch.object(ready.n, 'wait_ready', side_effect=self.wait)
        context.start(); self.addCleanup(context.stop)

    def wait(self, recorder, window):
        self.wait_calls += 1
        self.assertEqual(window, 30)
        self.assertEqual(self.fake.calls[:3], [('adb', 'identity'), ('adb', 'kernel-json'), ('adb', 'health')])
        if self.wait_error:
            raise ready.p.CaptureError(self.wait_error)
        (recorder.folder / 'readiness-01-windows.txt').write_text(json.dumps({'code43': []}))
        return {'samples': 1, 'source_ipv4': '169.254.74.160', 'delayed_readiness': False}

    def command(self, name, argv, *args, **kwargs):
        if name == 'ncm-auth':
            self.auth_argv.append(argv)
            return self.fake.ssh(name, '')
        return self.fake.command(name, argv, *args, **kwargs)

    def run_gate(self):
        return admission.admit(self.r, BOOT, CONFIG, NOTES)

    def test_hardware_first_and_bound_auth_once(self):
        result = self.run_gate()
        self.assertEqual(self.wait_calls, 1)
        self.assertEqual(len(self.auth_argv), 1)
        argv = self.auth_argv[0]
        self.assertEqual(argv[argv.index('-b') + 1], '169.254.74.160')
        self.assertIn('ConnectionAttempts=1', argv)
        self.assertEqual(result['transport_retries'], 0)

    def test_hardware_fault_never_waits_or_connects(self):
        self.fake.health = 'Unspecified failure'
        with self.assertRaises(ready.p.CaptureError): self.run_gate()
        self.assertEqual(self.wait_calls, 0)
        self.assertFalse(self.auth_argv)

    def test_pending_hardware_never_waits_or_connects(self):
        self.fake.health = 'Unknown'
        with self.assertRaises(ready.p.CaptureError): self.run_gate()
        self.assertEqual(self.wait_calls, 0)

    def test_code43_readiness_failure_keeps_device_evidence(self):
        self.wait_error = 'Code43'
        with self.assertRaisesRegex(ready.p.CaptureError, 'Code43'): self.run_gate()
        self.assertFalse(self.auth_argv)
        self.assertEqual(self.fake.calls[-1], ('adb', 'ncm-failure-device'))

    def test_first_auth_failure_never_retries(self):
        self.fake.auth_status = 255
        with self.assertRaisesRegex(ready.p.CaptureError, 'no retry'): self.run_gate()
        self.assertEqual(len(self.auth_argv), 1)
        self.assertEqual(self.fake.calls[-1], ('adb', 'ncm-failure-device'))

    def test_ssh_before_readiness_refused(self):
        with self.assertRaisesRegex(ready.p.CaptureError, 'SSH refused'):
            self.r.ssh('premature', 'uptime')
        self.assertFalse(self.auth_argv)


if __name__ == '__main__':
    unittest.main()
