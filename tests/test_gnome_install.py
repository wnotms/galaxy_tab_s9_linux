import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
with patch.object(sys, 'path', [str(ROOT / 'userspace/gnome')] + sys.path):
    spec = importlib.util.spec_from_file_location('gnome_install', ROOT / 'userspace/gnome/install.py')
    p = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p)


class InstallTests(unittest.TestCase):
    def test_local_only_apt_sources_and_absolute_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            argv = p.local_apt_argv(root, self.rows(), root)
            self.assertNotIn('--no-download', argv)
            self.assertIn('Dir::Etc::sourcelist=' + str(root / 'empty-sources.list'), argv)
            self.assertIn('Dir::Etc::sourceparts=' + str(root / 'empty-sources.d'), argv)
            self.assertEqual((root / 'empty-sources.list').read_text(), '')
            self.assertEqual(list((root / 'empty-sources.d').iterdir()), [])
            self.assertEqual(argv[-1], str(root / 'foo_1_arm64.deb'))

    def test_actual_apt_simulates_local_archive_with_repositories_disabled(self):
        # Real APT acquisition semantics were missed by the original mock. This
        # builds a harmless all-arch dummy and ONLY simulates, never installs it.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);control = root / 'pkg/DEBIAN';control.mkdir(parents=True)
            (control / 'control').write_text('Package: gts9-gnome-offline-test\nVersion: 1\n'
                'Architecture: all\nMaintainer: Test <test@example.invalid>\nDescription: simulation only\n')
            archive = root / 'dummy.deb'
            subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(control.parent),
                            str(archive)], check=True, capture_output=True)
            rows = [dict(package='gts9-gnome-offline-test', version='1', filename=archive.name)]
            argv = p.local_apt_argv(root, rows, root)
            result = subprocess.run(argv[:1] + ['--simulate'] + argv[1:],
                capture_output=True, text=True, timeout=20, env=dict(os.environ, LC_ALL='C'))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(p.verify_simulation(result.stdout, rows, {}), 1)

    def rows(self):
        return [dict(package='foo', version='1', architecture='arm64', filename='foo_1_arm64.deb',
                     bytes=3, sha256=hashlib.sha256(b'deb').hexdigest(), url='https://deb.debian.org/foo.deb')]

    def test_exact_new_package_plan(self):
        self.assertEqual(p.verify_simulation('Inst foo (1 Debian:13 [arm64])\n', self.rows(), {}), 1)
        self.assertEqual(p.verify_simulation('', self.rows(), {'foo': '1'}), 0)

    def test_removal_upgrade_extra_missing_and_malformed_plan_rejected(self):
        for text, installed in [('Remv bar [1]\n', {}),
                                ('Inst foo [0] (1 Debian [arm64])', {}),
                                ('Inst foo [0] (1 Debian [arm64])', {'foo': '0'}),
                                ('Inst foo (2 Debian [arm64])', {}),
                                ('Inst foo (1 Debian [arm64])\nInst bar (1 Debian [arm64])', {}),
                                ('', {}), ('Inst foo unrecognized', {})]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                p.verify_simulation(text, self.rows(), installed)

    def test_only_fully_installed_versions_are_accepted(self):
        self.assertEqual(p.installed_versions('foo\t1\tinstalled\nbar\t2\tunpacked\n'), {'foo': '1'})

    def test_package_and_firmware_cache_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);cache = root / 'cache';cache.mkdir()
            (cache / 'foo_1_arm64.deb').write_bytes(b'deb')
            firmware = root / 'firmware';firmware.mkdir();blobs = []
            for name in p.FIRMWARE:
                path = firmware / name;path.parent.mkdir(parents=True, exist_ok=True);path.write_bytes(b'fw')
                blobs.append(dict(destination=name, bytes=2, sha256=hashlib.sha256(b'fw').hexdigest()))
            (firmware / 'PREPARED.json').write_text(json.dumps(dict(files=blobs)))
            manifest = dict(packages=self.rows(), package_count=1, download_bytes=3)
            result = p.plan(manifest, cache, firmware)
            self.assertFalse(result['device_operations'])
            (firmware / p.FIRMWARE[0]).write_bytes(b'bad')
            with self.assertRaises(ValueError):
                p.plan(manifest, cache, firmware)

    def test_policy_absent_restored_to_absent(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder);policy = directory / 'policy-rc.d'
            with p.deny_service_actions(directory):
                self.assertIn('exit 101', policy.read_text())
                self.assertEqual(stat.S_IMODE(policy.stat().st_mode), 0o755)
            self.assertFalse(policy.exists())

    def test_original_policy_mode_and_bytes_restored_on_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder);policy = directory / 'policy-rc.d'
            policy.write_text('original');policy.chmod(0o700)
            with self.assertRaises(RuntimeError):
                with p.deny_service_actions(directory):
                    raise RuntimeError('APT failed')
            self.assertEqual(policy.read_text(), 'original')
            self.assertEqual(stat.S_IMODE(policy.stat().st_mode), 0o700)

    def test_symlink_policy_preserved_and_stale_backup_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder);source = directory / 'existing';source.write_text('original')
            policy = directory / 'policy-rc.d';policy.symlink_to(source)
            with p.deny_service_actions(directory):
                self.assertFalse(policy.is_symlink())
            self.assertEqual(policy.readlink(), source)
            self.assertEqual(source.read_text(), 'original')
            (directory / 'policy-rc.d.gts9-gnome-backup').write_text('unfinished')
            with self.assertRaises(ValueError):
                with p.deny_service_actions(directory):
                    self.fail('must reject unfinished transaction')
            self.assertTrue(policy.is_symlink())

    def test_all_actual_gdm_entry_points_remain_masked(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            p.mask_gdm(directory)
            for name in ('gdm.service', 'gdm3.service', 'display-manager.service'):
                self.assertEqual((directory / name).readlink(), Path('/dev/null'))

    def test_existing_unit_override_is_preserved_before_any_mask(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder);original = directory / 'display-manager.service';original.write_text('owner')
            with self.assertRaises(ValueError):
                p.mask_gdm(directory)
            self.assertEqual(original.read_text(), 'owner')
            self.assertFalse((directory / 'gdm.service').is_symlink())

    def test_partial_mask_creation_failure_rolls_back_created_masks(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder);real = Path.symlink_to
            def fail(path, target):
                if path.name == 'gdm3.service':
                    raise OSError('write failure')
                real(path, target)
            with patch.object(Path, 'symlink_to', fail), self.assertRaises(OSError):
                p.mask_gdm(directory)
            self.assertEqual(list(directory.iterdir()), [])

    def test_wrong_target_is_rejected_without_evidence_or_mutation(self):
        with patch.object(Path, 'read_text', return_value='be1baaaa-47fc-41f5-8255-8f7092c01653'), \
             patch.object(Path, 'read_bytes', return_value=b'samsung,gts9wifi\0'), \
             patch.object(p.platform, 'machine', return_value='x86_64'), \
             self.assertRaises(ValueError):
            p.target_identity('be1baaaa-47fc-41f5-8255-8f7092c01653')

    def workflow(self, root, fail_apt=False, bad_gdm=False):
        cache = root / 'cache';cache.mkdir()
        firmware = root / 'firmware';firmware.mkdir();blobs = []
        for name in p.FIRMWARE:
            path = firmware / name;path.parent.mkdir(parents=True, exist_ok=True);path.write_bytes(b'fw')
            blobs.append(dict(destination=name, bytes=2, sha256=hashlib.sha256(b'fw').hexdigest()))
        policy = root / 'usr/sbin/policy-rc.d';policy.parent.mkdir(parents=True);policy.write_text('owner')
        evidence = root / 'evidence';seen = []
        def fake_run(argv, folder, name, check=True):
            seen.append(name)
            output, status = '', 0
            if name == 'packages-before': output = 'existing\t7\tinstalled\n'
            if name == 'gdm-before': output, status = ('inactive\n' * 3, 3) if not bad_gdm else ('', 1)
            if name == 'apt-simulation': output = 'Inst foo (1 Debian [arm64])\n'
            if name == 'apt-install':
                self.assertIn('exit 101', policy.read_text())
                for unit in p.GDM_UNITS:
                    self.assertEqual(str((root / 'etc/systemd/system' / unit).readlink()), '/dev/null')
                if fail_apt: raise RuntimeError('mock APT failure')
            if name == 'packages-after': output = 'existing\t7\tinstalled\nfoo\t1\tinstalled\n'
            if name == 'gdm-state': output, status = 'inactive\n', 3
            return subprocess.CompletedProcess(argv, status, stdout=output, stderr='')
        def target_path(name):
            path = Path(name)
            return root / str(path).lstrip('/') if path.is_absolute() else path
        with patch.object(p, 'target_identity', return_value='test-boot'), \
             patch.object(p, 'Path', target_path), patch.object(p, 'run', fake_run):
            try:
                p.install(dict(packages=self.rows(), firmware=blobs), cache, firmware, evidence, 'test-boot')
            except (ValueError, RuntimeError):
                if not (fail_apt or bad_gdm): raise
        self.assertEqual(policy.read_text(), 'owner')
        return json.loads((evidence / 'summary.json').read_text()), seen

    def test_successful_mock_install_keeps_gdm_masks_and_does_not_start_gui(self):
        with tempfile.TemporaryDirectory() as folder:
            summary, seen = self.workflow(Path(folder))
            self.assertEqual(summary['verdict'], 'INSTALLED_GDM_MASKED_HARDWARE_NOT_ACCEPTED')
            self.assertEqual(len(summary['masks']), 3)
            self.assertFalse(summary['gdm_started'])
            self.assertIn('apt-install', seen)

    def test_apt_failure_restores_policy_keeps_guard_and_records_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            summary, seen = self.workflow(Path(folder), fail_apt=True)
            self.assertEqual(summary['verdict'], 'STOP_INSTALLATION_GDM_GUARD_RETAINED')
            self.assertEqual(len(summary['masks']), 3)
            self.assertNotIn('packages-after', seen)

    def test_missing_systemd_response_stops_before_any_installation(self):
        with tempfile.TemporaryDirectory() as folder:
            summary, seen = self.workflow(Path(folder), bad_gdm=True)
            self.assertEqual(summary['verdict'], 'STOP_BEFORE_INSTALLATION')
            self.assertEqual(summary['masks'], [])
            self.assertNotIn('apt-install', seen)
