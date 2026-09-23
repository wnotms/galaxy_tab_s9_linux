"""Checks for the Debian-side "reboot into TWRP" helper.

The helper runs on the tablet as root and writes to a raw UFS partition, so the
things worth testing are its refusals and its byte layout rather than a happy
path: on a development host there is no misc partition to write to, and there
must never be one.  The write sequence itself is executed here against a plain
file, extracted from the shipped script, so a change to it is caught.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'boot/gts9-debian-to-recovery.sh'
INITRAMFS_HELPER = ROOT / 'boot/gts9-to-recovery.sh'
INIT = ROOT / 'boot/bringup-init.sh'


def shell_function(source, name):
    """Return the text of a top-level `name() { ... }` shell function."""
    start = re.search(r'^' + name + r'\(\)\s*\{', source, flags=re.M)
    assert start is not None, name
    depth, i = 0, start.end() - 1
    while True:
        if source[i] == '{':
            depth += 1
        elif source[i] == '}':
            depth -= 1
            if depth == 0:
                return source[start.start():i + 1]
        i += 1


class DebianRecoveryBoot(unittest.TestCase):
    def setUp(self):
        if not shutil.which('sh'):
            self.skipTest('requires a POSIX shell')
        self.text = HELPER.read_text()

    def test_syntax(self):
        for sh in ('sh', 'dash'):
            if shutil.which(sh):
                subprocess.run([sh, '-n', str(HELPER)], check=True)

    def test_write_bcb_layout_matches_the_proven_sequence(self):
        """Execute the shipped write_bcb() and compare the block byte for byte."""
        source = self.text
        harness = 'BCB_BYTES=2048\nBCB_COMMAND=boot-recovery\n'
        harness += 'info() { :; }\n'
        harness += 'die() { echo "$*" >&2; exit 1; }\n'
        harness += shell_function(source, 'bcb_command') + '\n'
        harness += shell_function(source, 'write_bcb') + '\n'
        harness += 'dev=$1\nwrite_bcb\n'

        with tempfile.TemporaryDirectory() as tmp:
            dev = Path(tmp) / 'misc.img'
            dev.write_bytes(b'\xff' * 4096)  # pre-fill: the write must overwrite
            subprocess.run(['sh', '-eu', '-c', harness, 'sh', str(dev)], check=True)
            got = dev.read_bytes()

        # Exactly one 2048-byte block is touched; the rest is left alone.
        self.assertEqual(got[2048:], b'\xff' * 2048)
        self.assertEqual(got[:13], b'boot-recovery')
        self.assertEqual(got[13:2048], b'\x00' * (2048 - 13))

    def test_layout_matches_the_initramfs_helper(self):
        """Both helpers must ask for recovery with the same command bytes."""
        # The initramfs helper is the one verified on hardware.
        self.assertIn("printf 'boot-recovery'", INITRAMFS_HELPER.read_text())
        # This helper must use the same string; test_write_bcb_layout... then
        # proves it lands in the block identically.
        self.assertIn("BCB_COMMAND='boot-recovery'", self.text)

    def test_never_asks_the_kernel_for_recovery_mode(self):
        """A reboot mode string writes SPMI SDAM, which hangs this kernel."""
        code = '\n'.join(l for l in self.text.split('\n')
                         if not l.lstrip().startswith('#'))
        # No mode request may be issued, in any spelling.
        self.assertNotIn('reboot recovery', code)
        self.assertNotIn('reboot bootloader', code)
        self.assertNotIn('RESTART2', code)
        self.assertNotIn('--boot-loader', code)
        # Only an argument-less restart is allowed.
        self.assertIn('\texec reboot\n', code)  # produced the same as `systemctl reboot`
        self.assertIn('\t\texec systemctl reboot\n', code)
        self.assertNotIn('reboot -f', code)

    def test_existing_recovery_request_still_requires_confirmation(self):
        """An already-written BCB must not turn a default invocation into a surprise reboot."""
        branch = re.search(r'^write\)\n(.*?)\n\t;;', self.text, flags=re.M | re.S)
        self.assertIsNotNone(branch)
        self.assertIn('confirm_write', branch.group(1))

        harness = ('PROG=test\nBCB_COMMAND=boot-recovery\n'
                   'assume_yes=0\ndo_reboot=1\ncurrent=boot-recovery\n'
                   'dev=/dev/sda10\n'
                   'die() { echo "$*" >&2; exit 1; }\n'
                   + shell_function(self.text, 'confirm_write')
                   + '\nconfirm_write\n')
        r = subprocess.run(['sh', '-eu', '-c', harness],
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('no terminal to confirm', r.stderr)

    def test_bcb_read_failure_does_not_look_like_an_empty_request(self):
        harness = ('die() { echo "$*" >&2; exit 1; }\n'
                   + shell_function(self.text, 'bcb_command')
                   + '\nbcb_command /definitely/not/a/block/device\n')
        r = subprocess.run(['sh', '-eu', '-c', harness],
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('cannot read the BCB', r.stderr)

    def test_refuses_anything_that_is_not_ufs_misc(self):
        """Every guard fails closed: a wrong device is somebody else's partition."""
        for guard in ('must run as root',
                      'is not a block device',
                      'is not a UFS partition',
                      'has no GPT partition label',
                      'is not a SCSI/UFS disk',
                      'is mounted at',
                      'is the running root filesystem'):
            self.assertIn(guard, self.text, guard)
        # A label mismatch must be refused, not logged and ignored.
        self.assertIn("$MISC_LABEL'\"", self.text)
        # The microSD is mmcblk1; it must be excluded by name.
        self.assertIn('mmcblk*', self.text)

    def test_expected_layout_matches_the_recorded_gpt_entry(self):
        """misc is GPT index 9, 256 sectors, which is /dev/sda10."""
        self.assertIn('EXPECTED_SECTORS=256', self.text)
        report = (ROOT / 'reference/boot-tests/test-047-20260922T060344Z'
                  / 'bringup-report.txt')
        if not report.is_file():
            self.skipTest('no recorded bringup report')
        found = re.search(rb'^\s*9\s+25356\s+256\s+\d+\s+misc\s*$',
                          report.read_bytes(), flags=re.M)
        self.assertIsNotNone(found, 'misc GPT entry not found in the report')
        # Partition index 9 -> the 10th device node.
        self.assertIn('/dev/sda10', report.read_bytes().decode('utf-8', 'replace'))

    def test_a_failed_request_costs_one_boot_not_a_brick(self):
        """The round trip works because the initramfs consumes the request."""
        init = INIT.read_text()
        clear = init.index('\nclear_stale_bcb\n')
        handoff = init.index('\n    if ! boot_rootfs; then')
        self.assertLess(clear, handoff,
                        'clear_stale_bcb must run before the rootfs handoff, '
                        'or a recovery request would survive into the next boot')
        self.assertIn('boot-recovery', init)

    def test_help_and_guards_are_reachable_without_root(self):
        r = subprocess.run(['sh', str(HELPER), '--help'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('--clear', r.stdout)
        r = subprocess.run(['sh', str(HELPER), '--bogus'],
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('unknown argument', r.stderr)


if __name__ == '__main__':
    unittest.main()
