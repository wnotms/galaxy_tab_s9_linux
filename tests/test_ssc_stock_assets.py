import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'userspace/sensors/verify-stock-assets.py'
SPEC = importlib.util.spec_from_file_location('ssc_stock_assets',SCRIPT)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def firmware(name='adsp.mdt', start=0x9ea00000, embedded=False):
    size = 52+4*32
    ident = b'\x7fELF\x01\x01\x01'+b'\0'*9
    header = M.ELF_HEADER.pack(ident,2,164,1,0,52,0,0,52,32,4,0,0,0)
    ph = [(0,0,0,0,size,0,7<<24,0),
          (0,8192,0,0,4,4,2<<24,0),
          (1,size+4 if embedded else 4096,0,start,4,4096,5,4096),
          (1,12288,0,start+4096,0,4096,6,4096)]
    blob = header + b''.join(M.PROGRAM_HEADER.pack(*p) for p in ph) + b'HASH'
    if embedded:
        # Keep the BSS offset out of range: zero-sized entries do not imply split.
        blob += b'DATA'
        b = bytearray(blob);struct.pack_into('<I',b,52+32+4,size);blob=bytes(b)
    return {name:blob,name[:-3]+'b02':b'DATA'}


def registry():
    return {'persist/sensors/registry/registry/sensors_registry':b'',
            'persist/sensors/registry/registry/sns_reg_config':json.dumps({'sns_reg_config':{
                'owner':'NA','/vendor/etc/sensors/config/accelerometer.json':{
                    'type':'int','ver':'0','data':'1640995200'}}}).encode(),
            'persist/sensors/registry/sns_reg_version':b'version=6\0'}


