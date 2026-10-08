import hashlib
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('gpu_firmware', ROOT / 'userspace/gnome/prepare-firmware.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def image():
    data = bytearray(512)
    struct.pack_into('<16sHHIIIIIHHHHHH', data, 0, b'\x7fELF\x01\x01\x01' + b'\0' * 9,
                     2, 164, 1, 0, 52, 0, 0, 52, 32, 3, 0, 0, 0)
    for i, values in enumerate([(0, 0, 0, 0, 148, 0, 0, 0),
                                (1, 160, 4096, 4096, 32, 32, 0, 4),
                                (0, 256, 0, 0, 32, 32, 2 << 24, 4)]):
        struct.pack_into('<8I', data, 52 + i * 32, *values)
    return data


class FirmwareTests(unittest.TestCase):
    def test_complete_mbn_keeps_bytes_and_needs_no_split_files(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'source'; source.mkdir()
            rows = []
            for name in p.DESTINATIONS:
                data = bytes(image()) if name.endswith('.mbn') else b'firmware'
                (source / name).write_bytes(data)
                rows.append(dict(filename=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
            output = Path(folder) / 'staged'
            report = p.stage(dict(files=rows, repository='pinned-repo', commit='pin'), source, output)
            self.assertFalse(report['device_operations'])
            self.assertEqual((output / p.DESTINATIONS['a740_zap.mbn']).read_bytes(), bytes(image()))
            with self.assertRaises(ValueError):
                p.stage(dict(files=rows, repository='pinned-repo', commit='pin'), source, output)

    def test_truncated_and_wrong_format_rejected(self):
        for data in (b'', image()[:100], b'not-elf' + image()[7:]):
            with self.assertRaises(ValueError):
                p.validate_zap(data)

    def test_missing_hash_rejected(self):
        data = image(); struct.pack_into('<I', data, 52 + 2 * 32 + 24, 0)
        with self.assertRaises(ValueError):
            p.validate_zap(data)

    def test_split_segment_and_invalid_memory_rejected(self):
        for position, value in ((52 + 32 + 4, 500), (52 + 32 + 20, 16)):
            data = image(); struct.pack_into('<I', data, position, value)
            with self.assertRaises(ValueError):
                p.validate_zap(data)

    def test_program_header_table_bounds_rejected(self):
        data = image(); struct.pack_into('<I', data, 28, 500)
        with self.assertRaises(ValueError):
            p.validate_zap(data)

    def test_wrong_source_set_rejected_without_output(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'out'
            with self.assertRaises(ValueError):
                p.stage(dict(files=[]), Path(folder), output)
            self.assertFalse(output.exists())

    def test_corrupted_source_rejects_entire_set_before_publish(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'source'; source.mkdir()
            rows = []
            for name in p.DESTINATIONS:
                data = bytes(image()) if name.endswith('.mbn') else b'firmware'
                (source / name).write_bytes(data)
                rows.append(dict(filename=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
            (source / 'a740_zap.mbn').write_bytes(b'corrupt')
            output = Path(folder) / 'out'
            with self.assertRaises(ValueError):
                p.stage(dict(files=rows), source, output)
            self.assertFalse(output.exists())
