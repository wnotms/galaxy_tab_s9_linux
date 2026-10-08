import importlib.util
from pathlib import Path
import struct
import unittest

SPEC=importlib.util.spec_from_file_location('vendor_sensors',
    Path(__file__).resolve().parents[1]/'userspace/sensors/read-vendor-sensors.py')
M=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def fixture(*,name=b'vendor',count=1,kind=0,target=2048,sectors=4096,source=0):
    size=8*1024*1024
    tables=(struct.pack('<36sIIII',name,1,0,count,0)
            +struct.pack('<QIQI',sectors,kind,target,source)
            +struct.pack('<36sIQ',b'default',0,0)
            +struct.pack('<QIIQ36sI',2048,1024*1024,0,size,b'super',0))
    header=bytearray(128)
    struct.pack_into('<IHHI',header,0,0x414c5030,10,0,128)
    struct.pack_into('<I',header,44,len(tables));header[48:80]=M.sha(tables)
    for pos,offset,step in [(80,0,52),(92,52,24),(104,76,48),(116,124,64)]:
        struct.pack_into('<III',header,pos,offset,1,step)
    header[12:44]=M.sha(header)
    geom=bytearray(52);struct.pack_into('<II',geom,0,0x616c4467,52)
    struct.pack_into('<III',geom,40,4096,1,4096);geom[8:40]=M.sha(geom)
    prefix=bytearray(1024*1024)
    for off in (4096,8192):prefix[off:off+52]=geom
    for off in (12288,16384):prefix[off:off+128+len(tables)]=header+tables
    return prefix,size


class VendorLayoutTests(unittest.TestCase):
    def test_single_extent_vendor(self):
        p,size=fixture();r=M.vendor_extent(p,size)
        self.assertEqual(r['offset'],1024*1024);self.assertEqual(r['bytes'],2*1024*1024)
        self.assertTrue(r['primary_backup_agree'])

    def test_geometry_corruption(self):
        p,size=fixture();p[4104]^=1
        with self.assertRaisesRegex(ValueError,'geometry checksum'):M.vendor_extent(p,size)

    def test_header_corruption(self):
        p,size=fixture();p[12288+12]^=1
        with self.assertRaisesRegex(ValueError,'header checksum'):M.vendor_extent(p,size)

    def test_table_corruption(self):
        p,size=fixture();p[12288+128+1]^=1
        with self.assertRaisesRegex(ValueError,'tables size/checksum'):M.vendor_extent(p,size)

    def test_backup_corruption(self):
        p,size=fixture();p[16384+12]^=1
        with self.assertRaisesRegex(ValueError,'header checksum'):M.vendor_extent(p,size)

    def test_valid_but_disagreeing_backups(self):
        p,size=fixture();other,_=fixture(target=4096)
        p[16384:20480]=other[16384:20480]
        with self.assertRaisesRegex(ValueError,'primary/backup disagree'):M.vendor_extent(p,size)

    def test_ab_partition_refused(self):
        p,size=fixture(name=b'vendor_a')
        with self.assertRaisesRegex(ValueError,'unsuffixed'):M.vendor_extent(p,size)

    def test_fragmented_partition_refused(self):
        p,size=fixture(count=2)
        with self.assertRaisesRegex(ValueError,'one readonly'):M.vendor_extent(p,size)

    def test_zero_or_other_device_extent_refused(self):
        for kind,source in [(1,0),(0,1)]:
            with self.subTest(kind=kind,source=source):
                p,size=fixture(kind=kind,source=source)
                with self.assertRaisesRegex(ValueError,'vendor extent'):M.vendor_extent(p,size)

    def test_out_of_device_or_metadata_overlap_refused(self):
        for target in (0,16384):
            with self.subTest(target=target):
                p,size=fixture(target=target)
                with self.assertRaisesRegex(ValueError,'vendor extent'):M.vendor_extent(p,size)

    def test_device_size_change_refused(self):
        p,size=fixture()
        with self.assertRaisesRegex(ValueError,'identity/size'):M.vendor_extent(p,size+4096)

    def test_short_prefix_refused(self):
        p,size=fixture()
        with self.assertRaisesRegex(ValueError,'short LP'):M.vendor_extent(p[:17000],size)


if __name__ == '__main__':
    unittest.main()
