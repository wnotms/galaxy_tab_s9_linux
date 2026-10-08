"""Host source preparation must reject corrupt/escaping inputs before publication."""
import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "userspace/sensors/prepare.py"
spec = importlib.util.spec_from_file_location("ssc_prepare", SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def archive(entries):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as output:
        for name, content, kind in entries:
            row = tarfile.TarInfo(name)
            if kind == "link":
                row.type = tarfile.SYMTYPE
                row.linkname = "../../escape"
            else:
                row.size = len(content)
            output.addfile(row, io.BytesIO(content))
    return stream.getvalue()


class SourceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cache = self.root / "cache"
        self.cache.mkdir()
        self.output = self.root / "prepared"
        self.data = archive([("demo-1.0/file.c", b"old\n", "file")])
        (self.cache / "demo.tar.gz").write_bytes(self.data)
        self.row = dict(name="demo", version="1.0", filename="demo.tar.gz",
                        archive_root="demo-1.0", bytes=len(self.data),
                        sha256=hashlib.sha256(self.data).hexdigest(), patches=[])
        self.manifest = dict(fedora_commit="pinned", sources=[self.row])

    def prepare(self):
        return m.prepare(self.manifest, self.cache, self.output, self.root)

    def test_prepares_exact_files_without_device_operations(self):
        result = self.prepare()
        self.assertEqual((self.output / "demo/file.c").read_bytes(), b"old\n")
        self.assertFalse(result["device_operations"])
        self.assertFalse(result["build_executed"])
        self.assertEqual(result["sources"][0]["patched_files"]["file.c"], hashlib.sha256(b"old\n").hexdigest())

    def test_source_hash_mismatch_does_not_publish(self):
        (self.cache / "demo.tar.gz").write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_source_size_mismatch_does_not_publish(self):
        self.row["bytes"] += 1
        with self.assertRaisesRegex(ValueError, "size mismatch"):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_rejects_source_symlink(self):
        (self.root / "copy.tar.gz").write_bytes(self.data)
        (self.cache / "demo.tar.gz").unlink()
        (self.cache / "demo.tar.gz").symlink_to(self.root / "copy.tar.gz")
        with self.assertRaisesRegex(ValueError, "regular input"):
            self.prepare()

    def test_rejects_traversal_absolute_other_root_and_links(self):
        for name, kind in [("demo-1.0/../../escape", "file"), ("/escape", "file"),
                           ("other/file", "file"), ("demo-1.0/link", "link")]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                m.members(archive([(name, b"bad", kind)]), "demo-1.0")
        self.assertFalse((self.root / "escape").exists())

    def test_rejects_duplicate_and_empty_archives(self):
        entry = ("demo-1.0/file", b"x", "file")
        for data in (archive([entry, entry]), archive([])):
            with self.assertRaises(ValueError):
                m.members(data, "demo-1.0")

    def add_patch(self, content):
        (self.root / "change.patch").write_bytes(content)
        self.row["patches"] = [dict(path="change.patch", sha256=hashlib.sha256(content).hexdigest())]

    def test_patch_applies_and_records_hash(self):
        self.add_patch(b"--- a/file.c\n+++ b/file.c\n@@ -1 +1 @@\n-old\n+new\n")
        result = self.prepare()
        self.assertEqual((self.output / "demo/file.c").read_bytes(), b"new\n")
        self.assertEqual(result["sources"][0]["patches"][0]["returncode"], 0)

    def test_bad_patch_and_patch_hash_leave_no_published_tree(self):
        self.add_patch(b"--- a/file.c\n+++ b/file.c\n@@ -1 +1 @@\n-missing\n+new\n")
        with self.assertRaisesRegex(ValueError, "patch failed"):
            self.prepare()
        self.assertFalse(self.output.exists())
        (self.root / "change.patch").write_bytes(b"modified")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_preserves_existing_output_and_rejects_duplicate_source(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError, "output already exists"):
            self.prepare()
        self.assertEqual((self.output / "demo/file.c").read_bytes(), b"old\n")
        self.output = self.root / "another"
        self.manifest["sources"].append(self.row.copy())
        with self.assertRaisesRegex(ValueError, "duplicate source"):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_all_inputs_validated_before_any_output(self):
        second = dict(self.row, name="second", sha256="0" * 64)
        self.manifest["sources"].append(second)
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.output.parent.joinpath("prepared").exists())


if __name__ == "__main__":
    unittest.main()
