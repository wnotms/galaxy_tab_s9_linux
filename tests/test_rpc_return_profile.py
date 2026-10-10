"""Actual modified listener and codec, independent framing and strict admission."""
import hashlib
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'userspace/sensors'


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, BASE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P = load('return_profile_test', 'rpc_return_profile.py')
E = load('return_evidence_test', 'rpc_return_evidence.py')
BOOT = '11111111-1111-4111-8111-111111111111'


def journal(lines, unit='hexagonrpcd-adsp-sensorspd.service', pid='17'):
    return [dict(MESSAGE=line, _BOOT_ID=BOOT.replace('-', ''), _PID=pid,
                 _SYSTEMD_UNIT=unit, __CURSOR=unit + str(i), __MONOTONIC_TIMESTAMP=str(i))
            for i, line in enumerate(lines) if line.startswith('RPCRETURN')]


class ReturnProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.source = ROOT / 'out/ssc-sources/prepared-clean'
        cls.identity = P.prepare(cls.source, cls.root / 'profile')
        cls.tree = cls.root / 'profile/hexagonrpc'
        cls.binary = cls.root / 'harness'
        cls.compile(cls.binary)

    @classmethod
    def compile(cls, binary, sanitized=False):
        command = ['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                   '-Wno-unused-function', '-Wno-unused-parameter',
                   '-ffunction-sections', '-fdata-sections',
                   '-DHEXAGONRPC_BUILD_METHOD_DEFINITIONS=1',
                   '-I' + str(cls.tree / 'include'), '-I' + str(cls.tree / 'hexagonrpcd'),
                   str(ROOT / 'tests/fixtures/rpc_return_harness.c'),
                   str(cls.tree / 'hexagonrpcd/iobuffer.c'),
                   '-Wl,--gc-sections', '-o', str(binary)]
        if sanitized:
            command[1:1] = ['-fsanitize=undefined', '-fno-sanitize-recover=all']
        subprocess.run(command, check=True, capture_output=True)

    def run_case(self, case='normal', opt_in='1', binary=None):
        env = dict(os.environ)
        env.pop('HEXAGONRPC_RETURN_TRACE', None)
        if opt_in is not None:
            env['HEXAGONRPC_RETURN_TRACE'] = opt_in
        return subprocess.run([str(binary or self.binary), case], env=env,
                              capture_output=True, text=True, check=True, timeout=5)

    def evidence(self, lines):
        rows = journal(lines)
        rows += journal(['RPCRETURN seq=0 phase=tx rctx=0 handle=0 sc=00000000 '
                         'status=4294967295 bytes=0 hex=-'],
                        unit='hexagonrpcd-adsp-rootpd.service', pid='18')
        return E.inspect('\n'.join(json.dumps(row) for row in rows), BOOT)

    def test_real_listener_preserves_reply_and_consumes_empty_input(self):
        result = self.evidence(self.run_case().stderr.splitlines())
        self.assertTrue(result['complete'], result['faults'])
        calls = result['streams'][0]['calls']
        self.assertEqual(calls[1]['returned_buffer_lengths'], [8, 4])
        self.assertEqual(calls[1]['returned_buffer_sha256'][1], hashlib.sha256(b'abcd').hexdigest())
        self.assertEqual(calls[0]['request']['buffer_lengths'], [4, 0])
        self.assertFalse(result['DSP_content_parsing_proved'])

    def test_default_disabled_and_only_exact_opt_in(self):
        for value in (None, '', 'yes', '0'):
            with self.subTest(value=value):
                self.assertEqual(self.run_case(opt_in=value).stderr, '')

    def test_large_invoke_logs_full_frame_after_second_ioctl(self):
        result = self.evidence(self.run_case('large').stderr.splitlines())
        self.assertTrue(result['complete'], result['faults'])
        self.assertEqual(result['streams'][0]['calls'][0]['request']['buffer_lengths'], [4, 300])

    def test_transport_failure_is_not_success(self):
        result = self.evidence(self.run_case('transport-error').stderr.splitlines())
        self.assertTrue(result['complete'], result['faults'])
        self.assertEqual(result['streams'][0]['calls'][-1]['transport_return'], -1)

    def test_frame_limit_explicit_no_silent_truncation_or_second_record(self):
        result = self.run_case('frame-limit').stderr
        self.assertEqual(result, 'RPCRETURN_LIMIT seq=0 reason=frame\n')
        self.assertFalse(self.evidence(result.splitlines())['complete'])

    def test_null_nonempty_frame_stops_without_dereference(self):
        self.assertEqual(self.run_case('null-frame').stderr, 'RPCRETURN_LIMIT seq=0 reason=frame\n')

    def test_budget_bounded_and_input_untouched(self):
        result = self.run_case('budget').stderr
        self.assertLessEqual(len(result.encode()), 524288 + 80)
        self.assertEqual(result.count('RPCRETURN_LIMIT'), 1)
        self.assertTrue(result.splitlines()[-1].endswith('reason=budget'))

    def test_native_undefined_behavior_sanitizer(self):
        binary = self.root / 'harness-ubsan'
        self.compile(binary, sanitized=True)
        for case in ('normal', 'large', 'transport-error', 'frame-limit', 'budget'):
            self.run_case(case, binary=binary)

    def test_exact_two_changed_files_existing_callbacks_codec_library_unchanged(self):
        self.assertEqual(self.identity['composition']['changes_from_wire_stat'],
                         ['hexagonrpcd/listener.c', 'hexagonrpcd/rpc-return-trace.h'])
        before = self.identity['base_source']['patched_files']
        after = self.identity['patched_files']
        for name in before:
            if name not in ('hexagonrpcd/listener.c', 'hexagonrpcd/apps_std.c', 'hexagonrpcd/iobuffer.c'):
                self.assertEqual(before[name], after[name], name)

    def test_existing_output_rejected_without_overwrite(self):
        with self.assertRaises(ValueError):
            P.prepare(self.source, self.root / 'profile')

    def test_inside_source_output_rejected_before_write(self):
        with self.assertRaises(ValueError):
            P.prepare(self.source, self.source / 'forbidden-return-output')

    def test_incomplete_source_rejected_before_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'output'
            with self.assertRaises((ValueError, FileNotFoundError)):
                P.prepare(Path(directory), output)
            self.assertFalse(output.exists())


