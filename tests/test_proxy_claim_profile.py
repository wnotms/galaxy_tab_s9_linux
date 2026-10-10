"""Strict composition of the early-claim repair; no tablet or D-Bus access."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('proxy_claim_test', ROOT / 'userspace/sensors/proxy_claim_profile.py')
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)
SOURCE = ROOT / 'out/ssc-sources/prepared-clean/iio-sensor-proxy'


class ClaimSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_exact_one_file_composition(self):
        result = P.prepare(SOURCE, self.root / 'source')
        self.assertEqual(result['changed_files'], ['src/iio-sensor-proxy.c'])
        self.assertFalse(result['device_operations'])
        self.assertFalse(result['hardware_verified'])

    def test_original_fedora_tree_is_preserved(self):
        before = P.HELPER.files(SOURCE)
        P.prepare(SOURCE, self.root / 'source')
        self.assertEqual(before, P.HELPER.files(SOURCE))

    def test_existing_and_overlapping_output_rejected(self):
        out = self.root / 'exists'
        out.mkdir()
        for target in (out, SOURCE / 'nested'):
            with self.subTest(target=target), self.assertRaises(ValueError):
                P.prepare(SOURCE, target)

    def test_source_corruption_extra_file_and_link_rejected(self):
        for mode in ('corrupt', 'extra', 'link'):
            source = self.root / mode
            shutil.copytree(SOURCE, source)
            if mode == 'corrupt':
                (source / 'src/iio-sensor-proxy.c').write_text('altered')
            elif mode == 'extra':
                (source / 'unexpected').write_text('extra')
            else:
                (source / 'src/iio-sensor-proxy.c').unlink()
                (source / 'src/iio-sensor-proxy.c').symlink_to(SOURCE / 'src/iio-sensor-proxy.c')
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                P.prepare(source, self.root / ('out-' + mode))

    def test_adapted_and_reference_patch_hashes_required(self):
        for name in ('handle-early-ssc-claims.patch', 'reference-early-ssc-claim-race.patch'):
            base = self.root / name
            base.mkdir()
            shutil.copyfile(P.BASE / 'proxy-claim.json', base / 'proxy-claim.json')
            shutil.copytree(P.BASE / 'patches/iio-sensor-proxy', base / 'patches/iio-sensor-proxy')
            (base / 'patches/iio-sensor-proxy' / name).write_text('altered')
            out = self.root / ('out-' + name)
            with self.subTest(name=name), patch.object(P, 'BASE', base), self.assertRaises(ValueError):
                P.prepare(SOURCE, out)
            self.assertFalse(out.exists())

    def test_profile_does_not_claim_firmware_repair(self):
        profile = json.loads((P.BASE / 'proxy-claim.json').read_text())
        self.assertFalse(profile['fixes_SSC_publication'])
        self.assertEqual(profile['base_version'], '3.9')
