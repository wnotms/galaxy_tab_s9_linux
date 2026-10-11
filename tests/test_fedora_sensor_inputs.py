import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'fedora_sensor_inputs_test', ROOT/'userspace/sensors/fedora_sensor_inputs.py')
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class FedoraSensorInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.current = AUDIT.ARCHIVE.read_archive(
            ROOT/'out/ssc-assets/sensor-assets.tar.gz', AUDIT.ARCHIVE.BASE_SHA)
        cls.fedora = AUDIT.ARCHIVE.read_archive(
            ROOT/'out/ssc-fedora-compare/firmware-samsung-gts9wifi-v2.tar.gz',
            AUDIT.ARCHIVE.FEDORA_SHA, directories=True, owner=(1000, 1000))

    def test_real_config_and_version_bytes_match(self):
        report = AUDIT.compare(self.current, self.fedora)
        self.assertTrue(report['all_config_bytes_equal'])
        self.assertTrue(report['registry_markers_equal'])
        self.assertEqual(report['config_count'], 35)
        self.assertFalse(report['device_operations'])
        self.assertFalse(report['deployment_ready'])
        self.assertFalse(report['SSC_rootcause_proved'])

    def test_real_cache_difference_retained(self):
        report = AUDIT.compare(self.current, self.fedora)
        self.assertEqual({r['cache_seconds'] for r in report['current_mtime_cache']}, {1640995200})
        self.assertTrue(all(r['cache_matches_archive'] for r in report['current_mtime_cache']))
        self.assertEqual({r['cache_seconds'] for r in report['fedora_mtime_cache']}, {0})
        self.assertFalse(report['DSP_reparse_observed'])
        self.assertFalse(report['registry_reset_performed'])

    def test_real_factory_data_not_claimed_interchangeable(self):
        rows = {r['path']:r for r in AUDIT.compare(self.current, self.fedora)['rows']}
        row = rows[AUDIT.PREFIX+'sensors/registry/lsm6dso_0_platform.accel.fac_cal.bias']
        self.assertEqual(row['category'], 'calibration-or-placement-preserve-device')
        self.assertEqual(row['comparison'], 'bytes-different')
        self.assertFalse(row['json_equal'])

    def test_extra_current_library_is_not_missing_fedora_requirement(self):
        rows = {r['path']:r for r in AUDIT.compare(self.current, self.fedora)['rows']}
        row = rows[AUDIT.PREFIX+'dsp/adsp/fastrpc_shell_0']
        self.assertTrue(row['current_present'])
        self.assertFalse(row['fedora_present'])
        self.assertEqual(row['comparison'], 'member-set-difference')

    def test_fedora_soc_files_are_reference_values(self):
        self.assertEqual(self.fedora[AUDIT.PREFIX+'socinfo/platform_version']['data'], b'0\n')
        self.assertEqual(AUDIT.category(AUDIT.PREFIX+'socinfo/platform_version'),
                         'identity-reference-not-device-measurement')

    def test_nonstandard_vendor_json_is_not_repaired(self):
        rows = {r['path']:r for r in AUDIT.compare(self.current, self.fedora)['rows']}
        row = rows[AUDIT.PREFIX+'sensors/registry/ak0991x_0_platform.mag.fac_cal.corr_mat']
        self.assertFalse(row['strict_json_comparable'])
        self.assertIsNone(row['json_equal'])

    def test_key_order_does_not_fake_semantic_difference(self):
        self.assertEqual(AUDIT.fields(AUDIT.strict_json(b'{"a":1,"b":2}'),
                                      AUDIT.strict_json(b'{"b":2,"a":1}')), [])

    def test_strings_and_numbers_are_not_coerced(self):
        self.assertTrue(AUDIT.fields({'data':'10'}, {'data':'10.0'}))
        self.assertTrue(AUDIT.fields({'data':True}, {'data':1}))

    def test_missing_and_null_are_distinguished(self):
        changes = AUDIT.fields({}, {'data':None})
        self.assertFalse(changes[0]['before_present'])
        self.assertTrue(changes[0]['after_present'])

    def test_duplicate_keys_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            AUDIT.strict_json(b'{"a":1,"a":2}')

    def test_nonfinite_json_rejected(self):
        with self.assertRaisesRegex(ValueError, 'nonfinite'):
            AUDIT.strict_json(b'{"a":NaN}')

    def test_missing_config_rejected(self):
        other = dict(self.fedora)
        del other[AUDIT.CONFIG+'sns_cm.json']
        with self.assertRaisesRegex(ValueError, '35 config'):
            AUDIT.compare(self.current, other)

    def test_missing_marker_rejected(self):
        other = dict(self.fedora)
        del other[AUDIT.PREFIX+'sensors/sns_reg_version']
        with self.assertRaisesRegex(ValueError, 'marker'):
            AUDIT.compare(self.current, other)

    def test_partial_cache_rejected(self):
        other = copy.deepcopy(self.current)
        doc = json.loads(other[AUDIT.CACHE]['data'])
        del doc['sns_reg_config']['/vendor/etc/sensors/config/sns_cm.json']
        other[AUDIT.CACHE]['data'] = json.dumps(doc).encode()
        with self.assertRaisesRegex(ValueError, 'coverage'):
            AUDIT.cache_map(other)

    def test_negative_cache_timestamp_rejected(self):
        other = copy.deepcopy(self.current)
        doc = json.loads(other[AUDIT.CACHE]['data'])
        doc['sns_reg_config']['/vendor/etc/sensors/config/sns_cm.json']['data'] = '-1'
        other[AUDIT.CACHE]['data'] = json.dumps(doc).encode()
        with self.assertRaisesRegex(ValueError, 'entry'):
            AUDIT.cache_map(other)

    def test_comparison_leaves_every_input_byte_and_metadata_unchanged(self):
        a,b = copy.deepcopy(self.current), copy.deepcopy(self.fedora)
        AUDIT.compare(self.current, self.fedora)
        self.assertEqual(self.current, a)
        self.assertEqual(self.fedora, b)


if __name__ == '__main__':
    unittest.main()
