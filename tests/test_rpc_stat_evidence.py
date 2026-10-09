import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('rpc_stat_evidence', ROOT / 'userspace/sensors/rpc_stat_evidence.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
BOOT = '11111111-1111-1111-1111-111111111111'
NAME = '/vendor/etc/sensors/config/test.json'


class StatEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.reference = dict(entries=[dict(virtual_path=NAME, archive_size=123,
            archive_mtime_seconds=1640995200, cache_mtime_seconds=1640995200, mtime_matches=True)])
        self.row = dict(_BOOT_ID=BOOT.replace('-', ''), _SYSTEMD_UNIT=m.UNIT,
                        __MONOTONIC_TIMESTAMP='1000000',
                        MESSAGE='stat(' + NAME + ') -> size=123 mtime=1640995200.000000000')

    def inspect(self, rows=None):
        return m.inspect('\n'.join(json.dumps(row) for row in (rows or [self.row])), BOOT, self.reference)

    def test_complete_matching_metadata_not_a_sensor_pass(self):
        result = self.inspect()
        self.assertTrue(result['complete'])
        self.assertFalse(result['SSC_publication_proved'])
        self.assertFalse(result['accelerometer_sample_proved'])
        self.assertEqual(result['events'][NAME][0]['monotonic_us'], 1000000)

    def test_wrong_size_seconds_or_nanoseconds(self):
        for old, new in [('size=123', 'size=124'), ('1640995200.', '1640995201.'),
                         ('.000000000', '.000000001')]:
            with self.subTest(new=new):
                row = self.row | {'MESSAGE': self.row['MESSAGE'].replace(old, new)}
                self.assertFalse(self.inspect([row])['complete'])

    def test_old_trace_without_metadata_cannot_pass(self):
        result = self.inspect([self.row | {'MESSAGE': 'stat(' + NAME + ')'}])
        self.assertFalse(result['complete']); self.assertTrue(result['faults'])

    def test_success_cannot_hide_later_error_or_changed_metadata(self):
        for message in ['Could not stat ' + NAME + ': Input/output error',
                        'Could not open ' + NAME + ': No such file or directory',
                        self.row['MESSAGE'].replace('size=123', 'size=456')]:
            with self.subTest(message=message):
                self.assertFalse(self.inspect([self.row, self.row | {'MESSAGE': message}])['complete'])

    def test_other_unit_cannot_supply_sensor_evidence(self):
        self.assertFalse(self.inspect([self.row | {'_SYSTEMD_UNIT': 'hexagonrpcd-adsp-rootpd.service'}])['complete'])

    def test_wrong_boot_or_missing_boot(self):
        for boot in ['22222222-2222-2222-2222-222222222222', None]:
            row = self.row.copy()
            if boot: row['_BOOT_ID'] = boot
            else: row.pop('_BOOT_ID')
            with self.assertRaises((ValueError, KeyError)): self.inspect([row])

    def test_empty_or_malformed_journal(self):
        for raw in ['', 'not-json']:
            with self.assertRaises(ValueError): m.inspect(raw, BOOT, self.reference)

    def test_missing_reference_entry_is_incomplete(self):
        self.reference['entries'].append(self.reference['entries'][0] | {'virtual_path': NAME.replace('test', 'another')})
        self.assertFalse(self.inspect()['complete'])

    def test_duplicate_or_unmatched_reference_rejected(self):
        original = copy.deepcopy(self.reference)
        self.reference['entries'].append(self.reference['entries'][0])
        with self.assertRaises(ValueError): self.inspect()
        self.reference = original
        self.reference['entries'][0]['mtime_matches'] = False
        with self.assertRaises(ValueError): self.inspect()

    def test_duplicate_valid_events_retained(self):
        result = self.inspect([self.row, self.row | {'__MONOTONIC_TIMESTAMP': '2000000'}])
        self.assertTrue(result['complete']); self.assertEqual(len(result['events'][NAME]), 2)

    def test_missing_or_negative_source_timestamp(self):
        for value in [None, '-1']:
            row = self.row.copy()
            if value: row['__MONOTONIC_TIMESTAMP'] = value
            else: row.pop('__MONOTONIC_TIMESTAMP')
            with self.assertRaises((ValueError, KeyError)): self.inspect([row])

    def test_unrelated_oemconfig_lookup_not_mislabeled_config_failure(self):
        result = self.inspect([self.row, self.row | {'MESSAGE': 'Could not open oemconfig.so: No such file or directory'}])
        self.assertTrue(result['complete'])


if __name__ == '__main__': unittest.main()