class FramingTests(unittest.TestCase):
    def test_golden_unaligned_output_capacities(self):
        frame = bytes.fromhex('0800000000000000') + b'\0'*8
        frame += bytes.fromhex('0900000000000000') + b'example\0\0'
        frame += struct.pack('<II', 8, 255)
        self.assertEqual(len(frame), 41)
        inputs, capacities = E.invocation(frame, 0x00020200)
        self.assertEqual(inputs, [b'\0'*8, b'example\0\0'])
        self.assertEqual(capacities, [8, 255])

    def test_recorded_test388_first_invoke_matches_reference_layout(self):
        row=json.loads((ROOT/'tests/fixtures/rpc_return_first_invoke.json').read_text())
        parsed=E.invocation(bytes.fromhex(row['hex']), int(row['scalars'],16))
        self.assertEqual([len(x) for x in parsed[0]], [8,9])
        self.assertEqual(parsed[1], [8,255])

    def test_capacity_count_exact_not_arbitrary_trailing_bytes(self):
        frame = struct.pack('<II', 0, 512)
        self.assertEqual(E.invocation(frame, 0x01010100), ([b''], [512]))
        for value in (frame[:-1], frame+b'\0', frame+b'\0'*4):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, 'output capacity'):
                    E.invocation(value, 0x01010100)

    def test_output_only_and_zero_output_input_frames(self):
        self.assertEqual(E.invocation(struct.pack('<II', 4, 0), 0x00000200), ([], [4, 0]))
        self.assertEqual(E.invocation(struct.pack('<I', 0), 0x00010000), ([b''], []))
        self.assertEqual(E.invocation(b'', 0), ([], []))

    def test_response_rejects_capacity_descriptor_trailer(self):
        with self.assertRaisesRegex(ValueError, 'extra frame'):
            E.buffers(struct.pack('<II', 0, 512), 1)

    def test_independent_empty_and_nonempty_golden(self):
        frame = bytes.fromhex('000000000300000061626300000000')
        self.assertEqual(E.buffers(frame, 3), [b'', b'abc', b''])

    def test_truncated_headers_payload_and_extra_bytes(self):
        for frame, count in ((b'\0', 1), (b'\x02\0\0\0', 1), (b'\0' * 5, 1)):
            with self.subTest(frame=frame):
                with self.assertRaises(ValueError): E.buffers(frame, count)

    def test_over_budget_frame_rejected(self):
        with self.assertRaises(ValueError): E.buffers(b'x' * 8193, 0)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.rows = []
        for unit, pid in [('hexagonrpcd-adsp-rootpd.service', '17'),
                          ('hexagonrpcd-adsp-sensorspd.service', '18')]:
            self.rows += journal([
                'RPCRETURN seq=0 phase=tx rctx=0 handle=0 sc=00000000 status=4294967295 bytes=0 hex=-',
                'RPCRETURN seq=0 phase=next rctx=10 handle=1 sc=04010200 status=0 bytes=0 hex=-',
                'RPCRETURN seq=0 phase=rx rctx=10 handle=1 sc=04010200 status=0 bytes=20 hex=0400000000000000070000000800000004000000',
                'RPCRETURN seq=1 phase=tx rctx=10 handle=1 sc=04010200 status=0 bytes=28 hex=08000000000000000400000001000000040000000000000061626364',
            ], unit, pid)

    def evidence(self):
        return E.inspect('\n'.join(json.dumps(row) for row in self.rows), BOOT)

    def assert_fault(self):
        self.assertFalse(self.evidence()['complete'])

    def test_final_blocked_call_remains_pending_not_acknowledged(self):
        result = self.evidence()
        self.assertTrue(result['complete'], result['faults'])
        for stream in result['streams']:
            self.assertEqual(len(stream['calls']), 1)
            self.assertIsNone(stream['pending_final_call']['transport_return'])
            self.assertEqual(stream['calls'][0]['request']['output_capacities'], [8, 4])
            self.assertEqual(stream['pending_final_call']['response_to']['output_capacities'], [8, 4])

    def test_missing_capacity_descriptors_stops_without_dropping_bytes(self):
        self.rows[2]['MESSAGE'] = self.rows[2]['MESSAGE'].replace('bytes=20', 'bytes=12')[:-16]
        result = self.evidence()
        self.assertFalse(result['complete'])
        self.assertTrue(any('output capacity' in x['reason'] for x in result['faults']))

    def test_wrong_boot(self):
        self.rows[0]['_BOOT_ID'] = '2' * 32
        self.assert_fault()

    def test_missing_unit(self):
        self.rows = self.rows[:4]
        self.assert_fault()

    def test_restarted_unit(self):
        self.rows += journal([self.rows[0]['MESSAGE']], pid='19')
        self.rows[-1]['__CURSOR'] += '-new'
        self.assert_fault()

    def test_duplicate_cursor(self):
        self.rows[1]['__CURSOR'] = self.rows[0]['__CURSOR']
        self.assert_fault()

    def test_dropped_request(self):
        self.rows.pop(2)
        self.assert_fault()

    def test_duplicate_sequence(self):
        self.rows[3]['MESSAGE'] = self.rows[3]['MESSAGE'].replace('seq=1', 'seq=0')
        self.assert_fault()

    def test_wrong_return_context(self):
        self.rows[3]['MESSAGE'] = self.rows[3]['MESSAGE'].replace('rctx=10', 'rctx=11')
        self.assert_fault()

    def test_incoming_metadata_must_match_next2(self):
        self.rows[2]['MESSAGE'] = self.rows[2]['MESSAGE'].replace('handle=1', 'handle=2')
        self.assert_fault()

    def test_wrong_declared_size(self):
        self.rows[2]['MESSAGE'] = self.rows[2]['MESSAGE'].replace('bytes=20', 'bytes=21')
        self.assert_fault()

    def test_truncated_hex(self):
        self.rows[2]['MESSAGE'] = self.rows[2]['MESSAGE'][:-1]
        self.assert_fault()

    def test_missing_source_timestamp(self):
        self.rows[0].pop('__MONOTONIC_TIMESTAMP')
        self.assert_fault()


