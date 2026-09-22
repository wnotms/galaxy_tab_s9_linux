"""Host checks for the optional Debian microSD boot (gts9_rootfs=)."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INIT = (ROOT / 'boot' / 'bringup-init.sh').read_text()
CMDLINE = (ROOT / 'boot' / 'cmdline.example.txt').read_text()


class RootfsBoot(unittest.TestCase):
    def test_parses_the_interface(self):
        self.assertIn('gts9_rootfs=*) ROOTFS_DEVICE=${arg#gts9_rootfs=}', INIT)
        self.assertIn("ROOTFS_DEVICE=''", INIT)

    def test_handoff_runs_before_the_panel_shell(self):
        self.assertIn('boot_rootfs()', INIT)
        call = INIT.index('\n    if ! boot_rootfs; then')
        self.assertLess(call, INIT.index('\nstart_panel_shell\n'))
        self.assertIn('falling back to BusyBox rescue shell', INIT)

    def test_failure_never_reboots_or_panics(self):
        body = INIT[INIT.index('boot_rootfs()'):]
        body = body[:body.index('\n}\n')]
        for forbidden in ('reboot', 'panic', 'poweroff', 'reboot_to_recovery'):
            self.assertNotIn(forbidden, body,
                             f'{forbidden} must not appear in the rootfs handoff')

    def test_root_device_is_never_exported_as_mass_storage(self):
        self.assertIn('USB mass storage disabled', INIT)
        self.assertIn('msc|both)', INIT)

    def test_switch_root_is_the_handoff(self):
        self.assertIn('exec switch_root /newroot /sbin/init', INIT)

    def test_timers_disabled_in_rootfs_mode(self):
        self.assertIn('proof and recovery timers disabled', INIT)

    def test_cmdline_profile(self):
        tokens = CMDLINE.split()
        self.assertIn('gts9_rootfs=/dev/mmcblk1p1', tokens)
        for gone in ('gts9_proof_code', 'gts9_proof_action', 'gts9_reboot_after',
                     'console=tty0', 'ignore_loglevel'):
            self.assertFalse(any(t.startswith(gone) for t in tokens), gone)
        self.assertIn('console=ttyMSM0,115200n8', tokens)
        self.assertIn('earlycon', tokens)
        self.assertIn('fbcon=font:TER16x32', tokens)


if __name__ == '__main__':
    unittest.main()
