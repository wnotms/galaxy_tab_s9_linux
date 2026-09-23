"""Host checks for the Debian-side X710 panel cold-boot recovery."""
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OVERLAY = ROOT / 'rootfs-overlay' / 'usr'
HELPER = OVERLAY / 'libexec' / 'gts9-panel-recover'
STAGE_HELPER = OVERLAY / 'libexec' / 'gts9-record-debian-stage'
UNIT = (OVERLAY / 'lib/systemd/system/gts9-panel-recover.service').read_text()
HELPER_TEXT = HELPER.read_text()
HELPER_CODE = '\n'.join(line for line in HELPER_TEXT.splitlines()
                        if not line.lstrip().startswith('#'))

ID_FAILURE = 'panel-samsung-ana38407 ae94000.dsi.0: ana38407 panel id: 00 00 00'
ID_OK = 'panel-samsung-ana38407 ae94000.dsi.0: ana38407 panel id: 80 00 04'

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


class PanelRecoverServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.fb_blank = self.root / 'fb0-blank'
        self.fb_blank.write_text('0\n')
        self.log = self.root / 'dmesg.txt'
        self.record = self.root / 'gts9-minimal-last-boot'
        self.record.write_text(INITRAMFS_RECORD)
        self.kmsg = self.root / 'kmsg'

    def run_helper(self, env=None, **overrides):
        environment = dict(os.environ,
                           GTS9_PANEL_FB_BLANK=str(self.fb_blank),
                           GTS9_PANEL_DMESG_FILE=str(self.log),
                           GTS9_PANEL_KMSG=str(self.kmsg),
                           GTS9_STAGE_HELPER=str(STAGE_HELPER),
                           GTS9_MINIMAL_BOOT_RECORD=str(self.record),
                           GTS9_PANEL_FB_WAIT_SECONDS='2',
                           GTS9_PANEL_ID_WAIT_SECONDS='1',
                           GTS9_PANEL_SETTLE_SECONDS='1',
                           GTS9_PANEL_CYCLES='3',
                           GTS9_PANEL_CYCLE_TIMEOUT='2')
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

    def recover_in_background(self):
        """Simulate the driver logging the good ID once the panel is unblanked."""
        return subprocess.Popen(
            ['/bin/sh', '-c',
             f'while :; do if [ "$(cat {self.fb_blank})" = 0 ]; then '
             f'echo "{ID_OK}" >> {self.log}; exit 0; fi; sleep 0.05; done'])

    def test_a_zero_id_is_recovered_by_a_framebuffer_cycle(self):
        self.log.write_text(ID_FAILURE + '\n')
        watcher = self.recover_in_background()
        try:
            result = self.run_helper()
        finally:
            watcher.wait(timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.fb_blank.read_text().strip(), '0',
                         'the panel must be left unblanked')
        fields = self.stages()
        self.assertEqual(fields['debian_stage'], 'panel-recovered')
        self.assertIn('panel-recovered', fields['debian_stage_history'])
        self.assertIn('recovered panel ID 80 00 04', result.stdout)

    def test_a_healthy_panel_is_left_alone(self):
        self.log.write_text(ID_OK + '\n')
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.stages()['debian_stage'], 'panel-ok')
        self.assertNotIn('cycling the framebuffer', result.stdout)

    def test_no_failure_recorded_means_nothing_to_do(self):
        self.log.write_text('panel-samsung-ana38407 ae94000.dsi.0: probe done\n')
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.stages()['debian_stage'], 'panel-ok')

    def test_missing_framebuffer_is_bounded_and_harmless(self):
        self.log.write_text(ID_FAILURE + '\n')
        started = time.monotonic()
        result = self.run_helper(GTS9_PANEL_FB_BLANK=str(self.root / 'nope' / 'blank'))
        elapsed = time.monotonic() - started
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(elapsed, 10, 'the framebuffer wait must stay bounded')
        self.assertEqual(self.stages()['debian_stage'], 'panel-unavailable')

    def test_exhausted_cycles_are_recorded_without_failing_the_boot(self):
        self.log.write_text(ID_FAILURE + '\n')
        started = time.monotonic()
        result = self.run_helper(GTS9_PANEL_CYCLES='2',
                                 GTS9_PANEL_SETTLE_SECONDS='0')
        elapsed = time.monotonic() - started
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(elapsed, 20)
        fields = self.stages()
        self.assertEqual(fields['debian_stage'], 'panel-recovery-failed')
        self.assertEqual(fields['debian_failure'], 'panel-recovery-failed')
        self.assertIn('did not come up after 2 framebuffer cycles', result.stdout)

    def test_no_kernel_log_source_is_reported_as_unchecked(self):
        result = self.run_helper(GTS9_PANEL_DMESG_FILE=str(self.root / 'missing.txt'))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.stages()['debian_stage'], 'panel-unavailable')
        self.assertIn('no kernel log available', result.stdout)

    def test_service_is_ordered_before_tty1_and_blocks_nothing(self):
        self.assertIn('After=local-fs.target', UNIT)
        self.assertIn('Before=getty@tty1.service', UNIT)
        self.assertIn('Type=oneshot', UNIT)
        self.assertIn('ExecStart=/usr/libexec/gts9-panel-recover', UNIT)
        self.assertIn('WantedBy=multi-user.target', UNIT)
        self.assertNotIn('Requires=', UNIT)
        self.assertNotIn('Before=multi-user.target', UNIT)
        self.assertNotIn('reboot', UNIT)
        self.assertNotIn('panic', UNIT)

    def test_helper_never_reboots_or_panics(self):
        for forbidden in ('reboot', 'poweroff', 'panic', 'systemctl'):
            self.assertNotIn(forbidden, HELPER_CODE, forbidden)

    def test_helper_is_independent_of_the_usb_path(self):
        for forbidden in ('configfs', 'ttyGS0', 'usb_gadget', 'udc',
                          '/dev/mmcblk', '/dev/sd'):
            self.assertNotIn(forbidden, HELPER_CODE, forbidden)

    def test_helper_uses_the_verified_driver_wording(self):
        self.assertIn('ana38407 panel id: 00 00 00', HELPER_TEXT)
        self.assertIn('ana38407 panel id: 80 00 04', HELPER_TEXT)
        self.assertIn('/sys/class/graphics/fb0/blank', HELPER_TEXT)

    def test_helper_has_no_bash_only_features(self):
        for bashism in ('[[', 'declare ', 'local '):
            self.assertNotIn(bashism, HELPER_CODE, bashism)


if __name__ == '__main__':
    unittest.main()
