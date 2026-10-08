import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('ssc_socinfo',ROOT/'userspace/sensors/map-socinfo.py')
M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)


def snapshot(**changes):
    d=dict(boot_id='11111111-2222-3333-4444-555555555555',family='Snapdragon',
           machine='SM8550',soc_id='519',info_fmt='0x00000013',hardware_platform='8',
           hardware_platform_subtype='0',platform_version='65536')
    return dict(d,**changes)


class SocinfoMappingTests(unittest.TestCase):
    def test_vendor_string_and_raw_platform_version(self):
        self.assertEqual(M.translate(snapshot()),dict(soc_id='519\n',hw_platform='MTP\n',
            platform_subtype='Unknown\n',platform_subtype_id='0\n',platform_version='65536\n'))

    def test_qrd_uses_separate_vendor_table(self):
        d=M.translate(snapshot(hardware_platform='11',hardware_platform_subtype='5'))
        self.assertEqual(d['platform_subtype'],'SKUG\n')

    def test_general_subtype(self):
        self.assertEqual(M.translate(snapshot(hardware_platform_subtype='3'))['platform_subtype'],'strange_2a\n')

    def test_unknown_platform_and_sparse_holes_rejected(self):
        for value in ('0','6','12','35','40'):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'platform'):
                M.translate(snapshot(hardware_platform=value))

    def test_invalid_subtype_and_qrd_hole_rejected(self):
        for p,s in (('8','4'),('11','4'),('11','6')):
            with self.subTest(p=p,s=s),self.assertRaisesRegex(ValueError,'subtype'):
                M.translate(snapshot(hardware_platform=p,hardware_platform_subtype=s))

    def test_other_soc_or_board_identity_rejected(self):
        for change in (dict(soc_id='457'),dict(machine='SM8650'),dict(family='other'),dict(boot_id='stale')):
            with self.subTest(change=change),self.assertRaises(ValueError):M.translate(snapshot(**change))

    def test_missing_field_rejected(self):
        for name in ('soc_id','info_fmt','hardware_platform','hardware_platform_subtype','platform_version'):
            d=snapshot();del d[name]
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'missing'):M.translate(d)

    def test_format_bounds(self):
        for fmt in ('5','24','0x10006'):
            with self.subTest(fmt=fmt),self.assertRaisesRegex(ValueError,'format'):
                M.translate(snapshot(info_fmt=fmt))
        for fmt in ('6','23','0x00000017'):
            self.assertEqual(M.translate(snapshot(info_fmt=fmt))['soc_id'],'519\n')

    def test_numeric_types_units_overflow_and_injection_rejected(self):
        for value in (True,1,1.5,'-1','1.5','4294967296','1\nextra','0x10000',''):
            with self.subTest(value=value),self.assertRaises(ValueError):
                M.translate(snapshot(platform_version=value))

    def test_decimal_whitespace_normalization(self):
        self.assertEqual(M.translate(snapshot(platform_version='  00065536\n'))['platform_version'],'65536\n')

    def test_invalid_input_creates_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'mapped'
            with self.assertRaises(ValueError):M.stage(snapshot(soc_id='0'),target)
            self.assertFalse(target.exists())

    def test_output_exact_files_and_existing_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'mapped';report=M.stage(snapshot(),target)
            self.assertFalse(report['device_operations'])
            self.assertFalse(report['physical_identity_verified'])
            self.assertEqual(set(x.name for x in target.iterdir()),set(M.translate(snapshot()))|{'MAPPING.json'})
            with self.assertRaises(FileExistsError):M.stage(snapshot(),target)


if __name__=='__main__':unittest.main()
