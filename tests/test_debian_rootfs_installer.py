"""Host checks for the reproducible Debian rootfs overlay installer."""
import hashlib
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASH = shutil.which('bash') or '/bin/bash'
INSTALLER = ROOT / 'scripts' / 'install-debian-rootfs.sh'
OVERLAY = ROOT / 'rootfs-overlay'
BUILDER = ROOT / 'scripts' / 'build-bringup-initramfs.sh'


def run_installer(*args, env=None, cwd=None):
    environment = dict(os.environ)
    if env:
        environment.update(env)
    return subprocess.run([BASH, str(INSTALLER), *args],
                          env=environment, cwd=cwd, text=True,
                          capture_output=True, check=False)


def snapshot(tree):
    """Relative path -> (type, mode, sha256 or symlink target)."""
    tree = Path(tree)
    entries = {}
    for path in sorted(tree.rglob('*')):
        rel = path.relative_to(tree).as_posix()
        info = path.lstat()
        mode = stat.S_IMODE(info.st_mode)
        if path.is_symlink():
            entries[rel] = ('link', mode, os.readlink(path))
        elif path.is_dir():
            entries[rel] = ('dir', mode, '')
        else:
            entries[rel] = ('file', mode,
                            hashlib.sha256(path.read_bytes()).hexdigest())
    return entries


