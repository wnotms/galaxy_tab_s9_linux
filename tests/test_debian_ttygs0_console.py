"""Host checks for the bring-up root console on the USB ACM ttyGS0.

The console moved on 2026-09-24 (test-184): the generic
serial-getty@ttyGS0.service waits for dev-ttyGS0.device, which the gadget
creates only a moment later, so it timed out and failed - and with nobody
holding the tty open the gadget had no OUT requests, so host writes timed out
too.  The port is now served by gts9-acm-getty.service, ordered after
gts9-usb-acm.service, with autologin in the unit itself rather than a drop-in.
"""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OVERLAY = ROOT / 'rootfs-overlay'
ETC = OVERLAY / 'etc'
LIBEXEC = OVERLAY / 'usr' / 'libexec'
ACM_GETTY = OVERLAY / 'usr' / 'lib' / 'systemd' / 'system' / 'gts9-acm-getty.service'
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
    def test_autologin_is_in_the_dedicated_unit(self):
        text = ACM_GETTY.read_text()
        self.assertIn('ExecStart=-/usr/sbin/agetty --autologin root --noclear ttyGS0 115200 vt100',
                      text)
        self.assertIn('After=gts9-usb-acm.service', text)
        self.assertIn('Wants=gts9-usb-acm.service', text)

    def test_no_getty_drop_in_remains(self):
        # Autologin lives in the unit now; a leftover drop-in would be a second
        # source of truth for the same console.
        leftovers = sorted(str(p.relative_to(ETC)) for p in ETC.rglob('*.conf'))
        self.assertEqual(leftovers, ['systemd/logind.conf.d/60-gts9-power-key.conf'])

    def test_no_global_getty_or_autologin_override(self):
        system_dir = ETC / 'systemd' / 'system'
        for forbidden in ('getty@.service', 'getty@tty1.service',
                          'serial-getty@.service', 'getty.target'):
            self.assertFalse((system_dir / forbidden).exists(), forbidden)
        self.assertFalse((ETC / 'securetty').exists())
        for path in system_dir.rglob('*'):
            if path.is_file():
                self.assertNotIn('autologin', path.read_text(), str(path))

    def test_dedicated_getty_is_enabled_and_the_generic_instance_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = enable_units_in(tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            wants = Path(tmp) / 'etc/systemd/system/multi-user.target.wants'
            link = wants / 'gts9-acm-getty.service'
            self.assertTrue(link.is_symlink(), 'the ACM console getty must be enabled')
            # Relative, because TWRP's busybox tar refuses absolute symlink
            # targets that live outside the extraction root.
            self.assertEqual(link.readlink().as_posix(),
                             '../../../../usr/lib/systemd/system/gts9-acm-getty.service')
            self.assertTrue(link.resolve().is_file())
            self.assertFalse((Path(tmp) / 'etc/systemd/system/getty.target.wants' /
                              'serial-getty@ttyGS0.service').exists())

    def test_ttymsm0_getty_is_masked_and_no_other_getty_is_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(enable_units_in(tmp).returncode, 0)
            getty_wants = Path(tmp) / 'etc/systemd/system/getty.target.wants'
            entries = sorted(p.name for p in getty_wants.iterdir()) if getty_wants.is_dir() else []
            self.assertEqual(entries, [])
            mask = Path(tmp) / 'etc/systemd/system/serial-getty@ttyMSM0.service'
            self.assertTrue(mask.is_symlink())
            self.assertEqual(os.readlink(mask), '/dev/null')

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
