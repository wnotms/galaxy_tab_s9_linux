"""Host checks for the X710 power-key policy: blank the panel, keep running."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OVERLAY = ROOT / 'rootfs-overlay'
LOGIND = OVERLAY / 'etc/systemd/logind.conf.d/60-gts9-power-key.conf'
UNIT = OVERLAY / 'usr/lib/systemd/system/gts9-power-key.service'
SOURCE = OVERLAY / 'usr/libexec/gts9-power-key.c'
INSTALLER = ROOT / 'scripts' / 'install-debian-rootfs.sh'

SOURCE_TEXT = SOURCE.read_text()
SOURCE_CODE = '\n'.join(line for line in SOURCE_TEXT.splitlines()
                        if not line.lstrip().startswith(('*', '/*', '//')))


class PowerKeyPolicy(unittest.TestCase):
    def test_logind_no_longer_suspends_or_powers_off(self):
        text = LOGIND.read_text()
        self.assertIn('HandlePowerKey=ignore', text)
        self.assertNotIn('HandlePowerKey=suspend', text)
        self.assertNotIn('HandlePowerKey=poweroff', text)

    def test_service_only_blanks_the_panel(self):
        text = UNIT.read_text()
        self.assertIn('Type=simple', text)
        self.assertIn('ExecStart=/usr/libexec/gts9-power-key', text)
        self.assertIn('Restart=always', text)
        self.assertIn('After=local-fs.target', text)
        self.assertIn('WantedBy=multi-user.target', text)
        for forbidden in ('reboot', 'poweroff', 'suspend', 'hibernate'):
            self.assertNotIn(forbidden, text, forbidden)

    def test_daemon_toggles_the_panel_only(self):
        self.assertIn('/sys/class/graphics/fb0/blank', SOURCE_TEXT)
        self.assertIn('#define KEY_POWER 116', SOURCE_TEXT)
        self.assertIn('#define EV_KEY 0x01', SOURCE_TEXT)
        self.assertIn('"pwrkey"', SOURCE_TEXT)
        self.assertIn('toggle', SOURCE_TEXT)
        # The whole point: never suspend, never power the machine off.
        for forbidden in ('suspend', 'poweroff', 'reboot', 'hibernate'):
            self.assertNotIn(forbidden, SOURCE_CODE.lower(), forbidden)

    def test_daemon_compiles_static_for_the_tablet(self):
        clang = shutil.which('clang')
        if not clang or not shutil.which('ld.lld'):
            self.skipTest('clang/ld.lld is unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            binary = os.path.join(tmp, 'gts9-power-key')
            build = subprocess.run(
                [clang, '--target=aarch64-linux-gnu', '-nostdlib', '-static',
                 '-ffreestanding', '-fno-stack-protector', '-fno-builtin',
                 '-fuse-ld=lld', '-Wl,--build-id=none', '-Wl,-n',
                 '-o', binary, str(SOURCE)],
                text=True, capture_output=True, check=False)
            self.assertEqual(build.returncode, 0, build.stderr)
            headers = subprocess.run(['readelf', '-h', binary], text=True,
                                     capture_output=True, check=True).stdout
            self.assertIn('AArch64', headers)
            self.assertIn('EXEC', headers)
            segments = subprocess.run(['readelf', '-l', binary], text=True,
                                      capture_output=True, check=True).stdout
            self.assertNotIn('INTERP', segments)

    def test_installer_builds_the_helper_and_drops_the_source(self):
        if not shutil.which('clang') or not shutil.which('ld.lld'):
            self.skipTest('clang/ld.lld is unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'debian'
            (target / 'etc/systemd').mkdir(parents=True)
            (target / 'etc/os-release').write_text('ID=debian\n')
            (target / 'usr/lib/systemd/system').mkdir(parents=True)
            (target / 'usr/lib/systemd/systemd').write_text('systemd\n')
            (target / 'usr/lib/systemd/systemd').chmod(0o755)
            for link in ('lib', 'bin', 'sbin'):
                (target / link).symlink_to(f'usr/{link}')
            result = subprocess.run(
                ['bash', str(INSTALLER), '--skip-modules', '--skip-firmware',
                 str(target)], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            helper = target / 'usr/libexec/gts9-power-key'
            self.assertTrue(helper.is_file())
            self.assertTrue(os.access(helper, os.X_OK))
            self.assertFalse((target / 'usr/libexec/gts9-power-key.c').exists())
            headers = subprocess.run(['readelf', '-h', str(helper)], text=True,
                                     capture_output=True, check=True).stdout
            self.assertIn('AArch64', headers)

    def test_installer_warns_but_continues_without_a_toolchain(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'debian'
            (target / 'etc/systemd').mkdir(parents=True)
            (target / 'etc/os-release').write_text('ID=debian\n')
            (target / 'usr/lib/systemd/system').mkdir(parents=True)
            (target / 'usr/lib/systemd/systemd').write_text('systemd\n')
            (target / 'usr/lib/systemd/systemd').chmod(0o755)
            for link in ('lib', 'bin', 'sbin'):
                (target / link).symlink_to(f'usr/{link}')
            result = subprocess.run(
                ['bash', str(INSTALLER), '--skip-modules', '--skip-firmware',
                 str(target)],
                env=dict(os.environ, GTS9_CC='clang-that-does-not-exist'),
                text=True, capture_output=True, check=False)
            # No toolchain: the rest of the overlay must still install.
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('clang/ld.lld missing', result.stdout)
            self.assertFalse((target / 'usr/libexec/gts9-power-key').exists())
            self.assertTrue((target / 'usr/libexec/gts9-panel-recover').is_file())

    def test_docs_describe_the_new_behavior(self):
        text = (ROOT / 'docs' / 'DEBIAN_POWER_KEY.md').read_text()
        self.assertIn('blank', text.lower())
        self.assertIn('USB', text)
        self.assertIn('gts9-power-key', text)


if __name__ == '__main__':
    unittest.main()
