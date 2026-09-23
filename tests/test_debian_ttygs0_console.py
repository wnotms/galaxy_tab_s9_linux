"""Host checks for the bring-up root console on the USB ACM ttyGS0."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ETC = ROOT / 'rootfs-overlay' / 'etc'
DROP_IN = ETC / 'systemd' / 'system' / 'serial-getty@ttyGS0.service.d' / 'autologin.conf'
WANTS = ETC / 'systemd' / 'system' / 'getty.target.wants'


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
        link = WANTS / 'serial-getty@ttyGS0.service'
        self.assertTrue(link.is_symlink(), 'the ttyGS0 console must be enabled')
        self.assertEqual(link.readlink().as_posix(),
                         '/usr/lib/systemd/system/serial-getty@.service')

    def test_no_other_getty_is_enabled_by_the_overlay(self):
        entries = sorted(p.name for p in WANTS.iterdir())
        self.assertEqual(entries, ['serial-getty@ttyGS0.service'])


if __name__ == '__main__':
    unittest.main()
