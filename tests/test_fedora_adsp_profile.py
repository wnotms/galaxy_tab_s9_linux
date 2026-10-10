import copy
import importlib.util
import io
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'fedora_adsp_profile_test', ROOT/'userspace/sensors/fedora_adsp_profile.py')
PROFILE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROFILE)


class FedoraAdspProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = PROFILE.read_archive(ROOT/'out/ssc-assets/sensor-assets.tar.gz', PROFILE.BASE_SHA)
        cls.fedora = PROFILE.read_archive(
            ROOT/'out/ssc-fedora-compare/firmware-samsung-gts9wifi-v2.tar.gz',
            PROFILE.FEDORA_SHA, directories=True, owner=(1000, 1000))

    def test_real_complete_pair_preserves_all_other_assets(self):
        files, report = PROFILE.plan(self.base, self.fedora)
        self.assertEqual((report['firmware_files'], report['changed_files'],
                          report['non_firmware_members_preserved']), (52, 19, 276))
        self.assertEqual(set(files), set(self.base))
        for n, e in files.items():
            self.assertEqual(e, self.fedora[n] | {'mode': self.base[n]['mode']}
                             if PROFILE.PATTERN.fullmatch(n) else self.base[n])
        self.assertFalse(report['authentication_verified'])
        self.assertFalse(report['device_operations'])

    def test_missing_unchanged_segment_rejected(self):
        source = dict(self.fedora)
        del source[PROFILE.FW+'adsp.b02']
        with self.assertRaisesRegex(ValueError, '52-file'):
            PROFILE.plan(self.base, source)

    def test_extra_firmware_segment_rejected(self):
        source = dict(self.fedora)
        source[PROFILE.FW+'adsp.b99'] = source[PROFILE.FW+'adsp.b02']
        with self.assertRaisesRegex(ValueError, '52-file'):
            PROFILE.plan(self.base, source)

    def test_unrelated_fedora_blobs_are_not_copied(self):
        source = dict(self.fedora)
        source['usr/lib/firmware/qcom/sm8550/foreign.mdt'] = {'data': b'foreign', 'mtime': 0, 'mode': 0o644}
        result, _ = PROFILE.plan(self.base, source)
        self.assertNotIn('usr/lib/firmware/qcom/sm8550/foreign.mdt', result)

    def test_wrong_split_length_rejected(self):
        source = copy.deepcopy(self.fedora)
        source[PROFILE.FW+'adsp.b18']['data'] = source[PROFILE.FW+'adsp.b18']['data'][:-1]
        with self.assertRaisesRegex(ValueError, 'wrong-sized'):
            PROFILE.plan(self.base, source)

    def test_wrong_machine_rejected(self):
        source = copy.deepcopy(self.fedora)
        raw = bytearray(source[PROFILE.FW+'adsp.mdt']['data'])
        struct.pack_into('<H', raw, 18, 183)
        source[PROFILE.FW+'adsp.mdt']['data'] = bytes(raw)
        with self.assertRaisesRegex(ValueError, 'machine'):
            PROFILE.plan(self.base, source)

    def test_dtb_envelope_machine_one_is_accepted(self):
        report = PROFILE.firmware_audit(self.fedora)
        self.assertTrue(report['adsp_dtb.mdt']['structurally_complete'])
        self.assertEqual(report['adsp_dtb.mdt']['memory_start'], 0x9e980000)

    def test_changed_carveout_rejected(self):
        source = copy.deepcopy(self.fedora)
        name = PROFILE.FW+'adsp_dtb.mdt'
        raw = bytearray(source[name]['data'])
        off = struct.unpack_from('<I', raw, 28)[0]
        count = struct.unpack_from('<H', raw, 44)[0]
        for i in range(count):
            p = PROFILE.MDT.PROGRAM_HEADER.unpack_from(raw, off + 32*i)
            if p[0] == 1 and p[6] & PROFILE.MDT.TYPE_MASK != PROFILE.MDT.TYPE_HASH and p[5]:
                struct.pack_into('<I', raw, off + 32*i + 12, p[3]+0x1000)
        source[name]['data'] = bytes(raw)
        with self.assertRaisesRegex(ValueError, 'carveout'):
            PROFILE.plan(self.base, source)

    def _unsafe_archive(self, *, name='safe', kind=tarfile.REGTYPE, uid=0, duplicate=False):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'source.tar'
            with tarfile.open(path, 'w') as archive:
                for _ in range(2 if duplicate else 1):
                    member = tarfile.TarInfo(name)
                    member.type, member.uid, member.size = kind, uid, 1 if kind == tarfile.REGTYPE else 0
                    archive.addfile(member, io.BytesIO(b'x') if member.size else None)
            return PROFILE.read_archive(path, PROFILE.digest(path.read_bytes()))

    def test_unsafe_path_rejected(self):
        with self.assertRaisesRegex(ValueError, 'path'):
            self._unsafe_archive(name='../outside')

    def test_duplicate_member_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self._unsafe_archive(duplicate=True)

    def test_symlink_rejected(self):
        with self.assertRaisesRegex(ValueError, 'nonregular'):
            self._unsafe_archive(kind=tarfile.SYMTYPE)

    def test_unexpected_ownership_rejected(self):
        with self.assertRaisesRegex(ValueError, 'ownership'):
            self._unsafe_archive(uid=1000)

    def test_source_identity_rejected_before_parsing(self):
        with self.assertRaisesRegex(ValueError, 'identity'):
            PROFILE.read_archive(ROOT/'out/ssc-assets/sensor-assets.tar.gz', '0'*64)

    def test_real_output_is_root_owned_and_not_deployable(self):
        import json
        folder = ROOT/'out/ssc-fedora-adsp-profile'
        report = json.loads((folder/'PROFILE.json').read_text())
        files = PROFILE.read_archive(folder/'sensor-assets.tar.gz', report['archive_sha256'])
        planned, _ = PROFILE.plan(self.base, self.fedora)
        self.assertEqual(files, planned)
        self.assertFalse(report['deployment_ready'])
        self.assertFalse(report['authentication_verified'])
        self.assertIn('qualified transactional firmware install/restore', report['outstanding'])

    def test_rebuilding_archive_is_deterministic(self):
        with tempfile.TemporaryDirectory() as temp:
            report = PROFILE.stage(
                ROOT/'out/ssc-assets/sensor-assets.tar.gz',
                ROOT/'out/ssc-fedora-compare/firmware-samsung-gts9wifi-v2.tar.gz',
                Path(temp)/'profile')
            self.assertEqual(report['archive_sha256'],
                             'd647dcdf5ecc010080dbd057cec2c9cc66368d9e241cc3883a532e3f648177b3')

    def test_existing_output_is_never_replaced(self):
        with tempfile.TemporaryDirectory() as temp:
            sentinel = Path(temp)/'sensor-assets.tar.gz'
            sentinel.write_bytes(b'prior output')
            with self.assertRaises(FileExistsError):
                PROFILE.stage(
                    ROOT/'out/ssc-assets/sensor-assets.tar.gz',
                    ROOT/'out/ssc-fedora-compare/firmware-samsung-gts9wifi-v2.tar.gz',
                    Path(temp))
            self.assertEqual(sentinel.read_bytes(), b'prior output')


if __name__ == '__main__':
    unittest.main()
