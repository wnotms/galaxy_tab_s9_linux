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

    def test_job_control_is_on_for_the_launch(self):
        # Without it the child inherits SIGINT as SIG_IGN and Ctrl-C does nothing.
        body = INIT[INIT.index('start_panel_shell()'):]
        body = body[:body.index('\n}\n')]
        self.assertIn('set -m', body)
        self.assertIn('set +m', body)

    def test_panel_carries_only_the_shell(self):
        self.assertNotIn('cat /dev/kmsg > /dev/tty1', INIT)
        self.assertIn('tty0/active', INIT, 'the foreground VT must be logged')
        self.assertIn('chvt 1', INIT)
        self.assertIn('/dev/tty1', INIT)

    def test_rescue_shell_survives_a_failed_handoff(self):
        # The handoff runs before the panel shell and succeeds by exec'ing switch_root,
        # so ordering - not a cmdline check - is what keeps BusyBox off tty1.  The panel
        # shell must stay reachable when the handoff fails: the first Debian candidate
        # suppressed it in both cases and booted to a silent screen.
        body = INIT[INIT.index('start_panel_shell()'):]
        body = body[:body.index('\n}\n')]
        self.assertNotIn("grep -q 'gts9_rootfs='", body)
        self.assertIn('if ! boot_rootfs; then', INIT)
        self.assertIn('falling back to BusyBox rescue shell', INIT)

    def test_printk_is_quietened_but_not_disabled(self):
        self.assertIn("printf '1 4 1 7\\n' > /proc/sys/kernel/printk", INIT)
        self.assertNotIn('echo off > /proc/sys/kernel/printk', INIT)


class Cmdline(unittest.TestCase):
    """The command line carries exactly one console, and it is the panel.

    Inverted on 2026-09-26.  This class used to assert the opposite - that the
    panel had NO `console=tty0` and that the only console was `ttyMSM0,115200n8`
    plus `earlycon`.  Both serial debug consoles were then removed: the USB ACM
    one (`console=ttyGS1`) is the measured cause of the boot stall, and the SoC
    UART is the second of the two the removal covers.  The tests are kept, and
    keep the same purpose, so that a later edit cannot quietly put a serial
    console back on this command line.
    """

    def test_the_panel_is_the_console(self):
        tokens = CMDLINE.split()
        self.assertIn('console=tty0', tokens)
        # ... and it is the ONLY console, so /dev/console cannot resolve to a
        # port whose writer blocks when nobody drains it.
        consoles = [t for t in tokens if t.startswith('console=')]
        self.assertEqual(consoles, ['console=tty0'])
        self.assertNotIn('ignore_loglevel', tokens)

    def test_no_serial_debug_console_survives(self):
        tokens = CMDLINE.split()
        for gone in ('console=ttyMSM0,115200n8', 'console=ttyGS1', 'earlycon'):
            self.assertNotIn(gone, tokens, f'{gone} is a removed debug console')
        # `ignore_console_null` belonged to the retired patch 0003; the appended
        # `console=null` is absorbed by CONFIG_NULL_TTY instead.
        self.assertNotIn('ignore_console_null', tokens)
        # No other token may name a serial device either.
        for token in tokens:
            self.assertFalse(token.startswith(('console=ttyGS', 'console=ttyMSM')),
                             f'unexpected serial console: {token}')

    def test_remaining_channels_survive(self):
        tokens = CMDLINE.split()
        self.assertIn('fbcon=font:TER16x32', tokens)
        self.assertIn('loglevel=4', tokens)
        # The persistent Samsung ring is the evidence path that replaces the
        # serial console, so it must stay.
        self.assertTrue(any(t.startswith('gts9_sec_log=') for t in tokens))


if __name__ == '__main__':
    unittest.main()