class RegistryContentsTests(unittest.TestCase):
    def setUp(self):
        self.path = '/mnt/vendor/persist/sensors/registry/registry/group.json'
        self.manifest = {'usr/share/qcom/sm8550/Samsung/gts9wifi/sensors/registry/group.json':
                         {'bytes': 4, 'sha256': hashlib.sha256(b'abcd').hexdigest()}}
        self.calls = []
        self.add(19, [b'\0' * 16, b'ADSP_LIBRARY_PATH\0', b';\0', self.path.encode() + b'\0', b'r\0'],
                 [struct.pack('<I', 4)])
        self.add(4, [struct.pack('<II', 4, 512)], [struct.pack('<II', 4, 1), b'abcd' + b'X' * 508])
        self.add(3, [struct.pack('<I', 4)], [])

    def add(self, method, incoming, outgoing):
        self.calls.append({'sequence': len(self.calls), 'status': 0, 'transport_return': 0,
                           'response_to': {'handle': 1, 'scalars': method << 24,
                                           'buffers_hex': [p.hex() for p in incoming]},
                           'returned_buffers_hex': [p.hex() for p in outgoing]})

    def result(self, pending=None):
        evidence = {'complete': True, 'streams': [{'unit': 'hexagonrpcd-adsp-sensorspd.service',
                    'calls': self.calls, 'pending_final_call': pending}]}
        return E.registry_contents(evidence, self.manifest)

    def test_exact_content_not_padding_hash_matches(self):
        result = self.result()
        self.assertTrue(result['complete'], result)
        self.assertEqual(result['sessions'][0]['returned_bytes'], 4)
        self.assertEqual(result['sessions'][0]['returned_sha256'], hashlib.sha256(b'abcd').hexdigest())
        self.assertFalse(result['DSP_content_parsing_proved'])

    def test_real_returned_corruption_is_detected_despite_correct_lengths(self):
        self.calls[1]['returned_buffers_hex'][1] = (b'abce' + b'X' * 508).hex()
        self.assertFalse(self.result()['complete'])

    def test_multiple_read_calls_are_concatenated_by_fd(self):
        close = self.calls.pop()
        self.calls[1]['returned_buffers_hex'] = [struct.pack('<II', 2, 0).hex(), (b'ab' + b'X' * 510).hex()]
        self.add(4, [struct.pack('<II', 4, 512)], [struct.pack('<II', 2, 1), b'cd' + b'X' * 510])
        close['sequence'] = 3
        self.calls.append(close)
        self.assertTrue(self.result()['complete'])

    def test_close_not_acknowledged_is_incomplete(self):
        pending = self.calls.pop()
        pending['transport_return'] = None
        self.assertFalse(self.result(pending)['complete'])

    def test_partial_read_unclosed_failed_read_and_reused_fd(self):
        original = copy.deepcopy(self.calls)
        for mode in ('partial', 'unclosed', 'failed', 'reuse'):
            self.calls = copy.deepcopy(original)
            if mode == 'partial': self.calls[1]['returned_buffers_hex'][0] = struct.pack('<II', 3, 1).hex()
            elif mode == 'unclosed': self.calls.pop()
            elif mode == 'failed': self.calls[1]['transport_return'] = -1
            else: self.calls.insert(1, copy.deepcopy(self.calls[0]))
            with self.subTest(mode=mode): self.assertFalse(self.result()['complete'])

    def test_nonlinear_seek_detected(self):
        self.calls[1]['response_to']['scalars'] = 9 << 24
        self.assertFalse(self.result()['complete'])

    def test_invalid_return_length_detected(self):
        self.calls[1]['returned_buffers_hex'][0] = struct.pack('<II', 513, 1).hex()
        self.assertFalse(self.result()['complete'])

    def test_missing_group_and_malformed_manifest_rejected(self):
        self.manifest['usr/share/qcom/sm8550/Samsung/gts9wifi/sensors/registry/second.json'] = next(iter(self.manifest.values()))
        self.assertFalse(self.result()['complete'])
        self.manifest = {'usr/share/qcom/sm8550/Samsung/gts9wifi/sensors/registry/../outside':
                         {'bytes': 4, 'sha256': '0' * 64}}
        with self.assertRaises(ValueError): self.result()


