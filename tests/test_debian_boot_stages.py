"""Host checks for the Debian half of the minimal-rootfs boot record."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OVERLAY = ROOT / 'rootfs-overlay' / 'usr'
HELPER = OVERLAY / 'libexec' / 'gts9-record-debian-stage'
UNIT_DIR = OVERLAY / 'lib' / 'systemd' / 'system'

INITRAMFS_RECORD = """\
format_version=1
origin=initramfs
boot_id=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee
kernel_release=7.2.0-rc3-gts9wifi-dirty
cmdline=console=ttyMSM0,115200n8 gts9_minimal_rootfs=1 gts9_rootfs=/dev/mmcblk1p1
timestamp=2026-09-24T00:00:00Z
uptime_seconds=3
root_device=/dev/mmcblk1p1
stage=switch-root
stage_history=kernel-userspace,waiting-root,root-found,mounting-root,root-mounted,init-found,switch-root
failure=none
mmc_devices=/dev/mmcblk1,/dev/mmcblk1p1
"""


def run_helper(record, *args):
    return subprocess.run(
        ['sh', str(HELPER), *args],
        env=dict(os.environ, GTS9_MINIMAL_BOOT_RECORD=str(record)),
        text=True, capture_output=True, check=False)


def parse(path):
    fields = {}
    for line in Path(path).read_text().splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            fields[key] = value
    return fields


class DebianStageUnits(unittest.TestCase):
    def unit(self, name):
        return (UNIT_DIR / name).read_text()

    def test_entry_unit_runs_early_and_records_entry(self):
        unit = self.unit('gts9-debian-entered.service')
        self.assertIn('DefaultDependencies=no', unit)
        self.assertIn('After=local-fs.target', unit)
        self.assertIn('Before=basic.target', unit)
        self.assertIn('ConditionPathExists=/var/log/gts9-minimal-last-boot', unit)
        self.assertIn('/usr/libexec/gts9-record-debian-stage systemd-entered local-fs',
                      unit)

    def test_every_stage_unit_is_skipped_without_the_minimal_record(self):
        # A regular bring-up boot writes /var/log/gts9-last-boot-stage; these
        # units must not touch it.
        for name in ('gts9-debian-entered.service',
                     'gts9-debian-basic-stage.service',
                     'gts9-debian-getty-stage.service',
                     'gts9-debian-multi-user-stage.service'):
            unit = self.unit(name)
            self.assertIn('ConditionPathExists=/var/log/gts9-minimal-last-boot',
                          unit, name)

    def test_stage_units_record_the_documented_stages(self):
        self.assertIn('gts9-record-debian-stage basic',
                      self.unit('gts9-debian-basic-stage.service'))
        getty = self.unit('gts9-debian-getty-stage.service')
        self.assertIn('tty1-getty-active', getty)
        self.assertIn('tty1-getty-inactive', getty)
        self.assertIn('--failure', getty)
        self.assertIn('gts9-record-debian-stage multi-user',
                      self.unit('gts9-debian-multi-user-stage.service'))

    def test_stage_units_do_not_block_the_boot_targets(self):
        for name in ('gts9-debian-entered.service',
                     'gts9-debian-basic-stage.service',
                     'gts9-debian-getty-stage.service',
                     'gts9-debian-multi-user-stage.service'):
            unit = self.unit(name)
            self.assertIn('Type=oneshot', unit)
            self.assertNotIn('Requires=', unit)
            self.assertNotIn('reboot', unit)
            self.assertNotIn('panic', unit)

    def test_each_stage_unit_can_be_disabled_on_its_own(self):
        for name in ('gts9-debian-entered.service',
                     'gts9-debian-basic-stage.service',
                     'gts9-debian-getty-stage.service',
                     'gts9-debian-multi-user-stage.service'):
            unit = self.unit(name)
            self.assertIn('[Install]', unit)
            self.assertIn('WantedBy=', unit)


class DebianStageHelper(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.record = Path(self.tmp.name) / 'gts9-minimal-last-boot'

    def write_record(self, text=INITRAMFS_RECORD):
        self.record.write_text(text)
        return self.record

    def test_missing_record_is_a_successful_noop(self):
        result = run_helper(self.record, 'systemd-entered')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.record.exists())

    def test_entry_keeps_the_initramfs_block_and_appends_debian_state(self):
        original = self.write_record()
        initramfs_lines = original.read_text().splitlines()
        result = run_helper(original, 'systemd-entered', 'local-fs')
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = self.record.read_text().splitlines()
        self.assertEqual(lines[:len(initramfs_lines)], initramfs_lines)
        fields = parse(self.record)
        self.assertEqual(fields['stage'], 'switch-root')
        self.assertEqual(fields['stage_history'].split(',')[-1], 'switch-root')
        self.assertEqual(fields['debian_origin'], 'debian-systemd')
        self.assertEqual(fields['debian_stage'], 'local-fs')
        self.assertEqual(fields['debian_stage_history'], 'systemd-entered,local-fs')
        self.assertEqual(fields['debian_failure'], 'none')

    def test_entry_records_boot_identity_and_root_source(self):
        original = self.write_record()
        run_helper(original, 'systemd-entered')
        fields = parse(self.record)
        self.assertEqual(fields['debian_boot_id'],
                         Path('/proc/sys/kernel/random/boot_id').read_text().strip())
        self.assertEqual(fields['debian_boot_id_match'], 'no',
                         'the fixture boot_id is not this boot')
        self.assertEqual(fields['debian_kernel_release'],
                         os.uname().release)
        self.assertTrue(fields['debian_root_source'])
        self.assertTrue(fields['debian_root_fstype'])
        self.assertIn('debian_updated_timestamp', fields)
        self.assertIn('debian_updated_uptime_seconds', fields)

    def test_matching_boot_id_is_recorded_as_a_match(self):
        boot_id = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        original = self.write_record(INITRAMFS_RECORD.replace(
            'boot_id=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
            f'boot_id={boot_id}'))
        run_helper(original, 'systemd-entered')
        self.assertEqual(parse(self.record)['debian_boot_id_match'], 'yes')

    def test_stage_markers_are_printed_for_the_journal(self):
        original = self.write_record()
        result = run_helper(original, 'systemd-entered', 'local-fs')
        self.assertIn('GTS9_DEBIAN_STAGE=systemd-entered', result.stdout)
        self.assertIn('GTS9_DEBIAN_STAGE=local-fs', result.stdout)

    def test_history_accumulates_across_units(self):
        original = self.write_record()
        run_helper(original, 'systemd-entered', 'local-fs')
        run_helper(original, 'basic')
        run_helper(original, 'usb-acm-ready')
        run_helper(original, 'multi-user')
        fields = parse(self.record)
        self.assertEqual(fields['debian_stage'], 'multi-user')
        self.assertEqual(fields['debian_stage_history'],
                         'systemd-entered,local-fs,basic,usb-acm-ready,multi-user')
        # The initramfs record is still intact after four rewrites.
        self.assertEqual(fields['stage'], 'switch-root')
        self.assertEqual(fields['failure'], 'none')
        self.assertNotIn('debian_origin=initramfs', Path(self.record).read_text())

    def test_repeated_stages_do_not_grow_the_history(self):
        original = self.write_record()
        run_helper(original, 'local-fs')
        run_helper(original, 'local-fs')
        self.assertEqual(parse(self.record)['debian_stage_history'], 'local-fs')

    def test_failure_and_extra_fields_are_recorded(self):
        original = self.write_record()
        run_helper(original, '--failure', 'tty1-getty-inactive',
                   '--set', 'usb_acm=failed', 'tty1-getty-inactive')
        fields = parse(self.record)
        self.assertEqual(fields['debian_failure'], 'tty1-getty-inactive')
        self.assertEqual(fields['debian_usb_acm'], 'failed')
        self.assertEqual(fields['debian_stage'], 'tty1-getty-inactive')

    def test_unknown_options_and_empty_stage_lists_fail_loudly(self):
        original = self.write_record()
        self.assertEqual(run_helper(original, '--bogus').returncode, 2)
        self.assertEqual(run_helper(original).returncode, 2)
        self.assertEqual(original.read_text(), INITRAMFS_RECORD)

    def test_rewrite_is_atomic(self):
        original = self.write_record()
        run_helper(original, 'systemd-entered', 'local-fs')
        self.assertFalse(Path(f'{self.record}.tmp').exists())
        # A half-written file would lose fields; every intermediate state is
        # a complete record.
        fields = parse(self.record)
        for key in ('format_version', 'boot_id', 'stage', 'stage_history',
                    'failure', 'mmc_devices', 'debian_stage',
                    'debian_stage_history'):
            self.assertIn(key, fields)

    def test_helper_has_no_bash_only_features(self):
        text = HELPER.read_text()
        for bashism in ('[[', 'declare ', 'local ', 'function ', '${!'):
            self.assertNotIn(bashism, text, bashism)


if __name__ == '__main__':
    unittest.main()
