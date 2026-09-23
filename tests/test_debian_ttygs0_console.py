"""Host checks for the bring-up root console on the USB ACM ttyGS0."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OVERLAY = ROOT / 'rootfs-overlay'
ETC = OVERLAY / 'etc'
LIBEXEC = OVERLAY / 'usr' / 'libexec'
DROP_IN = ETC / 'systemd' / 'system' / 'serial-getty@ttyGS0.service.d' / 'autologin.conf'
ENABLE_HELPER = LIBEXEC / 'gts9-enable-units'


def enable_units_in(root):
    """Run the shipped enablement helper against a temporary Debian root."""
    system = Path(root) / 'usr' / 'lib' / 'systemd' / 'system'
    system.mkdir(parents=True, exist_ok=True)
    # The template the ttyGS0 instance is created from.
    (system / 'serial-getty@.service').write_text('[Unit]\nDescription=Serial Getty on %I\n')
    for unit in (OVERLAY / 'usr/lib/systemd/system').glob('gts9-*.service'):
        (system / unit.name).write_text(unit.read_text())
    return subprocess.run(['sh', str(ENABLE_HELPER), str(root)],
                          text=True, capture_output=True, check=False)


class TtyGs0Console(unittest.TestCase):
    def test_drop_in_autologins_root_on_the_instance_argument(self):
        text = DROP_IN.read_text()
        self.assertEqual(text.strip().splitlines(), [
            '[Service]',
            'ExecStart=',
            'ExecStart=-/sbin/agetty --autologin root --noclear %I $TERM',
        ])

    def test_drop_in_applies_to_ttygs0_only(self):
        # Any other getty drop-in would change a different console.
        drop_ins = sorted(str(p.relative_to(ETC)) for p in ETC.rglob('*.conf'))
        self.assertEqual(drop_ins, [
            'systemd/logind.conf.d/60-gts9-power-key.conf',
            'systemd/system/serial-getty@ttyGS0.service.d/autologin.conf',
        ])

    def test_no_global_getty_or_autologin_override(self):
        system_dir = ETC / 'systemd' / 'system'
        for forbidden in ('getty@.service', 'getty@tty1.service',
                          'serial-getty@.service', 'getty.target'):
            self.assertFalse((system_dir / forbidden).exists(), forbidden)
        self.assertFalse((ETC / 'securetty').exists())
        for path in system_dir.rglob('*'):
            if path.is_file() and path != DROP_IN:
                self.assertNotIn('autologin', path.read_text(), str(path))

    def test_console_is_enabled_through_the_instance_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = enable_units_in(tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            link = (Path(tmp) / 'etc/systemd/system/getty.target.wants' /
                    'serial-getty@ttyGS0.service')
            self.assertTrue(link.is_symlink(), 'the ttyGS0 console must be enabled')
            # The instance points at the template, and the target is relative:
            # TWRP's busybox tar refuses to replace absolute symlink targets
            # that live outside the extraction root.
            self.assertEqual(link.readlink().as_posix(),
                             '../../../../usr/lib/systemd/system/serial-getty@.service')
            self.assertTrue(link.resolve().is_file())

    def test_no_other_getty_is_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(enable_units_in(tmp).returncode, 0)
            wants = Path(tmp) / 'etc/systemd/system/getty.target.wants'
            entries = sorted(p.name for p in wants.iterdir())
            self.assertEqual(entries, ['serial-getty@ttyGS0.service'])

    def test_helper_never_touches_other_enablement_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            wants = Path(tmp) / 'etc/systemd/system/multi-user.target.wants'
            wants.mkdir(parents=True)
            keep = wants / 'sshd.service'
            os.symlink('/usr/lib/systemd/system/sshd.service', keep)
            self.assertEqual(enable_units_in(tmp).returncode, 0)
            self.assertTrue(keep.is_symlink())
            self.assertEqual(os.readlink(keep), '/usr/lib/systemd/system/sshd.service')

    def test_helper_is_posix_and_needs_no_systemctl(self):
        text = ENABLE_HELPER.read_text()
        code = '\n'.join(line for line in text.splitlines()
                         if not line.lstrip().startswith('#'))
        for bashism in ('[[', 'declare ', 'local ', 'function '):
            self.assertNotIn(bashism, code, bashism)
        self.assertNotIn('systemctl', code)
        self.assertTrue(os.access(ENABLE_HELPER, os.X_OK))


if __name__ == '__main__':
    unittest.main()
