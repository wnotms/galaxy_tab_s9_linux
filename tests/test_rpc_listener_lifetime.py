"""Actual rpcd.c ownership/order and frozen profile tests; no tablet access."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('listener_profile_test', ROOT/'userspace/sensors/rpc_listener_lifetime_profile.py')
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)
SOURCE = ROOT/'out/rpc-open-error/sources'


class ListenerLifetimeTests(unittest.TestCase):
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
                '-DHEXAGONRPC_VERBOSE', '-I'+str(source/'include'), '-I'+str(source/'hexagonrpcd'),
                str(ROOT/'tests/fixtures/rpc_listener_lifetime_harness.c'), '-Wl,--gc-sections',
                '-o', str(cls.root/(name+'-harness'))], capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError(result.stderr)

    def case(self, mode, profile='final'):
        result = subprocess.run([str(self.root/(profile+'-harness')), profile, mode],
            capture_output=True, text=True, check=True, timeout=5)
        self.assertNotIn('runtime error', result.stderr)
        return json.loads(result.stdout.splitlines()[-1])

    def test_retained_until_loop_returns(self):
        row = self.case('normal')
        self.assertEqual(row['events'], 'ORLCD')
        self.assertTrue(row['held_at_loop'])
        self.assertEqual((row['opens'], row['registers'], row['loops'], row['closes']), (1, 1, 1, 1))
        self.assertEqual((row['remaining_contexts'], row['locals_closed']), (0, 1))

    def test_original_releases_before_callbacks(self):
        row = self.case('normal', 'original')
        self.assertEqual(row['events'], 'ORCLD')
        self.assertFalse(row['held_at_loop'])

    def test_loop_error_releases_once_after_callbacks(self):
        row = self.case('loop-error')
        self.assertEqual(row['events'], 'ORLCD')
        self.assertEqual((row['closes'], row['remaining_contexts'], row['locals_closed']), (1, 0, 1))

    def test_open_transport_and_dsp_error_never_register_or_run(self):
        for mode in ('open-transport-error', 'open-dsp-error'):
            with self.subTest(mode=mode):
                row = self.case(mode)
                self.assertEqual(row['events'], 'OD')
                self.assertEqual((row['registers'], row['loops'], row['closes'], row['remaining_contexts']), (0, 0, 0, 0))

    def test_register_error_closes_without_loop(self):
        row = self.case('register-error')
        self.assertEqual(row['events'], 'ORCD')
        self.assertEqual((row['loops'], row['closes'], row['remaining_contexts'], row['locals_closed']), (0, 1, 0, 1))

    def test_close_transport_and_dsp_error_release_local_context_without_retry(self):
        for mode in ('close-transport-error', 'close-dsp-error'):
            with self.subTest(mode=mode):
                row = self.case(mode)
                self.assertEqual(row['events'], 'ORLCD')
                self.assertEqual((row['closes'], row['remaining_contexts'], row['locals_closed']), (1, 0, 1))
                old = self.case(mode, 'original')
                self.assertEqual(old['remaining_contexts'], 1)

    def test_repeated_local_sessions_do_not_leak_or_double_close(self):
        row = self.case('repeat')
        self.assertEqual((row['opens'], row['closes'], row['loops'], row['locals_closed']), (512, 512, 512, 512))
        self.assertEqual(row['events'], 'ORLCD'*512)
        self.assertEqual(row['remaining_contexts'], 0)

    def test_only_rpcd_changes_over_qualified_missing_file_profile(self):
        self.assertEqual(self.identity['changed_files'], ['hexagonrpcd/rpcd.c'])
        self.assertEqual(P.HELPER.files(SOURCE), self.identity['profile']['base_source_files'])
        self.assertFalse(self.identity['hardware_verified'])
        for name in ('hexagonrpcd/apps_std.c', 'hexagonrpcd/listener.c', 'libhexagonrpc/fastrpc.c'):
            self.assertEqual((SOURCE/name).read_bytes(), (self.root/'final'/name).read_bytes())

    def test_existing_overlapping_extra_corrupt_and_linked_sources_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for mode in ('extra', 'corrupt', 'linked'):
                source = root/mode
                shutil.copytree(SOURCE, source)
                target = source/'hexagonrpcd/rpcd.c'
                if mode == 'extra':
                    (source/'unknown').write_text('extra')
                elif mode == 'corrupt':
                    target.write_text('changed')
                else:
                    target.unlink()
                    target.symlink_to(SOURCE/'hexagonrpcd/rpcd.c')
                with self.subTest(mode=mode), self.assertRaises(ValueError):
                    P.prepare(source, root/(mode+'-out'))
            for target in (SOURCE, SOURCE/'nested', self.root/'final'):
                with self.assertRaises(ValueError):
                    P.prepare(SOURCE, target)

    def test_patch_drift_refused_before_preparing_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'diagnostics').mkdir()
            shutil.copyfile(P.BASE/'diagnostics/rpc-listener-lifetime.json', root/'diagnostics/rpc-listener-lifetime.json')
            (root/'diagnostics/rpc-listener-lifetime.patch').write_text('changed patch')
            with patch.object(P, 'BASE', root), self.assertRaisesRegex(ValueError, 'patch mismatch'):
                P.prepare(SOURCE, root/'out')
            self.assertFalse((root/'out').exists())


if __name__ == '__main__':
    unittest.main()
