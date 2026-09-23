"""Host checks for the Debian-side Pogo keyboard cold-boot recovery."""
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OVERLAY = ROOT / 'rootfs-overlay' / 'usr'
HELPER = OVERLAY / 'libexec' / 'gts9-pogo-recover'
STAGE_HELPER = OVERLAY / 'libexec' / 'gts9-record-debian-stage'
UNIT = (OVERLAY / 'lib/systemd/system/gts9-pogo-recover.service').read_text()
HELPER_TEXT = HELPER.read_text()
HELPER_CODE = '\n'.join(line for line in HELPER_TEXT.splitlines()
                        if not line.lstrip().startswith('#'))

INITRAMFS_RECORD = """\
format_version=1
origin=initramfs
boot_id=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee
kernel_release=7.2.0-rc3-gts9wifi-dirty
cmdline=console=ttyMSM0,115200n8 gts9_minimal_rootfs=1
timestamp=2026-09-24T00:00:00Z
uptime_seconds=3
root_device=/dev/mmcblk1p1
stage=switch-root
stage_history=kernel-userspace,waiting-root,root-found,mounting-root,root-mounted,init-found,switch-root
failure=none
mmc_devices=/dev/mmcblk1,/dev/mmcblk1p1
"""


class PogoRecoverServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sysfs = self.root / 'rearm'
        self.record = self.root / 'gts9-minimal-last-boot'
        self.record.write_text(INITRAMFS_RECORD)
        self.kmsg = self.root / 'kmsg'
        self.writes = self.root / 'rearm-writes'

    def write_state(self, state='DETACHED', connect=0):
        self.sysfs.write_text(
            f'state={state}\npowered=0\nevent_enabled=0\nirq_armed=0\n'
            f'ready=0\nconnect={connect}\nannounce=0\nannouncements=0\n'
            f'regulator_enabled=0\n')

    def run_helper(self, env=None, **overrides):
        environment = dict(os.environ,
                           GTS9_POGO_SYSFS=str(self.sysfs),
                           GTS9_STAGE_HELPER=str(STAGE_HELPER),
                           GTS9_MINIMAL_BOOT_RECORD=str(self.record),
                           GTS9_POGO_KMSG=str(self.kmsg),
                           GTS9_POGO_WINDOW_SECONDS='3',
                           GTS9_POGO_POLL_SECONDS='1',
                           GTS9_POGO_REARM_WAIT_SECONDS='2')
        environment.update(overrides)
        if env:
            environment.update(env)
        return subprocess.run(['sh', str(HELPER)], env=environment,
                              text=True, capture_output=True, check=False)

    def stages(self):
        fields = {}
        for line in self.record.read_text().splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                fields[key] = value
        return fields

    def test_a_ready_keyboard_is_left_alone(self):
        self.write_state('READY', 1)
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.stages()['debian_stage'], 'pogo-ok')
        self.assertNotIn('hard rearm', result.stdout)

    def test_an_absent_keyboard_is_not_touched(self):
        self.write_state('DETACHED', 0)
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.stages()['debian_stage'], 'pogo-absent')

    def test_an_attached_but_detached_keyboard_is_rearmed(self):
        # Exactly the test 178 state: the early probe saw connect=1 but gave up,
        # and a later hard rearm brings the keyboard up.  The watcher plays the
        # driver: it answers the helper's "hard" write with state=READY.
        self.write_state('DETACHED', 1)
        watcher = subprocess.Popen(
            ['/bin/sh', '-c',
             f'while :; do if grep -q hard {self.sysfs} 2>/dev/null; then '
             f'printf "state=READY\\nconnect=1\\nready=1\\n" > {self.sysfs}; exit 0; fi; '
             f'sleep 0.05; done'])
        try:
            result = self.run_helper()
        finally:
            watcher.wait(timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        fields = self.stages()
        self.assertEqual(fields['debian_stage'], 'pogo-recovered')
        self.assertEqual(fields['debian_failure'], 'none')
        self.assertIn('hard rearm', result.stdout)

    def test_a_failed_rearm_is_recorded_without_failing_the_boot(self):
        self.write_state('DETACHED', 1)
        started = time.monotonic()
        result = self.run_helper(GTS9_POGO_WINDOW_SECONDS='2',
                                 GTS9_POGO_REARM_WAIT_SECONDS='1')
        elapsed = time.monotonic() - started
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(elapsed, 15, 'the recovery wait must stay bounded')
        fields = self.stages()
        self.assertEqual(fields['debian_stage'], 'pogo-recovery-failed')
        self.assertEqual(fields['debian_failure'], 'pogo-recovery-failed')

    def test_a_late_driver_reconnect_is_recognised(self):
        # Test 178: the driver's own hot-reconnect brought the keyboard up at
        # 34 s, so the service must report pogo-recovered rather than absent.
        self.write_state('DETACHED', 0)
        watcher = subprocess.Popen(
            ['/bin/sh', '-c',
             f'sleep 1; printf "state=READY\\nconnect=1\\nready=1\\n" > {self.sysfs}'])
        try:
            result = self.run_helper(GTS9_POGO_WINDOW_SECONDS='6',
                                     GTS9_POGO_POLL_SECONDS='1')
        finally:
            watcher.wait(timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.stages()['debian_stage'], 'pogo-recovered')

    def test_missing_driver_is_reported_as_absent(self):
        result = self.run_helper(env={'GTS9_POGO_SYSFS': str(self.root / 'nope')})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.stages()['debian_stage'], 'pogo-absent')

    def test_service_observes_in_the_background_and_blocks_nothing(self):
        # Type=simple: a oneshot wanted by multi-user.target would hold the
        # target until the whole observation window had elapsed.
        self.assertIn('Type=simple', UNIT)
        self.assertIn('ExecStart=/usr/libexec/gts9-pogo-recover', UNIT)
        self.assertIn('After=local-fs.target', UNIT)
        self.assertIn('WantedBy=multi-user.target', UNIT)
        self.assertNotIn('Requires=', UNIT)
        self.assertNotIn('Before=multi-user.target', UNIT)
        self.assertNotIn('reboot', UNIT)
        self.assertNotIn('panic', UNIT)

    def test_helper_uses_the_drivers_own_rearm_interface(self):
        self.assertIn('/sys/bus/i2c/devices/5-002a/rearm', HELPER_TEXT)
        self.assertIn('echo hard > "$POGO_SYSFS"', HELPER_TEXT)
        self.assertIn('= READY', HELPER_TEXT)
        self.assertIn('GTS9_POGO_WINDOW_SECONDS', HELPER_TEXT)
        self.assertIn('pogo-recovered', HELPER_TEXT)

    def test_helper_never_reboots_or_masks_a_failure(self):
        for forbidden in ('reboot', 'poweroff', 'panic', 'systemctl'):
            self.assertNotIn(forbidden, HELPER_CODE, forbidden)

    def test_helper_has_no_bash_only_features(self):
        for bashism in ('[[', 'declare ', 'local ', 'function '):
            self.assertNotIn(bashism, HELPER_CODE, bashism)


if __name__ == '__main__':
    unittest.main()
