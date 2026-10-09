import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'userspace/sensors/registry_read_evidence.py'
spec = importlib.util.spec_from_file_location('registry_read_evidence', SCRIPT)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
BOOT = '11111111-1111-1111-1111-111111111111'
LEAF = 'lsm6dso_0.accel.config'


class RegistryReadEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {m.PHYSICAL + LEAF: dict(bytes=600, sha256='a' * 64),
                         m.PHYSICAL + 'sensors_registry': dict(bytes=0, sha256=m.sha(b''))}
        self.messages = ['openat($ADSP_LIBRARY_PATH, ' + m.VIRTUAL + LEAF + ') -> 3',
                         'read(3, 512) -> 512', 'read(3, 512) -> 88', 'close(3)']

    def rows(self, messages=None):
        return [dict(_BOOT_ID=BOOT.replace('-', ''), _PID='19', _SYSTEMD_UNIT=m.UNIT,
                     __MONOTONIC_TIMESTAMP=str(100 + i), MESSAGE=msg)
                for i, msg in enumerate(self.messages if messages is None else messages)]

    def inspect(self, messages=None, rows=None):
        return m.inspect('\n'.join(json.dumps(row) for row in
                         (self.rows(messages) if rows is None else rows)), BOOT, self.manifest)

    def test_complete_lengths_do_not_prove_contents_or_sensor_success(self):
        result = self.inspect()
        self.assertTrue(result['complete'])
        self.assertEqual((result['returned_bytes'], result['read_calls']), (600, 2))
        self.assertEqual(result['empty_members'], [m.VIRTUAL + 'sensors_registry'])
        for name in ('payload_contents_verified', 'DSP_parsing_proved',
                     'electrical_sensor_response_proved', 'SSC_publication_proved', 'device_operations'):
            self.assertFalse(result[name])

    def test_partial_excess_or_unclosed_reads_fail(self):
        for messages in [self.messages[:2] + ['close(3)'], self.messages[:-1],
                         self.messages[:2] + ['read(3, 512) -> 90', 'close(3)']]:
            with self.subTest(messages=messages): self.assertFalse(self.inspect(messages)['complete'])

    def test_reopens_cannot_add_partial_reads_into_a_complete_file(self):
        partial = [self.messages[0], 'read(3, 512) -> 300', 'close(3)']
        self.assertFalse(self.inspect(partial + partial)['complete'])
        self.assertFalse(self.inspect(partial + self.messages)['complete'])

    def test_fd_reuse_after_close_is_separate(self):
        self.assertTrue(self.inspect(self.messages + self.messages)['complete'])
        self.assertFalse(self.inspect(self.messages[:-1] + self.messages)['complete'])

    def test_missing_nonempty_group_not_hidden_by_empty_marker(self):
        self.manifest[m.PHYSICAL + 'gyro'] = dict(bytes=9, sha256='b' * 64)
        self.assertEqual(self.inspect()['missing'], [m.VIRTUAL + 'gyro'])
        self.assertFalse(self.inspect()['complete'])

    def test_read_without_open_or_return_beyond_request_fails(self):
        for messages in [self.messages[1:], [self.messages[0], 'read(3, 12) -> 600', 'close(3)']]:
            self.assertFalse(self.inspect(messages)['complete'])

    def test_seek_write_and_io_errors_cannot_be_hidden_by_complete_reads(self):
        for event in ['fseek(3, 0, 0)', 'write(3, 12) -> 12', 'read(3, 512) -> -1',
                      'Could not read file: Input/output error', 'Could not close: Bad file descriptor',
                      'Could not open ' + m.VIRTUAL + LEAF + ': No such file or directory']:
            with self.subTest(event=event): self.assertFalse(self.inspect(self.messages + [event])['complete'])

    def test_unknown_registry_member_fails(self):
        self.assertFalse(self.inspect(self.messages + [self.messages[0].replace(LEAF, 'unknown'), 'close(3)'])['complete'])

    def test_other_unit_cannot_supply_evidence(self):
        self.assertFalse(self.inspect(rows=[r | {'_SYSTEMD_UNIT': 'hexagonrpcd-adsp-rootpd.service'}
                                           for r in self.rows()])['complete'])

    def test_multiple_pids_or_wrong_boot_rejected(self):
        for key, value in [('_PID', '20'), ('_BOOT_ID', '2' * 32)]:
            rows = self.rows(); rows[1][key] = value
            with self.assertRaises(ValueError): self.inspect(rows=rows)

    def test_bad_timestamp_or_missing_pid_rejected(self):
        for key, value in [('__MONOTONIC_TIMESTAMP', '-1'), ('__MONOTONIC_TIMESTAMP', '1'), ('_PID', None)]:
            rows = self.rows(); rows[1][key] = value
            with self.assertRaises(ValueError): self.inspect(rows=rows)

    def test_invalid_manifest_or_empty_journal_rejected(self):
        for item in [dict(bytes=True, sha256='a' * 64), dict(bytes=-1, sha256='a' * 64),
                     dict(bytes=600, sha256='bad')]:
            self.manifest[m.PHYSICAL + LEAF] = item
            with self.assertRaises(ValueError): self.inspect()
        with self.assertRaises(ValueError): m.inspect('', BOOT, {})

    def test_failed_oemconfig_lookup_is_not_a_false_read_failure_or_cause_claim(self):
        self.assertTrue(self.inspect(['Could not open oemconfig.so: No such file or directory'] + self.messages)['complete'])

    def test_actual_test380_replay_and_pinned_cli(self):
        base = ROOT / 'reference/boot-tests/test-380-ssc-rpc-stat-enrolled'
        journal = base / 'runtime-discovery/failure-unit-journal.txt'
        manifest = base / 'asset-manifest.json'
        hashes = json.loads((base / 'RESULT_SHA256.json').read_text())
        args = [sys.executable, str(SCRIPT), '--journal', str(journal), '--manifest', str(manifest),
                '--boot-id', '16971083-2297-4220-a24f-24e113ba612d',
                '--journal-sha256', hashes[str(journal.relative_to(base))],
                '--manifest-sha256', hashes['asset-manifest.json']]
        process = subprocess.run(args, capture_output=True, text=True, timeout=10)
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual((result['expected_nonempty_groups'], result['observed_nonempty_groups'],
                          result['returned_bytes'], result['read_calls']), (178, 178, 44863, 203))
        args[-1] = '0' * 64
        process = subprocess.run(args, capture_output=True, text=True, timeout=10)
        self.assertNotEqual(process.returncode, 0)
        self.assertIn('hash mismatch', process.stderr)


if __name__ == '__main__': unittest.main()
