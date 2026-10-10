"""Strict isolated source preparation; real GLib/QEMU results are build evidence."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('libssc_wait_test', ROOT / 'userspace/sensors/libssc_wait_profile.py')
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)
SOURCE = ROOT / 'out/ssc-sources/prepared-clean/libssc'


class WaitSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_only_common_source_changed(self):
        result = P.prepare(SOURCE, self.root / 'source')
        self.assertEqual(result['changed_files'], ['src/libssc-common.c'])
        self.assertEqual(len(result['patch_logs']), 2)
        self.assertFalse(result['device_operations'])
        self.assertFalse(result['hardware_verified'])

    def test_original_tree_is_preserved(self):
        before = P.files(SOURCE)
        P.prepare(SOURCE, self.root / 'source')
        self.assertEqual(P.files(SOURCE), before)

    def test_reference_stage_is_distinct_from_completion_fix(self):
        ref = P.prepare(SOURCE, self.root / 'reference', reference_only=True)
        final = P.prepare(SOURCE, self.root / 'final')
        self.assertEqual(len(ref['patch_logs']), 1)
        self.assertNotEqual(ref['source_hashes']['src/libssc-common.c'],
                            final['source_hashes']['src/libssc-common.c'])

    def test_existing_output_and_source_overlap_are_rejected(self):
        out = self.root / 'exists'
        out.mkdir()
        for target in (out, SOURCE / 'nested'):
            with self.subTest(target=target), self.assertRaises(ValueError):
                P.prepare(SOURCE, target)

    def test_unqualified_base_corrupt_extra_and_link_rejected(self):
        for mode in ('corrupt', 'extra', 'link'):
            source = self.root / mode
            shutil.copytree(SOURCE, source)
            if mode == 'corrupt':
                (source / 'src/libssc-common.c').write_text('altered')
            elif mode == 'extra':
                (source / 'unexpected').write_text('extra')
            else:
                (source / 'src/libssc-common.c').unlink()
                (source / 'src/libssc-common.c').symlink_to(SOURCE / 'src/libssc-common.c')
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                P.prepare(source, self.root / ('out-' + mode))

    def test_reference_provenance_is_explicit(self):
        profile = json.loads((P.BASE / 'libssc-wait.json').read_text())
        self.assertTrue(profile['reference_patch_exact_copy'])
        self.assertEqual(profile['base_version'], '0.4.4')
        self.assertFalse(profile['fixes_SSC_publication'])

    def test_corrupt_patch_rejected_before_staging(self):
        base = self.root / 'recipe'
        base.mkdir()
        shutil.copyfile(P.BASE / 'libssc-wait.json', base / 'libssc-wait.json')
        shutil.copytree(P.BASE / 'patches/libssc', base / 'patches/libssc')
        (base / 'patches/libssc/fix-ssc-sync-wait-busy-loop.patch').write_text('altered')
        output = self.root / 'output'
        with patch.object(P, 'BASE', base), self.assertRaisesRegex(ValueError, 'patch input'):
            P.prepare(SOURCE, output)
        self.assertFalse(output.exists())