class InitializationContentsTests(unittest.TestCase):
    def setUp(self):
        self.path = '/sys/devices/soc0/soc_id'
        self.data = b'519\n'
        self.expected = {self.path: {'bytes': len(self.data),
                                    'sha256': hashlib.sha256(self.data).hexdigest()}}
        self.calls = []
        self.open(self.path)
        self.add(4, [struct.pack('<II', 4, 32)],
                 [struct.pack('<II', 4, 1), self.data + b'X' * 28])
        self.add(3, [struct.pack('<I', 4)], [])

    add = RegistryContentsTests.add

    def open(self, path):
        self.add(19, [b'\0' * 16, b'ADSP_LIBRARY_PATH\0', b';\0',
                      path.encode() + b'\0', b'r\0'], [struct.pack('<I', 4)])

    def result(self):
        return E.file_contents({'complete': True, 'streams': [
            {'unit': 'hexagonrpcd-adsp-sensorspd.service', 'calls': self.calls,
             'pending_final_call': None}]}, self.expected)

    def test_exact_input_and_padding(self):
        result = self.result()
        self.assertTrue(result['complete'], result)
        self.assertEqual(result['expected_files'], 1)
        self.assertEqual(result['sessions'][0]['returned_bytes'], 4)
        self.assertFalse(result['DSP_content_parsing_proved'])

    def test_version_marker_parent_alias(self):
        path = '/mnt/vendor/persist/sensors/registry/sns_reg_version'
        self.expected = {path: next(iter(self.expected.values()))}
        self.calls[0]['response_to']['buffers_hex'][3] = (
            '/mnt/vendor/persist/sensors/registry/registry/../sns_reg_version\0').encode().hex()
        self.assertTrue(self.result()['complete'])

    def test_other_path_cannot_substitute_expected_input(self):
        self.calls[0]['response_to']['buffers_hex'][3] = b'/sys/devices/soc0/other\0'.hex()
        self.assertFalse(self.result()['complete'])

    def test_matching_bytes_without_close_are_not_completed_session(self):
        self.calls.pop()
        result = self.result()
        self.assertFalse(result['complete'])
        self.assertTrue(result['sessions'][0]['returned_bytes_match'])
        self.assertFalse(result['sessions'][0]['content_matches'])

    def test_missing_failed_unacknowledged_and_corrupt_inputs(self):
        original = copy.deepcopy(self.calls)
        for mode in ('missing', 'failed-open', 'failed-read', 'pending-close', 'corrupt'):
            self.calls = copy.deepcopy(original)
            if mode == 'missing': self.calls = []
            elif mode == 'failed-open': self.calls[0]['status'] = 1
            elif mode == 'failed-read': self.calls[1]['status'] = 1
            elif mode == 'pending-close': self.calls[2]['transport_return'] = None
            else: self.calls[1]['returned_buffers_hex'][1] = (b'520\n' + b'X' * 28).hex()
            with self.subTest(mode=mode): self.assertFalse(self.result()['complete'])

    def test_unrelated_open_reusing_tracked_descriptor_is_fault(self):
        self.open('/unrelated')
        self.calls.insert(1, self.calls.pop())
        self.assertFalse(self.result()['complete'])

    def test_manifest_requires_canonical_absolute_paths_and_real_lengths(self):
        original = copy.deepcopy(self.expected)
        for path in ('relative', '/sys/devices/soc0/../soc_id'):
            self.expected = {path: next(iter(original.values()))}
            with self.subTest(path=path), self.assertRaises(ValueError): self.result()
        self.expected = original
        self.expected[self.path]['bytes'] = True
        with self.assertRaises(ValueError): self.result()

    def test_empty_manifest_is_not_success(self):
        self.expected = {}
        self.assertFalse(self.result()['complete'])


