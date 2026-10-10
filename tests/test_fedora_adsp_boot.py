import copy
import importlib.util
import json
from pathlib import Path
import stat
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('fedora_adsp_boot_test',
    ROOT/'userspace/sensors/fedora_adsp_boot.py')
BOOT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BOOT)


class FedoraAdspBootTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_raw = subprocess.check_output(['lz4', '-dc', str(
            ROOT/'out/boot-bundle-ssc-provider399/source/vendor_ramdisk00')], timeout=10)
        cls.rows = BOOT.parse_cpio(cls.original_raw)
        cls.base = BOOT.TX.archive_files(ROOT/'out/ssc-assets/sensor-assets.tar.gz', BOOT.TX.BASE_SHA)
        cls.new = BOOT.TX.archive_files(ROOT/'out/ssc-fedora-adsp-profile/sensor-assets.tar.gz', BOOT.TX.CANDIDATE_SHA)

    def test_real_original_has_exact_52_firmware_and_three_maps(self):
        files = [r for r in self.rows if stat.S_ISREG(r['fields'][1])]
        self.assertEqual(len(files), 55)
        changed, report = BOOT.replace_pair(self.rows, self.base, self.new)
        self.assertEqual((len(report), sum(r['changed'] for r in report)), (52, 19))
        for before, after in zip(self.rows, changed):
            if 'usr/'+before['name'] in self.new:
                self.assertEqual(after['data'], self.new['usr/'+before['name']]['data'])
                for i in range(13):
                    if i != 6:
                        self.assertEqual(before['fields'][i], after['fields'][i])
            else:
                self.assertEqual(before, after)

    def test_original_and_new_cpio_roundtrip(self):
        self.assertEqual(BOOT.parse_cpio(BOOT.pack_cpio(self.rows)), self.rows)
        changed, _ = BOOT.replace_pair(self.rows, self.base, self.new)
        self.assertEqual(BOOT.parse_cpio(BOOT.pack_cpio(changed)), changed)

    def test_original_firmware_drift_rejected(self):
        rows = copy.deepcopy(self.rows)
        row = next(r for r in rows if r['name'].endswith('adsp.b18'))
        row['data'] = row['data'][:-1]
        with self.assertRaisesRegex(ValueError, 'original differs'):
            BOOT.replace_pair(rows, self.base, self.new)

    def test_missing_unchanged_segment_rejected(self):
        rows = [r for r in self.rows if not r['name'].endswith('adsp.b01')]
        with self.assertRaisesRegex(ValueError, 'firmware/map set'):
            BOOT.replace_pair(rows, self.base, self.new)

    def test_missing_pd_map_rejected(self):
        rows = [r for r in self.rows if not r['name'].endswith('adsps.jsn')]
        with self.assertRaisesRegex(ValueError, 'firmware/map set'):
            BOOT.replace_pair(rows, self.base, self.new)

    def test_unrelated_added_firmware_rejected(self):
        row = copy.deepcopy(self.rows[-1])
        row['name'] = 'lib/firmware/qcom/sm8550/cdsp.mdt'
        with self.assertRaisesRegex(ValueError, 'firmware/map set'):
            BOOT.replace_pair(self.rows+[row], self.base, self.new)

    def test_wrong_candidate_names_rejected(self):
        new = dict(self.new)
        new[BOOT.TX.FW+'adsp.b99'] = new.pop(BOOT.TX.FW+'adsp.b01')
        with self.assertRaisesRegex(ValueError, 'firmware/map set'):
            BOOT.replace_pair(self.rows, self.base, new)

    def test_duplicate_cpio_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unsafe cpio'):
            BOOT.parse_cpio(BOOT.pack_cpio(self.rows+[self.rows[-1]]))

    def test_unsafe_path_rejected(self):
        rows = copy.deepcopy(self.rows)
        rows[-1]['name'] = '../outside'
        with self.assertRaisesRegex(ValueError, 'unsafe cpio'):
            BOOT.parse_cpio(BOOT.pack_cpio(rows))

    def test_symlink_cpio_rejected(self):
        rows = copy.deepcopy(self.rows)
        rows[-1]['fields'][1] = stat.S_IFLNK|0o777
        with self.assertRaisesRegex(ValueError, 'unsafe cpio'):
            BOOT.parse_cpio(BOOT.pack_cpio(rows))

    def test_nonroot_cpio_rejected(self):
        rows = copy.deepcopy(self.rows)
        rows[-1]['fields'][2] = 1000
        with self.assertRaisesRegex(ValueError, 'unsafe cpio'):
            BOOT.parse_cpio(BOOT.pack_cpio(rows))

    def test_short_and_trailerless_cpio_rejected(self):
        with self.assertRaisesRegex(ValueError, 'short cpio|missing cpio'):
            BOOT.parse_cpio(self.original_raw[:1024])

    def test_nonzero_trailing_bytes_rejected(self):
        with self.assertRaisesRegex(ValueError, 'trailing bytes'):
            BOOT.parse_cpio(self.original_raw+b'x')

    def test_actual_compressed_candidate_is_exact_new_pair(self):
        raw = subprocess.check_output(['lz4', '-dc', str(ROOT/'out/boot-bundle-ssc-fedora-adsp/fedora-adsp.lz4')], timeout=10)
        rows, _ = BOOT.replace_pair(self.rows, self.base, self.new)
        self.assertEqual(BOOT.parse_cpio(raw), rows)

    def test_actual_bundle_identity_and_protected_components(self):
        folder = ROOT/'out/boot-bundle-ssc-fedora-adsp'
        report = json.loads((folder/'BUILD.json').read_text())
        self.assertEqual(BOOT.sha(folder/'vendor_boot.img'), report['candidate_vendor_sha256'])
        self.assertEqual((folder/'vendor_boot.img').stat().st_size, 100663296)
        self.assertFalse(report['device_operations'])
        self.assertFalse(report['authentication_verified'])
        self.assertFalse(report['deployment_ready'])
        self.assertFalse(report['kernel_build_executed'])
        self.assertTrue(report['PD_maps_unchanged'])
        for component in ('dtb', 'bootconfig'):
            self.assertEqual(BOOT.sha(folder/'source'/component), BOOT.sha(folder/'verify'/component))
        before, after = report['command_arguments_before'], report['command_arguments_after']
        for flag in ('--vendor_cmdline', '--header_version', '--pagesize', '--ramdisk_type'):
            self.assertEqual(before[before.index(flag)+1], after[after.index(flag)+1])
        self.assertEqual((folder/'avb-verify.stderr').read_text(), '')
        self.assertIn('Successfully verified', (folder/'avb-verify.stdout').read_text())


if __name__ == '__main__':
    unittest.main()
