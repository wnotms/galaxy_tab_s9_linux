import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('gnome_prepare', ROOT / 'userspace/gnome/prepare.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class PreparationTests(unittest.TestCase):
    def row(self):
        return dict(filename='test_1_arm64.deb', architecture='arm64',
                    url='https://deb.debian.org/test.deb', bytes=3,
                    sha256=hashlib.sha256(b'deb').hexdigest())

    def test_manifest_rejects_wrong_architecture_path_and_hash(self):
        for key, value in [('architecture', 'amd64'), ('filename', '../test.deb'),
                           ('sha256', 'unknown'), ('bytes', True),
                           ('url', 'http://example.com/test.deb')]:
            row = dict(self.row(), **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                p.validate(dict(packages=[row], package_count=1, download_bytes=3))

    def test_duplicate_names_and_wrong_total_rejected(self):
        for rows, count, total in [([self.row()] * 2, 2, 6),
                                   ([self.row()], 2, 3), ([self.row()], 1, 4)]:
            with self.assertRaises(ValueError):
                p.validate(dict(packages=rows, package_count=count, download_bytes=total))

    def test_download_verified_and_reused_without_fetch(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            self.assertEqual(p.fetch(self.row(), output, lambda *a, **k: io.BytesIO(b'deb'))['status'], 'downloaded')
            def forbidden(*a, **k):
                self.fail('verified cache must not redownload')
            self.assertEqual(p.fetch(self.row(), output, forbidden)['status'], 'reused')

    def test_invalid_download_is_not_published(self):
        for data in (b'bad', b'deb-extra', b'd'):
            with tempfile.TemporaryDirectory() as folder:
                output = Path(folder)
                with self.assertRaises(ValueError):
                    p.fetch(self.row(), output, lambda *a, **k: io.BytesIO(data))
                self.assertEqual(list(output.iterdir()), [])

    def test_existing_mismatch_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder);target = output / self.row()['filename']
            target.write_bytes(b'bad')
            with self.assertRaises(ValueError):
                p.fetch(self.row(), output)
            self.assertEqual(target.read_bytes(), b'bad')

    def test_symlink_is_not_an_accepted_cache_entry(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder);source = output / 'source';source.write_bytes(b'deb')
            (output / self.row()['filename']).symlink_to(source)
            with self.assertRaises(ValueError):
                p.fetch(self.row(), output)