class ReturnBudgetV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root=Path(cls.temp.name)
        cls.identity=P.prepare(ROOT/'out/ssc-sources/prepared-clean',cls.root/'profile','rpc-return-v2')
        cls.tree=cls.root/'profile/hexagonrpc'
        cls.binary=cls.root/'harness'
        ReturnProfileTests.compile.__func__(cls,cls.binary)

    def test_new_budget_explicit_bounded_and_original_profile_retained(self):
        env=dict(os.environ,HEXAGONRPC_RETURN_TRACE='1')
        result=subprocess.run([str(self.binary),'budget'],env=env,capture_output=True,check=True)
        self.assertGreater(len(result.stderr),524288)
        self.assertLessEqual(len(result.stderr),1048576+80)
        self.assertEqual(result.stderr.count(b'RPCRETURN_LIMIT'),1)
        self.assertTrue(result.stderr.splitlines()[-1].endswith(b'reason=budget'))
        old=json.loads((BASE/'diagnostics/rpc-return.json').read_text())
        self.assertEqual(old['per_process_trace_bytes'],524288)
        self.assertEqual(hashlib.sha256((BASE/'diagnostics/rpc-return-trace.h').read_bytes()).hexdigest(),old['header_sha256'])

    def test_v2_only_budget_header_differs_from_v1_prepared_sources(self):
        first=P.prepare(ROOT/'out/ssc-sources/prepared-clean',self.root/'original')
        different=[n for n,v in first['patched_files'].items() if self.identity['patched_files'][n]!=v]
        self.assertEqual(different,['hexagonrpcd/rpc-return-trace.h'])

    def test_v2_real_listener_preserves_wire_and_full_capacities(self):
        result=subprocess.run([str(self.binary),'large'],env=dict(os.environ,HEXAGONRPC_RETURN_TRACE='1'),capture_output=True,text=True,check=True)
        rows=journal(result.stderr.splitlines())
        rows+=journal(['RPCRETURN seq=0 phase=tx rctx=0 handle=0 sc=00000000 status=4294967295 bytes=0 hex=-'],unit='hexagonrpcd-adsp-rootpd.service',pid='18')
        evidence=E.inspect('\n'.join(json.dumps(x) for x in rows),BOOT)
        self.assertTrue(evidence['complete'],evidence['faults'])
        self.assertEqual(evidence['streams'][0]['calls'][0]['request']['output_capacities'],[8,4])

    def test_unknown_profile_rejected_before_output(self):
        output=self.root/'unknown'
        with self.assertRaises(ValueError):P.prepare(ROOT/'out/ssc-sources/prepared-clean',output,'../other')
        self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
