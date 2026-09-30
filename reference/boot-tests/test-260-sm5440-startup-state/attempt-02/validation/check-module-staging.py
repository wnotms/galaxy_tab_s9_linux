"""Exercise the real staging transaction on temporary roots, never hardware."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[5]
A = ROOT / 'reference/boot-tests/test-260-sm5440-startup-state'
HELPER = A / 'attempt-01/module-swap.sh'
RELEASE = '7.2.0-rc3-gts9wifi-dirty'


class ModuleStagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.root = self.work / 'root'
        (self.root / 'etc').mkdir(parents=True)
        (self.root / 'etc/machine-id').write_text('3c2a1b8f2d624db4b5ffdc836050fcf6\n')
        self.base = self.root / 'usr/lib/modules'
        self.current = self.base / RELEASE
        self.current.mkdir(parents=True)
        self.old = {}
        for n in range(181):
            name = f'old-{n:03}.ko'
            data = ('old ' + name).encode()
            (self.current / name).write_bytes(data)
            self.old[name] = hashlib.sha256(data).hexdigest()
        self.old_manifest = self.manifest('old.sha256', self.old)
        # Test only the directory transaction. A local sync stub avoids global
        # host/Windows mount waits; the deployed helper still calls real sync.
        bin_dir = self.work / 'bin'; bin_dir.mkdir()
        sync = bin_dir / 'sync'; sync.write_text('#!/bin/sh\nexit 0\n'); sync.chmod(0o755)
        self.env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ['PATH'])

    def manifest(self, name, data):
        p = self.work / name
        p.write_text(''.join(f'{digest}  {key}\n' for key, digest in sorted(data.items())))
        return p

    def call(self, mode, manifest, archive=''):
        return subprocess.run(['sh', str(HELPER), str(self.root), mode,
                               str(manifest), str(archive), str(self.old_manifest)],
                              env=self.env, capture_output=True, timeout=30)

    def current_hashes(self, directory=None):
        directory = directory or self.current
        return {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in directory.rglob('*') if p.is_file()}

    def archive(self, entry):
        p = self.work / 'wrong.tar.gz'
        with tarfile.open(p, 'w:gz') as tar:
            data = b'candidate'
            item = tarfile.TarInfo(entry); item.size = len(data)
            tar.addfile(item, io.BytesIO(data))
        return p

    def test_actual_release_root_candidate_installs_and_restores(self):
        archive = ROOT / 'out/kernel-x710-260-passive/modules-x710.tar.gz'
        self.assertTrue(archive.is_file(), 'qualified candidate archive prerequisite')
        expected = json.loads((A / 'validation/module-hashes.json').read_text())
        manifest = self.manifest('new.sha256', expected)
        result = self.call('install', manifest, archive)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(self.current_hashes(), expected)
        saved = self.base / '.gts9-test260-original'
        self.assertEqual(self.current_hashes(saved), self.old)
        self.assertFalse((self.base / '.gts9-test260-stage').exists())
        result = self.call('restore', self.old_manifest)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(self.current_hashes(), self.old)
        self.assertEqual(self.current_hashes(self.base / '.gts9-test260-tested'), expected)

    def test_wrong_legacy_prefix_refused_before_current_rename(self):
        result = self.call('install', self.old_manifest, self.archive('lib/modules/' + RELEASE + '/new.ko'))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.current_hashes(), self.old)
        self.assertFalse((self.base / '.gts9-test260-original').exists())

    def test_traversal_refused_before_current_rename(self):
        result = self.call('install', self.old_manifest, self.archive(RELEASE + '/../escape'))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.base / '.gts9-test260-stage/lib/modules/escape').exists())
        self.assertEqual(self.current_hashes(), self.old)

    def test_incomplete_candidate_refused_before_current_rename(self):
        result = self.call('install', self.old_manifest, self.archive(RELEASE + '/new.ko'))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.current_hashes(), self.old)
        self.assertFalse((self.base / '.gts9-test260-original').exists())

    def test_existing_backup_is_preserved(self):
        saved = self.base / '.gts9-test260-original'; saved.mkdir()
        marker = saved / 'retained'; marker.write_text('keep')
        result = self.call('install', self.old_manifest, self.archive(RELEASE + '/new.ko'))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(marker.read_text(), 'keep')
        self.assertEqual(self.current_hashes(), self.old)

if __name__ == "__main__":
    unittest.main()
