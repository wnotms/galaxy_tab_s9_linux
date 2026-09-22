"""Host checks for the tty1 panel shell and the printk console removal.

These are the machine-checkable parts of the owner's specification for this change:
they do not prove the screen works, they prove the artifacts carry the intended
wiring, so a later edit cannot quietly undo it.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INIT = (ROOT / 'boot' / 'bringup-init.sh').read_text()
CMDLINE = (ROOT / 'boot' / 'cmdline.example.txt').read_text()


class PanelShell(unittest.TestCase):
    def test_function_exists_and_is_backgrounded(self):
        self.assertIn('start_panel_shell()', INIT)
        # The shell loop must be a background job, never PID 1.
        body = INIT[INIT.index('start_panel_shell()'):]
        body = body[:body.index('\n}\n')]
        self.assertIn(') &', body, 'the panel shell must run in the background')
        # `exec /bin/sh` inside the backgrounded child is intended; what must
        # never happen is init itself exec'ing the shell.
        for line in INIT.splitlines():
            self.assertFalse(line.startswith('exec /bin/sh'),
                             'the panel shell must never replace init')

    def test_called_before_the_usb_console_loop(self):
        call = INIT.index('\nstart_panel_shell\n')
        # the USB console section is the one that waits for ttyGS0
        usb = INIT.index('while [ "$i" -lt 20 ] && [ ! -c /dev/ttyGS0 ]')
        self.assertLess(call, usb, 'the USB section ends in a loop that never returns')

    def test_panel_carries_only_the_shell(self):
        self.assertNotIn('cat /dev/kmsg > /dev/tty1', INIT)
        self.assertIn('tty0/active', INIT, 'the foreground VT must be logged')
        self.assertIn('chvt 1', INIT)
        self.assertIn('/dev/tty1', INIT)

    def test_rootfs_boot_skips_the_panel_shell(self):
        body = INIT[INIT.index('start_panel_shell()'):]
        body = body[:body.index('\n}\n')]
        self.assertIn('gts9_rootfs=', body,
                      'a rootfs boot must keep the initramfs shell off tty1')

    def test_printk_is_quietened_but_not_disabled(self):
        self.assertIn("printf '1 4 1 7\\n' > /proc/sys/kernel/printk", INIT)
        self.assertNotIn('echo off > /proc/sys/kernel/printk', INIT)


class Cmdline(unittest.TestCase):
    def test_printk_has_no_panel_console(self):
        tokens = CMDLINE.split()
        self.assertNotIn('console=tty0', tokens)
        self.assertNotIn('ignore_loglevel', tokens)

    def test_debug_channels_survive(self):
        tokens = CMDLINE.split()
        self.assertIn('console=ttyMSM0,115200n8', tokens)
        self.assertIn('earlycon', tokens)
        self.assertIn('fbcon=font:TER16x32', tokens)
        self.assertIn('loglevel=4', tokens)

    def test_no_console_token_other_than_uart(self):
        consoles = [t for t in CMDLINE.split() if t.startswith('console=')]
        self.assertEqual(consoles, ['console=ttyMSM0,115200n8'])


if __name__ == '__main__':
    unittest.main()
