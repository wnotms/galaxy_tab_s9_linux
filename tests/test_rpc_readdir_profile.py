"""Actual readdir callback, recorded EOF residue and source isolation checks."""
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('readdir_profile_test', ROOT/'userspace/sensors/rpc_readdir_profile.py')
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)
ESPEC = importlib.util.spec_from_file_location('readdir_evidence_test', ROOT/'userspace/sensors/rpc_readdir_evidence.py')
E = importlib.util.module_from_spec(ESPEC)
ESPEC.loader.exec_module(E)
SOURCE = ROOT/'out/rpc-listener-lifetime/sources'
EVIDENCE = ROOT/'reference/boot-tests/test-397-sensor-first-startup/runtime-discovery/discovery-rpc-return-frames.json'


class ReaddirTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.identity = P.prepare(SOURCE, cls.root/'final')
        for name, source in [('original', SOURCE), ('final', cls.root/'final')]:
            result = subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                '-Wno-unused-function', '-Wno-unused-parameter', '-fsanitize=undefined',
                '-fno-sanitize-recover=all', '-ffunction-sections', '-fdata-sections',
                '-I'+str(source/'include'), '-I'+str(source/'hexagonrpcd'),
                str(ROOT/'tests/fixtures/rpc_readdir_harness.c'), '-Wl,--gc-sections',
                '-o', str(cls.root/(name+'-harness'))], capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError(result.stderr)

    def case(self, mode, profile='final'):
        result = subprocess.run([str(self.root/(profile+'-harness')), profile, mode],
            capture_output=True, text=True, check=True, timeout=5)
        self.assertNotIn('runtime error', result.stderr)
        return json.loads(result.stdout.splitlines()[-1])

    def test_original_eof_exposes_stale_memory(self):
        old = self.case('eof', 'original')
        self.assertEqual((old['status'], old['eof'], old['tail_nonzero'], old['padding']), (0, 1, 254, 165))

    def test_eof_reply_fully_initialized_without_changing_status(self):
        new = self.case('eof')
        self.assertEqual((new['status'], new['calls'], new['eof'], new['inode'], new['tail_nonzero'], new['padding']),
                         (0, 1, 1, 0, 0, 0))

    def test_existing_name_and_maximum_name_unchanged(self):
        for mode in ('name', 'max-name'):
            with self.subTest(mode=mode):
                old, new = self.case(mode, 'original'), self.case(mode)
                self.assertEqual((old['status'], old['eof'], old['inode']), (new['status'], new['eof'], new['inode']))
                self.assertEqual(new['padding'], 0)

    def test_backend_error_returns_failure_once_with_no_old_bytes(self):
        old, new = self.case('error', 'original'), self.case('error')
        self.assertEqual((old['status'], new['status'], new['calls']), (1, 1, 1))
        self.assertEqual((new['tail_nonzero'], new['padding']), (0, 0))

    def test_short_long_and_null_buffers_rejected_before_fs(self):
        for mode in ('short-in', 'long-in', 'short-out', 'long-out', 'null-in', 'null-out'):
            with self.subTest(mode=mode):
                row = self.case(mode)
                self.assertEqual((row['status'], row['calls']), (14, 0))

    def test_repeated_eof_cannot_reuse_previous_reply(self):
        row = self.case('repeat')
        self.assertEqual((row['calls'], row['eof'], row['tail_nonzero'], row['padding']), (512, 1, 0, 0))

    def test_actual397_attributed_eof_contains_previous_name_tail(self):
        report = json.loads(EVIDENCE.read_text())
        self.assertTrue(report['complete'])
        self.assertEqual(report['faults'], [])
        self.assertEqual(report['boot_id'], '65129696de09450b863c4d522465c5f3')
        found = []
        for stream in report['streams']:
            for call in stream['calls']:
                req = call['response_to']
                if req and req['handle'] == 1 and req['scalars'] >> 24 == 28 and call['status'] == 0:
                    buf = bytes.fromhex(call['returned_buffers_hex'][0])
                    self.assertEqual(len(buf), 264)
                    if struct.unpack_from('<I', buf, 260)[0] and any(buf[5:259]):
                        found.append((call['sequence'], buf[4], sum(x != 0 for x in buf[5:259])))
        self.assertEqual(found, [(954, 0, 15)])
        self.assertFalse(report['SSC_publication_proved'])
        observed = E.inspect(report)
        self.assertFalse(observed['complete'])
        self.assertEqual(observed['faults'], [{'sequence': 954, 'reason': 'nonzero reply tail/padding'}])

    def test_only_readdir_callback_file_changed_over397(self):
        self.assertEqual(self.identity['changed_files'], ['hexagonrpcd/apps_std.c'])
        self.assertFalse(self.identity['hardware_verified'])
        self.assertFalse(self.identity['profile']['fixes_SSC_publication'])
        for name in ('hexagonrpcd/rpcd.c', 'hexagonrpcd/listener.c', 'libhexagonrpc/fastrpc.c',
                     'hexagonrpcd/hexagonfs_mapped.c', 'hexagonrpcd/interfaces/apps_std.def'):
            self.assertEqual((SOURCE/name).read_bytes(), (self.root/'final'/name).read_bytes())

    def test_existing_overlapping_extra_corrupt_and_linked_sources_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for mode in ('extra', 'corrupt', 'linked'):
                source = root/mode
                shutil.copytree(SOURCE, source)
                target = source/'hexagonrpcd/apps_std.c'
                if mode == 'extra':
                    (source/'unknown').write_text('extra')
                elif mode == 'corrupt':
                    target.write_text('changed')
                else:
                    target.unlink()
                    target.symlink_to(SOURCE/'hexagonrpcd/apps_std.c')
                with self.subTest(mode=mode), self.assertRaises(ValueError):
                    P.prepare(source, root/(mode+'-out'))
            for target in (SOURCE, SOURCE/'nested', self.root/'final'):
                with self.assertRaises(ValueError):
                    P.prepare(SOURCE, target)

    def test_patch_drift_refused_before_preparing_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'diagnostics').mkdir()
            shutil.copyfile(P.BASE/'diagnostics/rpc-readdir.json', root/'diagnostics/rpc-readdir.json')
            (root/'diagnostics/rpc-readdir.patch').write_text('changed patch')
            with patch.object(P, 'BASE', root), self.assertRaisesRegex(ValueError, 'patch mismatch'):
                P.prepare(SOURCE, root/'out')
            self.assertFalse((root/'out').exists())