class StockAssetTests(unittest.TestCase):
    def test_split_complete_with_bss_and_number_gap(self):
        r=M.audit_mdt('adsp.mdt',firmware())
        self.assertEqual(r['required_split_files'],['adsp.b02'])
        self.assertEqual(r['memory_bytes'],8192)
        self.assertFalse(r['authentication_verified'])

    def test_missing_segment(self):
        f=firmware();del f['adsp.b02']
        with self.assertRaisesRegex(ValueError,'split segment'):M.audit_mdt('adsp.mdt',f)

    def test_truncated_segment(self):
        f=firmware();f['adsp.b02']=b'X'
        with self.assertRaisesRegex(ValueError,'split segment'):M.audit_mdt('adsp.mdt',f)

    def test_embedded_does_not_require_split_file(self):
        f=firmware(embedded=True);del f['adsp.b02']
        r=M.audit_mdt('adsp.mdt',f)
        self.assertFalse(r['split']);self.assertEqual(r['required_split_files'],[])

    def test_external_hash_required_and_size_checked(self):
        f=firmware();f['adsp.mdt']+=b'padding'
        with self.assertRaisesRegex(ValueError,'b01'):M.audit_mdt('adsp.mdt',f)
        f['adsp.b01']=b'HASH'
        self.assertEqual(M.audit_mdt('adsp.mdt',f)['metadata_location'],'split-hash-segment')

    def test_missing_hash(self):
        f=firmware();b=bytearray(f['adsp.mdt']);struct.pack_into('<I',b,52+32+24,0);f['adsp.mdt']=bytes(b)
        with self.assertRaisesRegex(ValueError,'hash metadata'):M.audit_mdt('adsp.mdt',f)

    def test_truncated_program_table(self):
        f=firmware();f['adsp.mdt']=f['adsp.mdt'][:80]
        with self.assertRaisesRegex(ValueError,'program table'):M.audit_mdt('adsp.mdt',f)

    def test_load_exceeds_memory(self):
        f=firmware();b=bytearray(f['adsp.mdt']);struct.pack_into('<I',b,52+2*32+16,5000);f['adsp.mdt']=bytes(b)
        with self.assertRaisesRegex(ValueError,'load segment'):M.audit_mdt('adsp.mdt',f)

    def test_registry_double_directory_maps_once(self):
        r=M.inspect_registry(registry())
        self.assertEqual(r['copied_registry_mapping']['persist/sensors/registry/registry/sensors_registry'],
                         'sensors/registry/sensors_registry')
        self.assertEqual(r['config_inputs'][0]['required_mtime'],1640995200)
        self.assertFalse(r['timestamp_normalization_allowed'])

    def test_marker_missing(self):
        f=registry();del f['persist/sensors/registry/registry/sensors_registry']
        with self.assertRaisesRegex(ValueError,'marker'):M.inspect_registry(f)

    def test_cache_path_escape(self):
        f=registry();n='persist/sensors/registry/registry/sns_reg_config'
        f[n]=f[n].replace(b'config/accelerometer.json',b'config/../secret.json')
        with self.assertRaisesRegex(ValueError,'input path'):M.inspect_registry(f)

    def archive(self,directory,change=None,extra=None):
        f=registry()
        f.update(firmware('apnhlos/image/adsp.mdt'))
        f.update(firmware('apnhlos/image/adsp_dtb.mdt',0x9e980000))
        manifest=dict(purpose='READ_ONLY_STOCK_SENSOR_ASSETS',firmware_installed=False,
                      remoteproc_started=False,temporary_mounts_removed=True,cleanup_errors=[],
                      skipped_links=[],boot_id='fixture-boot',total_bytes=sum(map(len,f.values())),
                      files={n:dict(bytes=len(b),sha256=M.digest(b),archive_mtime=123) for n,b in f.items()})
        if change:change(manifest,f)
        f['MANIFEST.json']=json.dumps(manifest).encode()
        path=Path(directory)/'assets.tar.gz'
        with tarfile.open(path,'w:gz') as t:
            for n,b in f.items():
                info=tarfile.TarInfo(n);info.size=len(b);info.mtime=123;t.addfile(info,io.BytesIO(b))
            if extra:t.addfile(extra)
        return path,M.digest(path.read_bytes())

    def test_complete_archive_reports_not_deployment_ready(self):
        with tempfile.TemporaryDirectory() as d:
            p,h=self.archive(d);r=M.verify_archive(p,h)
            self.assertFalse(r['device_deployment_ready'])
            self.assertTrue(r['firmware']['adsp.mdt']['existing_reserved_region_fits'])

    def test_archive_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            p,_=self.archive(d)
            with self.assertRaisesRegex(ValueError,'SHA-256'):M.verify_archive(p,'0'*64)

    def test_payload_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            p,h=self.archive(d,lambda m,f:f.update({'apnhlos/image/adsp.b02':b'EVIL'}))
            with self.assertRaisesRegex(ValueError,'identity'):M.verify_archive(p,h)

    def test_missing_manifest_member(self):
        with tempfile.TemporaryDirectory() as d:
            p,h=self.archive(d,lambda m,f:f.pop('apnhlos/image/adsp.b02'))
            with self.assertRaisesRegex(ValueError,'file set'):M.verify_archive(p,h)

    def test_incomplete_cleanup_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p,h=self.archive(d,lambda m,f:m.update(temporary_mounts_removed=False))
            with self.assertRaisesRegex(ValueError,'incomplete'):M.verify_archive(p,h)

    def test_unsafe_archive_members_rejected(self):
        for name,kind in [('../escape',tarfile.REGTYPE),('dsp/link',tarfile.SYMTYPE),
                          ('dsp/device',tarfile.CHRTYPE),('MANIFEST.json',tarfile.REGTYPE)]:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as d:
                extra=tarfile.TarInfo(name);extra.type=kind;extra.linkname='/etc/passwd'
                p,h=self.archive(d,extra=extra)
                with self.assertRaisesRegex(ValueError,'archive member'):M.verify_archive(p,h)


if __name__ == '__main__':
    unittest.main()
