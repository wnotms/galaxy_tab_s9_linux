"""Run the actual RPC callback under filesystem faults, not a Python rewrite."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('rpc_stat_profile', ROOT / 'userspace/sensors/rpc_stat_profile.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class RpcStatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name)
        cls.source = ROOT / 'out/ssc-sources/prepared-clean'
        cls.identity = m.prepare(cls.source, cls.root / 'profile')
        cls.binary = cls.root / 'harness'
        source = cls.root / 'profile/hexagonrpc'
        cls.compile(source, cls.binary)
        cls.unpatched = cls.root / 'unpatched'
        cls.compile(cls.source / 'hexagonrpc', cls.unpatched)

    @classmethod
    def compile(cls, source, binary):
        subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra',
                        '-Wno-unused-function', '-Wno-unused-parameter',
                        '-ffunction-sections', '-fdata-sections',
                        '-DHEXAGONRPC_VERBOSE', '-I' + str(source / 'include'),
                        '-I' + str(source / 'hexagonrpcd'),
                        str(ROOT / 'tests/fixtures/rpc_stat_harness.c'),
                        '-Wl,--gc-sections', '-o', str(binary)],
                       capture_output=True, text=True, check=True)

    def run_case(self, case):
        return subprocess.run([str(self.binary), case], capture_output=True,
                              text=True, check=True, timeout=5)

    def test_wire_metadata_and_verbose_mtime(self):
        result = self.run_case('success')
        self.assertIn('size=4294967299 mtime=1640995200.000000123', result.stdout)
        self.assertEqual(result.stderr, '')

    def test_open_failure(self):
        self.assertIn('No such file or directory', self.run_case('open-error').stderr)

    def test_stat_failure_closes_fd_and_reports_actual_error(self):
        self.assertIn('Input/output error', self.run_case('stat-error').stderr)

    def test_1024_stat_failures_do_not_exhaust_descriptors(self):
        self.run_case('repeat-error')

    def test_same_fault_reproduces_leak_in_fedora_baseline(self):
        result = subprocess.run([str(self.unpatched), 'stat-error'],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 23)

    def test_zero_and_null_path_rejected_before_open(self):
        for case in ('zero-path', 'null-path'):
            with self.subTest(case=case): self.run_case(case)

    def test_unterminated_path_rejected(self):
        self.run_case('unterminated')

    def test_short_or_null_output_untouched(self):
        for case in ('short-output', 'null-output'):
            with self.subTest(case=case): self.run_case(case)

    def test_only_stat_source_changed_and_baseline_unchanged(self):
        before = self.identity['base_source']['patched_files']
        after = self.identity['patched_files']
        self.assertEqual([n for n in before if before[n] != after[n]], ['hexagonrpcd/apps_std.c'])
        self.assertEqual(m.files(self.source / 'hexagonrpc'), before)
        self.assertFalse(self.identity['device_operations'])

    def test_existing_profile_not_overwritten(self):
        with self.assertRaisesRegex(ValueError, 'output must be absent'):
            m.prepare(self.source, self.root / 'profile')

    def test_modified_input_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as name:
            tree = Path(name)
            # Verification rejects the forged file set before publishing anything.
            (tree / 'PREPARED.json').write_bytes((self.source / 'PREPARED.json').read_bytes())
            with self.assertRaises(ValueError): m.prepare(tree, tree.parent / (tree.name + '-out'))
            self.assertFalse((tree.parent / (tree.name + '-out')).exists())


if __name__ == '__main__':
    unittest.main()
