"""Offline source/target admission checks; no Docker or tablet is needed."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1] / 'userspace/sensors'
sys.path.insert(0, str(BASE))
spec = importlib.util.spec_from_file_location('ssc_build', BASE / 'build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class StageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.stage = Path(self.temporary.name)
        self.runtime = ['usr/bin/pd-mapper', 'usr/bin/ssccli', 'usr/bin/monitor-sensor',
                        'usr/bin/hexagonrpcd', 'usr/libexec/iio-sensor-proxy']
        self.elf = b'\x7fELF\x02\x01' + bytes(12) + (183).to_bytes(2, 'little')
        for name in self.runtime:
            path = self.stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(self.elf)

    def test_arm64_runtime_set(self):
        report = build.inspect_stage(self.stage)
        self.assertEqual(set(report['elf_files']), set(self.runtime))
        self.assertEqual(len(report['files']), 5)

    def test_missing_executable(self):
        (self.stage / self.runtime[0]).unlink()
        with self.assertRaisesRegex(ValueError, 'missing ARM64'):
            build.inspect_stage(self.stage)

    def test_x86_64_rejected(self):
        (self.stage / self.runtime[0]).write_bytes(self.elf[:18] + (62).to_bytes(2, 'little'))
        with self.assertRaisesRegex(ValueError, 'not little-endian ARM64'):
            build.inspect_stage(self.stage)

    def test_wrong_elf_class_endian(self):
        for identity in [b'\x01\x01', b'\x02\x02']:
            (self.stage / self.runtime[0]).write_bytes(self.elf[:4] + identity + self.elf[6:])
            with self.assertRaises(ValueError):
                build.inspect_stage(self.stage)

    def test_service_path(self):
        path = self.stage / 'usr/lib/aarch64-linux-gnu/systemd/system/hexagonrpcd.service'
        path.parent.mkdir(parents=True)
        path.write_text('[Service]\n')
        with self.assertRaisesRegex(ValueError, 'unit path'):
            build.inspect_stage(self.stage)

    def test_symlink_escape(self):
        (self.stage / 'escape').symlink_to('/etc/passwd')
        with self.assertRaisesRegex(ValueError, 'escapes'):
            build.inspect_stage(self.stage)

    def test_relative_library_link(self):
        (self.stage / 'lib.so.2').write_bytes(self.elf)
        (self.stage / 'lib.so').symlink_to('lib.so.2')
        self.assertIn('lib.so.2', build.inspect_stage(self.stage)['elf_files'])

    def test_enabled_unit_rejected(self):
        unit = self.stage / 'usr/lib/systemd/system/sensor.service'
        unit.parent.mkdir(parents=True)
        unit.write_text('[Service]\n')
        link = unit.parent / 'multi-user.target.wants/sensor.service'
        link.parent.mkdir()
        link.symlink_to('../sensor.service')
        with self.assertRaisesRegex(ValueError, 'must not enable'):
            build.inspect_stage(self.stage)


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.tree = self.base / 'tree'
        root = self.tree / 'libssc'
        root.mkdir(parents=True)
        (root / 'a.c').write_text('original\n')
        row = dict(name='libssc', version='0.4.4', sha256='archive', patches=[])
        self.manifest = dict(fedora_commit='pinned', sources=[row])
        self.report = dict(fedora_commit='pinned', sources=[dict(name='libssc', version='0.4.4',
            archive_sha256='archive', patches=[], patched_files={'a.c': build.digest(root / 'a.c')})])
        (self.base / 'sources.json').write_text(json.dumps(self.manifest))
        self.save()

    def save(self):
        (self.tree / 'PREPARED.json').write_text(json.dumps(self.report))

    def verify(self):
        with patch.object(build, 'BASE', self.base):
            return build.verify_sources(self.tree)

    def test_verified_source(self):
        self.assertEqual(self.verify()['fedora_commit'], 'pinned')

    def test_unrelated_prepare_module_cannot_override_source_validation(self):
        unrelated = types.ModuleType('prepare')
        # GNOME has a same-named module without relative(). Combined discovery
        # must not replace the sensor validator with that cached module.
        with patch.dict(sys.modules, {'prepare': unrelated}):
            self.assertEqual(self.verify()['fedora_commit'], 'pinned')

    def test_source_changed(self):
        (self.tree / 'libssc/a.c').write_text('changed\n')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.verify()

    def test_extra_file(self):
        (self.tree / 'libssc/extra').touch()
        with self.assertRaisesRegex(ValueError, 'file set'):
            self.verify()

    def test_duplicate_component(self):
        self.report['sources'] *= 2
        self.save()
        with self.assertRaisesRegex(ValueError, 'source set'):
            self.verify()

    def test_archive_identity(self):
        self.report['sources'][0]['archive_sha256'] = 'different'
        self.save()
        with self.assertRaisesRegex(ValueError, 'archive mismatch'):
            self.verify()

    def test_source_link(self):
        target = self.tree / 'libssc/a.c'
        target.unlink()
        target.symlink_to('/etc/passwd')
        with self.assertRaisesRegex(ValueError, 'links'):
            self.verify()


if __name__ == '__main__':
    unittest.main()
