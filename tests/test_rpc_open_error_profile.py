"""Real C callback/VFS behavior and strict source composition; no tablet access."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('rpc_open_profile_test', ROOT / 'userspace/sensors/rpc_open_error_profile.py')
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)
SOURCE = ROOT / 'out/ssc-rpc-return-v2/sources/hexagonrpc'


class OpenErrorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.identity = P.prepare(SOURCE, cls.root / 'final')
        cls.payload = cls.root / 'payload'
        cls.payload.write_bytes(b'private-payload')
        for name, source in (('original', SOURCE), ('final', cls.root / 'final')):
            cls.compile(source, cls.root / (name + '-harness'))

    @staticmethod
    def compile(source, binary):
        directory = source / 'hexagonrpcd'
        result = subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                        '-Wno-unused-function', '-Wno-unused-parameter',
                        '-fsanitize=undefined', '-fno-sanitize-recover=all',
                        '-ffunction-sections', '-fdata-sections', '-DHEXAGONRPC_VERBOSE',
                        '-I' + str(source / 'include'), '-I' + str(directory),
                        str(ROOT / 'tests/fixtures/rpc_open_error_harness.c'),
                        str(directory / 'hexagonfs.c'), str(directory / 'hexagonfs_virt_dir.c'),
                        str(directory / 'hexagonfs_mapped.c'), '-Wl,--gc-sections', '-o', str(binary)],
                       capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stderr)

    def case(self, mode, profile='final'):
        run = subprocess.run([str(self.root / (profile + '-harness')), mode, str(self.payload)],
                             capture_output=True, text=True, check=True, timeout=5)
        self.assertNotIn('runtime error', run.stderr)
        return json.loads(run.stdout.splitlines()[-1]), run

    def test_real_missing_library_returns_qualcomm_status(self):
        row, run = self.case('missing')
        self.assertEqual(row['status'], 0x45)
        self.assertIn('No such file or directory', run.stderr)
        self.assertNotIn('Input/output error', run.stderr)

    def test_original_collapses_missing_file_and_uses_stale_errno(self):
        row, run = self.case('missing', 'original')
        self.assertEqual(row['status'], 1)
        self.assertIn('Input/output error', run.stderr)

    def test_successful_file_bytes_and_descriptor_lifecycle_unchanged(self):
        original, before = self.case('present', 'original')
        final, after = self.case('present')
        self.assertEqual(original, final)
        self.assertEqual(final['status'], 0)
        self.assertEqual(before.stdout, after.stdout)
        self.assertEqual(self.payload.read_bytes(), b'private-payload')

    def test_permission_and_io_errors_are_not_relabelled_missing(self):
        for mode, text in (('permission', 'Permission denied'), ('io-error', 'Input/output error')):
            with self.subTest(mode=mode):
                row, run = self.case(mode)
                self.assertEqual(row['status'], 1)
                self.assertIn(text, run.stderr)

    def test_readonly_write_remains_failed_without_modification(self):
        row, run = self.case('readonly-write')
        self.assertEqual(row['status'], 1)
        self.assertIn('Read-only file system', run.stderr)
        self.assertEqual(self.payload.read_bytes(), b'private-payload')

    def test_invalid_environment_mode_and_missing_directory_unchanged(self):
        for mode, expected in (('unknown-env', 14), ('bad-mode', 14), ('missing-dir', 1)):
            with self.subTest(mode=mode):
                self.assertEqual(self.case(mode)[0]['status'], expected)

    def test_repeated_missing_requests_do_not_consume_descriptors(self):
        row, _ = self.case('repeat-missing')
        self.assertEqual((row['status'], row['loops'], row['remaining_fds']), (69, 1024, 1))

    def test_only_open_callback_and_error_number_change(self):
        self.assertEqual(self.identity['changed_files'], ['hexagonrpcd/aee_error.h', 'hexagonrpcd/apps_std.c'])
        self.assertEqual(P.HELPER.files(SOURCE), self.identity['profile']['base_source_files'])
        self.assertFalse(self.identity['hardware_verified'])

    def test_existing_overlap_corrupt_extra_and_links_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            for mode in ('corrupt', 'extra', 'link'):
                source = directory / mode
                shutil.copytree(SOURCE, source)
                file = source / 'hexagonrpcd/apps_std.c'
                if mode == 'corrupt': file.write_text('altered')
                elif mode == 'extra': (source / 'extra').write_text('extra')
                else:
                    file.unlink(); file.symlink_to(SOURCE / 'hexagonrpcd/apps_std.c')
                with self.subTest(mode=mode), self.assertRaises(ValueError):
                    P.prepare(source, directory / ('out-' + mode))
            for output in (self.root / 'final', SOURCE / 'nested'):
                with self.subTest(output=output), self.assertRaises(ValueError):
                    P.prepare(SOURCE, output)

    def test_corrupt_patch_rejected_before_output_publication(self):
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            shutil.copytree(P.BASE / 'diagnostics', base / 'diagnostics')
            (base / 'diagnostics/rpc-open-error.patch').write_text('altered')
            output = base / 'output'
            with patch.object(P, 'BASE', base), self.assertRaisesRegex(ValueError, 'patch mismatch'):
                P.prepare(SOURCE, output)
            self.assertFalse(output.exists())
