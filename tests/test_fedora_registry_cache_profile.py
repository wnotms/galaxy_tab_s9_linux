import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'registry_cache_profile_test', ROOT/'userspace/sensors/fedora_registry_cache_profile.py')
PROFILE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROFILE)


class RegistryCacheProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = PROFILE.ARCHIVE.read_archive(
            ROOT/'out/ssc-fedora-adsp-profile/sensor-assets.tar.gz', PROFILE.BASE_SHA)
        cls.fedora = PROFILE.ARCHIVE.read_archive(
            ROOT/'out/ssc-fedora-compare/firmware-samsung-gts9wifi-v2.tar.gz',
            PROFILE.ARCHIVE.FEDORA_SHA, directories=True, owner=(1000,1000))

    def test_real_profile_changes_one_file_and_no_calibration_bytes(self):
        result,report = PROFILE.plan(self.base,self.fedora)
        self.assertEqual([n for n in result if result[n] != self.base[n]], [PROFILE.INPUTS.CACHE])
        self.assertEqual(len(report['changed_fields']),35)
        for n in self.base:
            self.assertEqual(result[n]['mtime'],self.base[n]['mtime'])
            self.assertEqual(result[n]['mode'],self.base[n]['mode'])
        self.assertFalse(report['calibration_input_changed'])
        self.assertFalse(report['device_operations'])
        self.assertFalse(report['deployment_ready'])

    def test_original_inputs_are_not_mutated(self):
        before=copy.deepcopy(self.base)
        PROFILE.plan(self.base,self.fedora)
        self.assertEqual(self.base,before)

    def test_missing_baseline_member_stops(self):
        base=dict(self.base);del base[next(iter(base))]
        with self.assertRaisesRegex(ValueError,'328-file'):
            PROFILE.plan(base,self.fedora)

    def test_reference_config_difference_stops(self):
        fedora=copy.deepcopy(self.fedora)
        fedora[PROFILE.INPUTS.CONFIG+'sns_cm.json']['data']+=b'\n'
        with self.assertRaisesRegex(ValueError,'config differs'):
            PROFILE.plan(self.base,fedora)

    def test_prior_modified_cache_cannot_be_staged_again(self):
        result,_=PROFILE.plan(self.base,self.fedora)
        with self.assertRaisesRegex(ValueError,'cache boundary'):
            PROFILE.plan(result,self.fedora)

    def test_nonzero_reference_cache_not_silently_adopted(self):
        fedora=copy.deepcopy(self.fedora)
        doc=json.loads(fedora[PROFILE.INPUTS.CACHE]['data'])
        doc['sns_reg_config']['/vendor/etc/sensors/config/sns_cm.json']['data']='123'
        fedora[PROFILE.INPUTS.CACHE]['data']=json.dumps(doc).encode()
        with self.assertRaisesRegex(ValueError,'cache boundary'):
            PROFILE.plan(self.base,fedora)

    def test_real_output_roundtrip_matches_exact_plan(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'profile'
            report=PROFILE.stage(ROOT/'out/ssc-fedora-adsp-profile/sensor-assets.tar.gz',
                ROOT/'out/ssc-fedora-compare/firmware-samsung-gts9wifi-v2.tar.gz',out)
            files=PROFILE.ARCHIVE.read_archive(out/'sensor-assets.tar.gz',report['archive_sha256'])
            expected,_=PROFILE.plan(self.base,self.fedora)
            self.assertEqual(files,expected)
            self.assertFalse(report['generated_cache_content_qualified'])
            self.assertFalse(report['physical_persist_changed'])
            with self.assertRaisesRegex(ValueError,'already exists'):
                PROFILE.stage(ROOT/'out/ssc-fedora-adsp-profile/sensor-assets.tar.gz',
                    ROOT/'out/ssc-fedora-compare/firmware-samsung-gts9wifi-v2.tar.gz',out)

    def test_bad_archive_hash_stops_before_output_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            bad=Path(temp)/'bad.tar.gz';bad.write_bytes(b'bad')
            out=Path(temp)/'result'
            with self.assertRaisesRegex(ValueError,'identity'):
                PROFILE.stage(bad,ROOT/'out/ssc-fedora-compare/firmware-samsung-gts9wifi-v2.tar.gz',out)
            self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
