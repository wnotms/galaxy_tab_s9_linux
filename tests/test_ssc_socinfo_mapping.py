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
    def test_native_identity_dependency_is_builtin_and_build_gated(self):
        fragment=(ROOT/'kernel/config/gts9wifi-mainline.fragment').read_text()
        self.assertIn('CONFIG_QCOM_SMEM=y\n',fragment)
        self.assertIn('CONFIG_QCOM_SOCINFO=y\n',fragment)
        build=(ROOT/'scripts/build-kernel.sh').read_text()
        required=build.split('required=(',1)[1].split('\n)',1)[0]
        self.assertIn('    CONFIG_QCOM_SOCINFO\n',required)
        self.assertIn('# CONFIG_HVC_DCC is not set',fragment)

    @staticmethod
    def charging_config(value='y', extra=None):
        spec=importlib.util.spec_from_file_location('socinfo_charging_gate',ROOT/'scripts/verify-x710-charging-profile.py')
        gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
        cfg=gate.STAGE2.CONTAINER.read_config(gate.BASE.read_text())
        cfg.update(CONFIG_CHARGER_SM5440_DIRECT='n',CONFIG_CHARGER_SM5440_FEDORA='y',CONFIG_QCOM_SOCINFO=value)
        cfg.update(extra or {})
        text=''.join(f'# {k} is not set\n' if v=='n' else f'{k}={v}\n' for k,v in cfg.items())
        return gate,text

    def test_explicit_socinfo_gate_accepts_only_reviewed_delta(self):
        gate,text=self.charging_config()
        self.assertFalse(gate.verify(text,profile='sm5440-fedora')['valid'])
        result=gate.verify(text,profile='sm5440-fedora',native_socinfo=True)
        self.assertTrue(result['valid'])
        self.assertTrue(result['native_socinfo_builtin'])
        self.assertEqual(result['unexpected_delta'],{})

    def test_explicit_socinfo_gate_rejects_disabled_or_module(self):
        for value in ('n','m'):
            gate,text=self.charging_config(value)
            with self.subTest(value=value):
                self.assertFalse(gate.verify(text,profile='sm5440-fedora',native_socinfo=True)['valid'])

    def test_socinfo_flag_does_not_admit_hardware_or_dcc_changes(self):
        for extra in (dict(CONFIG_USB_DWC3='n'),dict(CONFIG_HVC_DCC='y'),dict(CONFIG_TYPEC_DP_ALTMODE='y')):
            gate,text=self.charging_config(extra=extra)
            with self.subTest(extra=extra):
                self.assertFalse(gate.verify(text,profile='sm5440-fedora',native_socinfo=True)['valid'])

    def test_historical_charging_only_gate_unchanged(self):
        gate,text=self.charging_config('n')
        self.assertTrue(gate.verify(text,profile='sm5440-fedora')['valid'])

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
