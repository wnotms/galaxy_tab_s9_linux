"""Run combined admission against the real recorder's no-overwrite behavior."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import sm5440_device_completion as completion
from test_sm5440_passive_admission import FakeRecorder, BOOT, CONFIG, NOTES


class SavingRecorder(FakeRecorder):
    def __init__(self, folder):
        folder.mkdir(parents=True)
        super().__init__(folder)
        self.ready = {'ready': True, 'samples': 1, 'delayed_readiness': False}
        self.services = f'active\nactive\n{BOOT}\n'

    def save(self, name, output):
        text, status = output
        # Exercise Recorder.command itself, not a mock of its overwrite check.
        with patch.object(completion.p.subprocess, 'run', return_value=
                          subprocess.CompletedProcess(['mock'], status,
                                                      text.encode(), b'')):
            return completion.p.Recorder.command(self, name, ['mock'], required=False)

    def adb(self, name, script, *args, **kwargs):
        output = ((self.services, 0) if name == 'dcc-services' else
                  super().adb(name, script, *args, **kwargs))
        return self.save(name, output)

    def ps(self, name, script, *args, **kwargs):
        return self.save(name, super().ps(name, script, *args, **kwargs))

    def ssh(self, name, script, *args, **kwargs):
        return self.save(name, super().ssh(name, script, *args, **kwargs))

    def command(self, name, *args, **kwargs):
        return self.save(name, super().command(name, *args, **kwargs))


class DeviceCompletionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.parent = Path(tmp.name) / 'endpoint'
        self.parent.mkdir()
        self.folder = self.parent / 'device-completion'
        self.change = lambda recorder: None
        self.recorder = None

    def factory(self, folder):
        self.recorder = SavingRecorder(folder)
        self.change(self.recorder)
        return self.recorder

    def capture(self):
        return completion.capture_completion(self.folder, BOOT, CONFIG, NOTES,
                                             recorder_factory=self.factory)

    def test_parent_journal_and_original_stop_preserved_combined_admission(self):
        (self.parent / 'kernel-json.txt').write_bytes(b'original Wi-Fi journal\r\n')
        (self.parent / 'summary.json').write_text('{"verdict":"STOP host collision"}')
        before = {p.name: p.read_bytes() for p in self.parent.iterdir()}
        result = self.capture()
        self.assertEqual(result['verdict'], 'DEVICE_ACCEPTANCE_COMPLETED')
        for name, content in before.items():
            self.assertEqual((self.parent / name).read_bytes(), content)
        self.assertTrue((self.folder / 'kernel-json.txt').exists())
        self.assertEqual(self.recorder.calls.count(('ssh', 'ncm-auth')), 1)
        self.assertFalse(result['physical_recovery_time_measured'])

    def test_existing_directory_refused_before_any_command(self):
        self.folder.mkdir(); (self.folder / 'marker').write_text('retain')
        with self.assertRaisesRegex(completion.p.CaptureError, 'already exists'):
            self.capture()
        self.assertIsNone(self.recorder)
        self.assertEqual((self.folder / 'marker').read_text(), 'retain')

    def test_real_recorder_still_rejects_duplicate_filename(self):
        rec = self.factory(self.folder)
        rec.adb('kernel-json', '')
        original = (self.folder / 'kernel-json.txt').read_bytes()
        with self.assertRaisesRegex(completion.p.CaptureError, 'refusing to overwrite'):
            rec.adb('kernel-json', '')
        self.assertEqual((self.folder / 'kernel-json.txt').read_bytes(), original)

    def test_identity_change_stops_before_transport(self):
        self.change = lambda r: setattr(r, 'config', 'c' * 64)
        with self.assertRaisesRegex(completion.p.CaptureError, 'identity'):
            self.capture()
        self.assertFalse(any(method == 'ssh' for method, _ in self.recorder.calls))
        self.assertEqual(json.loads((self.folder / 'summary.json').read_text())['verdict'],
                         'DEVICE_CHECK_INCOMPLETE')

    def test_fault_keeps_evidence_and_never_claims_completion(self):
        self.change = lambda r: setattr(r, 'health', 'Unspecified failure')
        with self.assertRaisesRegex(completion.p.CaptureError, 'passive health'):
            self.capture()
        self.assertTrue((self.folder / 'health.txt').exists())
        self.assertNotIn('rollback_required', json.loads((self.folder / 'summary.json').read_text()))

    def test_code43_stops_and_preserves_device_evidence(self):
        self.change = lambda r: setattr(r, 'code43', [{'ConfigManagerErrorCode': 43}])
        with self.assertRaisesRegex(completion.p.CaptureError, 'Code43'):
            self.capture()
        self.assertTrue((self.folder / 'ncm-failure-device.txt').exists())

    def test_ncm_auth_failure_is_not_retried(self):
        self.change = lambda r: setattr(r, 'auth_status', 255)
        with self.assertRaisesRegex(completion.p.CaptureError, 'no retry'):
            self.capture()
        self.assertEqual(self.recorder.calls.count(('ssh', 'ncm-auth')), 1)

    def test_inactive_service_and_reboot_do_not_pass(self):
        for services in (f'active\ninactive\n{BOOT}\n', f'active\nactive\n{"2"*32}\n'):
            with tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp) / 'completion'
                def factory(path):
                    r = SavingRecorder(path); r.services = services; return r
                with self.assertRaises(completion.p.CaptureError):
                    completion.capture_completion(folder, BOOT, CONFIG, NOTES,
                                                  recorder_factory=factory)
                self.assertEqual(json.loads((folder / 'summary.json').read_text())['verdict'],
                                 'DEVICE_CHECK_INCOMPLETE')


if __name__ == '__main__':
    unittest.main()
