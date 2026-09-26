"""Host checks for the removal of the USB ACM login console (ttyGS0).

History, because it is what these checks are the inverse of.  Until 2026-09-24
the port was served by the generic `serial-getty@ttyGS0.service`, which waits for
`dev-ttyGS0.device`; the gadget creates that device only a moment later, so the
unit timed out and failed.  It was replaced by `gts9-acm-getty.service`, ordered
after `gts9-usb-acm.service`, with autologin in the unit itself.

That unit is now GONE, and deliberately.  `agetty --autologin` spawns a login
shell that agetty does not reap on SIGTERM, so the unit's cgroup stayed populated
and systemd waited out `TimeoutStopSec` - the ~90 s poweroff documented in
docs/SHUTDOWN_DELAY.md.  Both serial debug consoles were removed on 2026-09-26
and the tablet is reached over ssh instead (docs/FAST_DEBUG_CHANNEL.md).

These tests therefore assert the ABSENCE of the getty, of any autologin, and of
the enablement link that would start it - plus the two masks the enablement
helper must keep installing so an upgraded rootfs cannot resurrect a serial
getty.  They replace the previous file, which asserted the getty's presence.
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
UNIT_DIR = OVERLAY / 'usr' / 'lib' / 'systemd' / 'system'
ENABLE_HELPER = LIBEXEC / 'gts9-enable-units'


def enable_units_in(root):
    """Run the shipped enablement helper against a temporary Debian root."""
    system = Path(root) / 'usr' / 'lib' / 'systemd' / 'system'
    system.mkdir(parents=True, exist_ok=True)
    # The template a serial getty instance would be created from.
    (system / 'serial-getty@.service').write_text('[Unit]\nDescription=Serial Getty on %I\n')
    for unit in UNIT_DIR.glob('gts9-*.service'):
        (system / unit.name).write_text(unit.read_text())
    return subprocess.run(['sh', str(ENABLE_HELPER), str(root)],
                          text=True, capture_output=True, check=False)


class NoSerialLoginConsole(unittest.TestCase):
    def test_the_acm_getty_unit_is_gone(self):
        self.assertFalse((UNIT_DIR / 'gts9-acm-getty.service').exists(),
                         'the ttyGS0 autologin getty is the 90 s poweroff')

    def test_no_unit_anywhere_logs_anyone_in(self):
        # A getty on a serial device is what must never come back.  Check the
        # whole overlay, not just the unit directory: a drop-in or an /etc copy
        # would win over /usr/lib at runtime.
        #
        # Comments are stripped first.  These files explain the very mistake
        # these tests check for - gts9-enable-units documents the autologin shell
        # it removes - so prose must not be able to satisfy or defeat a check.
        #
        # What is forbidden is EXECUTION, not the word: gts9-device-changes greps
        # for 'agetty' on purpose, to report a leftover autologin drop-in, which is
        # the opposite of running one.  A test that failed on the mention would be
        # forcing the detector to be less useful than it should be.
        for path in sorted(OVERLAY.rglob('*')):
            if not path.is_file():
                continue
            for line in path.read_text(errors='replace').splitlines():
                code = line.split('#', 1)[0]
                if not code.strip():
                    continue
                with self.subTest(file=str(path), line=line.strip()):
                    self.assertNotIn('--autologin', code)
                    self.assertNotRegex(
                        code, r'(^|[|;&(`]|\$\(|\s)(/usr/sbin/|/sbin/)?agetty\s',
                        f'{path} appears to run agetty')
                    for dev in ('ttyGS0', 'ttyGS1', 'ttyMSM0'):
                        self.assertNotIn(f'getty {dev}', code)

    def test_no_global_getty_or_autologin_override(self):
        system_dir = ETC / 'systemd' / 'system'
        for forbidden in ('getty@.service', 'getty@tty1.service',
                          'serial-getty@.service', 'getty.target'):
            self.assertFalse((system_dir / forbidden).exists(), forbidden)
        self.assertFalse((ETC / 'securetty').exists())

    def test_the_removed_getty_link_is_not_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = enable_units_in(tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            wants = Path(tmp) / 'etc/systemd/system/multi-user.target.wants'
            self.assertFalse((wants / 'gts9-acm-getty.service').exists(),
                             'a dangling enable link is a boot-time failure')

    def test_both_serial_getties_are_masked_and_none_is_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(enable_units_in(tmp).returncode, 0)
            getty_wants = Path(tmp) / 'etc/systemd/system/getty.target.wants'
            entries = sorted(p.name for p in getty_wants.iterdir()) if getty_wants.is_dir() else []
            self.assertEqual(entries, [])
            for dev in ('ttyMSM0', 'ttyGS0'):
                mask = Path(tmp) / f'etc/systemd/system/serial-getty@{dev}.service'
                self.assertTrue(mask.is_symlink(), dev)
                self.assertEqual(os.readlink(mask), '/dev/null')

    def test_the_removed_getty_cannot_survive_in_etc(self):
        # /etc/systemd/system/ wins over /usr/lib, and this repository's own
        # notes record the two copies having diverged once.  The helper must mask
        # the name outright, so a stale copy there cannot start.
        with tempfile.TemporaryDirectory() as tmp:
            etc_system = Path(tmp) / 'etc/systemd/system'
            etc_system.mkdir(parents=True)
            stale = etc_system / 'gts9-acm-getty.service'
            stale.write_text('[Service]\nExecStart=/usr/sbin/agetty ttyGS0\n')
            self.assertEqual(enable_units_in(tmp).returncode, 0)
            # The name is replaced by a /dev/null mask, which is what systemctl
            # mask does and the only thing that reliably stops it starting.
            self.assertTrue(stale.is_symlink(), 'the stale unit must be masked')
            self.assertEqual(os.readlink(stale), '/dev/null')

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