class ReaddirEvidenceTests(unittest.TestCase):
    def fixture(self, *, eof=1, name=b''):
        buf = bytearray(264)
        buf[4:4+len(name)] = name
        struct.pack_into('<I', buf, 260, eof)
        call = dict(response_to=dict(handle=1, scalars=0x1c010100), status=0, sequence=1,
                    returned_buffers_hex=[buf.hex()])
        return dict(complete=True, faults=[], streams=[dict(calls=[call])])

    def test_clean_eof_and_regular_name(self):
        row = self.fixture()
        row['streams'][0]['calls'].append(self.fixture(eof=0, name=b'registry')['streams'][0]['calls'][0])
        result = E.inspect(row)
        self.assertTrue(result['complete'])
        self.assertEqual((result['eof_replies'], len(result['replies'])), (1, 2))
        self.assertFalse(result['SSC_publication_proved'])

    def test_bad_fields_missing_nul_tail_and_padding_rejected(self):
        for offset, value in ((0, 1), (259, 2), (260, 2), (4, 65), (20, 65)):
            row = self.fixture()
            buf = bytearray.fromhex(row['streams'][0]['calls'][0]['returned_buffers_hex'][0])
            buf[offset] = value
            row['streams'][0]['calls'][0]['returned_buffers_hex'] = [buf.hex()]
            with self.subTest(offset=offset):
                self.assertFalse(E.inspect(row)['complete'])
        self.assertFalse(E.inspect(self.fixture(eof=0, name=b'x'*255))['complete'])

    def test_bad_status_length_or_hex_rejected(self):
        for change in ({'status': 1}, {'returned_buffers_hex': []},
                       {'returned_buffers_hex': ['00']}, {'returned_buffers_hex': ['invalid']}):
            row = self.fixture(); row['streams'][0]['calls'][0].update(change)
            with self.subTest(change=change):
                self.assertFalse(E.inspect(row)['complete'])

    def test_absent_eof_empty_or_incomplete_frames_are_not_pass(self):
        for row in (self.fixture(eof=0, name=b'name'), dict(complete=True, faults=[], streams=[]),
                    dict(complete=False, faults=[], streams=[]), dict(complete=True, faults=['bad attribution'], streams=[])):
            with self.subTest(row=row):
                self.assertFalse(E.inspect(row)['complete'])


if __name__ == '__main__':
    unittest.main()