class DebianRootfsInstaller(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.target = self.root / 'debian'
        (self.target / 'etc' / 'systemd').mkdir(parents=True)
        (self.target / 'etc' / 'os-release').write_text('ID=debian\n')
        (self.target / 'usr' / 'lib' / 'systemd' / 'system').mkdir(parents=True)
        # A real Debian rootfs has the template the ttyGS0 console instantiates.
        (self.target / 'usr/lib/systemd/system/serial-getty@.service').write_text(
            '[Unit]\nDescription=Serial Getty on %I\n[Service]\n')
        # And it is usr-merged: /lib, /bin and /sbin are symlinks into /usr.
        for link in ('lib', 'bin', 'sbin'):
            (self.target / link).symlink_to(f'usr/{link}')
        (self.target / 'usr/lib/systemd/systemd').write_text('systemd\n')
        (self.target / 'usr/lib/systemd/systemd').chmod(0o755)

    def install(self, *args, **kwargs):
        return run_installer('--skip-modules', '--skip-firmware',
                             str(self.target), *args, **kwargs)

    def test_installs_the_userspace_and_enables_every_unit(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        for helper in ('gts9-record-boot-stage', 'gts9-record-poweroff-stage',
                       'gts9-record-debian-stage', 'gts9-usb-acm',
                       'gts9-panel-recover', 'gts9-enable-units'):
            path = self.target / 'usr' / 'libexec' / helper
            self.assertTrue(path.is_file(), helper)
            self.assertTrue(os.access(path, os.X_OK), helper)
        for unit in ('gts9-boot-stage.service', 'gts9-getty-stage.service',
                     'gts9-poweroff-stage.service',
                     'gts9-debian-entered.service',
                     'gts9-debian-basic-stage.service',
                     'gts9-debian-getty-stage.service',
                     'gts9-debian-multi-user-stage.service',
                     'gts9-usb-acm.service', 'gts9-panel-recover.service'):
            self.assertTrue((self.target / 'usr/lib/systemd/system' / unit).is_file(),
                            unit)
        autologin = (self.target / 'etc/systemd/system' /
                     'serial-getty@ttyGS0.service.d' / 'autologin.conf')
        self.assertTrue(autologin.is_file())
        self.assertIn('--autologin root', autologin.read_text())
        # The overlay ships no symlinks; the helper creates this one too.
        self.assertEqual(
            os.readlink(self.target / 'etc/systemd/system/getty.target.wants' /
                        'serial-getty@ttyGS0.service'),
            '../../../../usr/lib/systemd/system/serial-getty@.service')

    def test_enablement_symlinks_match_each_units_wantedby(self):
        self.install()
        for unit in sorted((self.target / 'usr/lib/systemd/system').glob('gts9-*.service')):
            wants = [line.split('=', 1)[1].strip()
                     for line in unit.read_text().splitlines()
                     if line.startswith('WantedBy=')]
            self.assertTrue(wants, unit.name)
            for want in wants:
                link = (self.target / 'etc/systemd/system' /
                        f'{want}.wants' / unit.name)
                self.assertTrue(link.is_symlink(), f'{unit.name} -> {want}')
                self.assertEqual(os.readlink(link),
                                 f'../../../../usr/lib/systemd/system/{unit.name}')

    def test_all_enablement_symlinks_are_relative(self):
        """Every generated link must be relative.

        TWRP's busybox tar refuses to replace a symlink whose stored target is
        absolute and outside the extraction root, so the deployed tree must not
        contain such links.
        """
        self.install()
        links = [p for p in self.target.rglob('*') if p.is_symlink()]
        self.assertTrue(links)
        for path in links:
            self.assertFalse(os.readlink(path).startswith('/'), str(path))

    def test_overlay_ships_no_symlinks_at_all(self):
        links = [p for p in OVERLAY.rglob('*') if p.is_symlink()]
        self.assertEqual(links, [],
                         'enablement links belong to gts9-enable-units')

    def test_tarball_contains_no_symlink_entries(self):
        tar_file = self.root / 'gts9-debian-overlay.tar'
        result = run_installer('--tar', str(tar_file), '--skip-modules',
                               '--skip-firmware')
        self.assertEqual(result.returncode, 0, result.stderr)
        listing = subprocess.run(['tar', '-tvf', str(tar_file)], text=True,
                                 capture_output=True, check=True).stdout
        self.assertNotIn(' -> ', listing,
                         'a symlink entry would make TWRP extraction fail')
        # The tree is only complete after the documented helper runs.
        self.assertIn('gts9-enable-units', listing)

    def test_enable_helper_is_idempotent_and_scoped(self):
        helper = OVERLAY / 'usr' / 'libexec' / 'gts9-enable-units'
        self.assertTrue(os.access(helper, os.X_OK))
        self.install()
        before = snapshot(self.target)
        again = subprocess.run(['sh', str(self.target / 'usr/libexec/gts9-enable-units'),
                                str(self.target)], text=True,
                               capture_output=True, check=False)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(snapshot(self.target), before)
        # Unrelated enablement links are never touched.
        self.assertFalse((self.target / 'etc/systemd/system/getty.target.wants' /
                          'serial-getty@ttyMSM0.service').exists())

    def test_installer_is_repeatable(self):
        first = self.install()
        self.assertEqual(first.returncode, 0, first.stderr)
        before = snapshot(self.target)
        second = self.install()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(snapshot(self.target), before)

    def test_never_writes_below_lib_bin_or_sbin(self):
        """A lib/ entry in the tarball replaces the /lib usr-merge symlink.

        TWRP's busybox tar does that, and the resulting dangling /sbin/init
        makes switch_root die and the kernel panic (test 178 boots 1-4).
        """
        kernel_dir = self.root / 'kernel-gts9wifi'
        module_file = (kernel_dir / 'modules-root' / 'lib' / 'modules' /
                       '7.2.0-test' / 'extra' / 'foo.ko')
        module_file.parent.mkdir(parents=True)
        module_file.write_text('not a real module\n')
        (kernel_dir / 'kernel.release').write_text('7.2.0-test\n')
        firmware = self.root / 'firmware'
        (firmware / 'keyboard_stm').mkdir(parents=True)
        (firmware / 'keyboard_stm' / 'stm32_gts9family.bin').write_text('blob\n')
        tar_file = self.root / 'overlay.tar'
        result = run_installer('--tar', str(tar_file),
                               '--modules', str(kernel_dir / 'modules-root'),
                               '--firmware', str(firmware),
                               env={'GTS9_DEPMOD': 'depmod-that-does-not-exist'})
        self.assertEqual(result.returncode, 0, result.stderr)
        listing = subprocess.run(['tar', '-tf', str(tar_file)], text=True,
                                 capture_output=True, check=True).stdout.split()
        for entry in listing:
            rel = entry[2:] if entry.startswith('./') else entry.lstrip('/')
            first = rel.split('/', 1)[0]
            self.assertNotIn(first, ('lib', 'bin', 'sbin', 'lib64'), entry)
        self.assertIn('./usr/lib/modules/7.2.0-test/extra/foo.ko', listing)
        self.assertIn('./usr/lib/firmware/keyboard_stm/stm32_gts9family.bin',
                      listing)

    def test_refuses_a_rootfs_whose_usr_merge_is_already_broken(self):
        # Simulate the damage: a real /lib directory instead of a symlink.
        (self.target / 'lib').unlink()
        (self.target / 'lib' / 'firmware').mkdir(parents=True)
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('is a real directory', result.stderr)

    def test_refuses_the_host_root_and_non_debian_targets(self):
        root = run_installer('--skip-modules', '--skip-firmware', '/')
        self.assertNotEqual(root.returncode, 0)
        self.assertIn('refusing', root.stderr)
        plain = self.root / 'not-debian'
        plain.mkdir()
        result = run_installer('--skip-modules', '--skip-firmware', str(plain))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('not a Debian root', result.stderr)

    def test_requires_exactly_one_destination(self):
        neither = run_installer('--skip-modules', '--skip-firmware')
        self.assertNotEqual(neither.returncode, 0)
        both = run_installer('--tar', str(self.root / 'x.tar'),
                             '--skip-modules', '--skip-firmware',
                             str(self.target))
        self.assertNotEqual(both.returncode, 0)

    def test_tarball_is_relative_and_matches_a_direct_install(self):
        tar_file = self.root / 'gts9-debian-overlay.tar'
        result = run_installer('--tar', str(tar_file), '--skip-modules',
                               '--skip-firmware')
        self.assertEqual(result.returncode, 0, result.stderr)
        listing = subprocess.run(['tar', '-tf', str(tar_file)], text=True,
                                 capture_output=True, check=True).stdout.split()
        self.assertTrue(listing)
        for entry in listing:
            self.assertFalse(entry.startswith('/'), entry)
            self.assertNotIn('..', Path(entry).parts, entry)

        direct = self.install()
        self.assertEqual(direct.returncode, 0, direct.stderr)
        extracted = self.root / 'extracted'
        extracted.mkdir()
        subprocess.run(['tar', '-xpf', str(tar_file), '-C', str(extracted)],
                       check=True)
        direct_files = snapshot(self.target)
        extracted_files = snapshot(extracted)
        # The direct target keeps its own pre-existing files; every file the
        # tarball carries must be identical in both.
        self.assertIn('usr/libexec/gts9-usb-acm', extracted_files)
        self.assertEqual(extracted_files,
                         {k: v for k, v in direct_files.items()
                          if k in extracted_files})

    def test_modules_are_installed_under_their_release(self):
        kernel_dir = self.root / 'kernel-gts9wifi'
        module_file = (kernel_dir / 'modules-root' / 'lib' / 'modules' /
                       '7.2.0-test' / 'extra' / 'foo.ko')
        module_file.parent.mkdir(parents=True)
        module_file.write_text('not a real module\n')
        (kernel_dir / 'kernel.release').write_text('7.2.0-test\n')
        result = run_installer('--modules', str(kernel_dir / 'modules-root'),
                               '--skip-firmware', str(self.target))
        self.assertEqual(result.returncode, 0, result.stderr)
        # usr/lib/modules, so no lib/ entry can ever clobber the usr-merge.
        installed = (self.target / 'usr' / 'lib' / 'modules' / '7.2.0-test' /
                     'extra' / 'foo.ko')
        self.assertTrue(installed.is_file())
        releases = [p.name for p in
                    (self.target / 'usr/lib/modules').iterdir()]
        self.assertEqual(releases, ['7.2.0-test'])
        self.assertTrue((self.target / 'lib').is_symlink())

    def test_module_release_must_match_the_recorded_kernel_release(self):
        kernel_dir = self.root / 'kernel-gts9wifi'
        module_file = (kernel_dir / 'modules-root' / 'lib' / 'modules' /
                       '7.2.0-other' / 'extra' / 'foo.ko')
        module_file.parent.mkdir(parents=True)
        module_file.write_text('not a real module\n')
        (kernel_dir / 'kernel.release').write_text('7.2.0-test\n')
        result = run_installer('--modules', str(kernel_dir / 'modules-root'),
                               '--skip-firmware', str(self.target))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('does not match kernel.release', result.stderr)

    def test_firmware_is_installed(self):
        firmware = self.root / 'firmware'
        (firmware / 'keyboard_stm').mkdir(parents=True)
        (firmware / 'keyboard_stm' / 'stm32_gts9family.bin').write_text('blob\n')
        result = run_installer('--firmware', str(firmware), '--skip-modules',
                               str(self.target))
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = (self.target / 'usr' / 'lib' / 'firmware' / 'keyboard_stm' /
                     'stm32_gts9family.bin')
        self.assertEqual(installed.read_text(), 'blob\n')
        self.assertTrue((self.target / 'lib').is_symlink())

    def test_depmod_runs_against_the_installed_tree(self):
        kernel_dir = self.root / 'kernel-gts9wifi'
        module_file = (kernel_dir / 'modules-root' / 'lib' / 'modules' /
                       '7.2.0-test' / 'extra' / 'foo.ko')
        module_file.parent.mkdir(parents=True)
        module_file.write_text('not a real module\n')
        (kernel_dir / 'kernel.release').write_text('7.2.0-test\n')
        fakebin = self.root / 'fakebin'
        fakebin.mkdir()
        log = self.root / 'depmod-args.txt'
        fake_depmod = fakebin / 'depmod'
        fake_depmod.write_text(f'#!/bin/sh\necho "$@" > {log}\nexit 0\n')
        fake_depmod.chmod(0o755)
        result = run_installer('--modules', str(kernel_dir / 'modules-root'),
                               '--skip-firmware', str(self.target),
                               env={'PATH': f'{fakebin}:{os.environ["PATH"]}'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(log.read_text().strip(),
                         f'-b {self.target} 7.2.0-test')

    def test_missing_depmod_is_only_a_warning(self):
        kernel_dir = self.root / 'kernel-gts9wifi'
        module_file = (kernel_dir / 'modules-root' / 'lib' / 'modules' /
                       '7.2.0-test' / 'extra' / 'foo.ko')
        module_file.parent.mkdir(parents=True)
        module_file.write_text('not a real module\n')
        (kernel_dir / 'kernel.release').write_text('7.2.0-test\n')
        result = run_installer('--modules', str(kernel_dir / 'modules-root'),
                               '--skip-firmware', str(self.target),
                               env={'GTS9_DEPMOD': 'depmod-that-does-not-exist'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('depmod is unavailable', result.stdout)


class MinimalInitramfsHasNoModules(unittest.TestCase):
    def test_builder_keeps_modules_out_of_the_initramfs(self):
        busybox_deb = (ROOT / '.work' / 'downloads' /
                       'busybox-static_1.36.1-6ubuntu3.1_arm64.deb')
        if not busybox_deb.is_file() or not shutil.which('clang') or \
           not shutil.which('ld.lld'):
            self.skipTest('busybox cache or clang is unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / 'tree'
            out = Path(tmp) / 'initramfs.img'
            result = subprocess.run(
                [str(BUILDER), '--tree', str(tree), '--out', str(out)],
                text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((tree / 'minimal-rootfs-init').is_file())
            self.assertTrue((tree / 'minimal-rootfs-state.sh').is_file())
            self.assertFalse((tree / 'lib' / 'modules').exists(),
                             'the minimal initramfs must not carry a module tree')

    def test_modules_are_opt_in_for_the_builder(self):
        text = BUILDER.read_text()
        self.assertIn("if [ -n \"$modules\" ]; then", text)
        self.assertIn('exec_args=(--modules "$modules")', text)
        self.assertIn('exec_args=()', text)


if __name__ == '__main__':
    unittest.main()
