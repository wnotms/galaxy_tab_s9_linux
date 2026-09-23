"""Host checks for the optional Debian microSD boot (gts9_rootfs=)."""
import os
import pty
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INIT = (ROOT / 'boot' / 'bringup-init.sh').read_text()
MINIMAL_INIT = (ROOT / 'boot' / 'minimal-rootfs-init.sh').read_text()
MINIMAL_STATE = (ROOT / 'boot' / 'minimal-rootfs-state.sh').read_text()
CMDLINE = (ROOT / 'boot' / 'cmdline.example.txt').read_text()
MINIMAL_CMDLINE = (ROOT / 'boot' / 'cmdline.minimal-rootfs.example.txt').read_text()
TRACE_CMDLINE = (ROOT / 'boot' / 'cmdline.boot-trace.example.txt').read_text()
OVERLAY = ROOT / 'rootfs-overlay' / 'usr'


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

    def test_boot_stages_and_failure_codes_are_reported(self):
        for stage in ('kernel-userspace', 'framebuffer-control-available',
                      'framebuffer-control-unavailable', 'waiting-mmc', 'mmc-found',
                      'mounting-root', 'root-mounted',
                      'init-found', 'switch-root'):
            self.assertIn(f'record_boot_stage {stage}', INIT)
        for failure in ('mmc-timeout', 'root-mount', 'missing-init',
                        'missing-switch-root', 'switch-root-returned'):
            self.assertIn(f'record_boot_failure {failure}', INIT)
        self.assertIn('GTS9_BOOT_STAGE=', INIT)
        self.assertIn('GTS9_BOOT_FAIL=', INIT)

    def test_panel_boot_trace_is_opt_in_and_covers_reports(self):
        normal_tokens = CMDLINE.split()
        trace_tokens = TRACE_CMDLINE.split()
        self.assertNotIn('gts9_boot_trace_console=1', normal_tokens)
        self.assertIn('gts9_boot_trace_console=1', trace_tokens)
        self.assertIn('gts9_boot_trace_console=*)', INIT)
        self.assertIn('[ "$BOOT_TRACE_CONSOLE" = 1 ] || return 0', INIT)
        self.assertIn('GTS9_BOOT_REPORT_BEGIN=$report_title', INIT)
        self.assertIn('GTS9_BOOT_REPORT_END=$report_title status=$report_status', INIT)
        self.assertIn('if [ "$BOOT_TRACE_CONSOLE" = 1 ]; then\n            echo "exit_status=$report_status"',
                      INIT)
        proc_mount = INIT.index('mount_path proc /proc')
        trace_option = INIT.index('gts9_boot_trace_console=*)')
        first_stage = INIT.index('record_boot_stage kernel-userspace')
        self.assertLess(proc_mount, trace_option)
        self.assertLess(trace_option, first_stage)

    def test_boot_trace_tty_stays_available_after_dev_move(self):
        start = INIT.index('trace_boot_console() {')
        end = INIT.index('\n}\n', start) + 2
        trace_function = INIT[start:end].replace(
            '/dev/tty0', '"$GTS9_TEST_TTY"')

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dev = root / 'dev'
            moved_dev = root / 'newroot' / 'dev'
            dev.mkdir()
            moved_dev.parent.mkdir()
            master_fd, slave_fd = pty.openpty()
            try:
                tty_path = os.ttyname(slave_fd)
                (dev / 'tty0').symlink_to(tty_path)
                shell_script = '\n'.join((
                    'BOOT_TRACE_CONSOLE=1',
                    'BOOT_TRACE_CONSOLE_FD_OPEN=0',
                    trace_function,
                    'trace_boot_console before-dev-move',
                    f'mv {shlex.quote(str(dev))} {shlex.quote(str(moved_dev))}',
                    'trace_boot_console after-dev-move',
                    'exec 3>&-',
                    '[ ! -e /proc/$$/fd/3 ]',
                ))
                env = dict(os.environ, GTS9_TEST_TTY=str(dev / 'tty0'))
                result = subprocess.run(
                    ['/bin/sh', '-c', shell_script],
                    env=env, text=True, capture_output=True, check=False)
                output = os.read(master_fd, 4096).decode()
            finally:
                os.close(master_fd)
                os.close(slave_fd)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('before-dev-move', output)
        self.assertIn('after-dev-move', output)
        self.assertIn('exec switch_root /newroot /sbin/init 3>&-', INIT)

    def test_rootfs_diagnostic_is_written_only_after_mount(self):
        mount = INIT.index("log 'gts9-rootfs: rootfs mounted rw'")
        diagnostic = INIT.index('BOOT_DIAG_FILE=/newroot/var/log/gts9-last-boot-stage')
        self.assertLess(mount, diagnostic)
        self.assertIn('boot_id=%s', INIT)
        self.assertIn('cmdline=%s', INIT)
        self.assertIn('mmc_regulators=%s', INIT)
        self.assertIn('mmc_log=%s', INIT)

    def test_failed_handoff_is_explicit_on_tty1(self):
        self.assertIn('GTS9 rescue shell', INIT)
        self.assertIn('rootfs handoff failed', INIT)
        self.assertIn('reason: %s', INIT)
        self.assertIn('last stage: %s', INIT)

    def test_debian_stage_units_have_distinct_boot_and_poweroff_markers(self):
        unit_dir = OVERLAY / 'lib' / 'systemd' / 'system'
        boot = (unit_dir / 'gts9-boot-stage.service').read_text()
        getty = (unit_dir / 'gts9-getty-stage.service').read_text()
        poweroff = (unit_dir / 'gts9-poweroff-stage.service').read_text()
        marker = (OVERLAY / 'libexec' / 'gts9-record-poweroff-stage').read_text()

        self.assertIn('ExecStart=/bin/sh /usr/libexec/gts9-record-boot-stage systemd-basic',
                      boot)
        self.assertIn('ExecStart=', getty)
        self.assertIn('After=umount.target', poweroff)
        self.assertIn('Before=systemd-poweroff.service', poweroff)
        self.assertIn('stage=systemd-poweroff-service', marker)
        self.assertIn('boot_id=%s', marker)

    def test_timers_disabled_in_rootfs_mode(self):
        self.assertIn('proof and recovery timers disabled', INIT)

    def test_minimal_cmdline_recovers_from_a_panic(self):
        # A panicking kernel with panic=0 leaves the tablet hung with no USB
        # and no key response (test 178 boots #2 and #3); the minimal profile
        # must reboot instead so the device stays reachable.
        tokens = MINIMAL_CMDLINE.split()
        self.assertIn('panic=10', tokens)
        self.assertNotIn('panic=0', tokens)
        normal = CMDLINE.split()
        self.assertIn('panic=0', normal,
                      'the full bring-up cmdline is not being changed here')

    def test_cmdline_profile(self):
        tokens = CMDLINE.split()
        self.assertIn('gts9_rootfs=/dev/mmcblk1p1', tokens)
        for gone in ('gts9_proof_code', 'gts9_proof_action', 'gts9_reboot_after',
                     'console=tty0', 'ignore_loglevel'):
            self.assertFalse(any(t.startswith(gone) for t in tokens), gone)
        self.assertIn('console=ttyMSM0,115200n8', tokens)
        self.assertIn('earlycon', tokens)
        self.assertIn('fbcon=font:TER16x32', tokens)

    def test_minimal_profile_is_opt_in_and_branches_before_bringup(self):
        normal_tokens = CMDLINE.split()
        minimal_tokens = MINIMAL_CMDLINE.split()
        self.assertNotIn('gts9_minimal_rootfs=1', normal_tokens)
        self.assertIn('gts9_minimal_rootfs=1', minimal_tokens)
        self.assertIn('gts9_rootfs=/dev/mmcblk1p1', minimal_tokens)
        branch = INIT.index('exec /minimal-rootfs-init')
        self.assertLess(branch, INIT.index('mount_path sysfs /sys'))
        self.assertLess(branch, INIT.index('display_recover\n'))
        self.assertLess(branch, INIT.index('setup_usb_gadget\n'))
        self.assertLess(branch, INIT.index('report \'regulator summary\''))

    def test_minimal_profile_stage_order_and_bounded_root_wait(self):
        stages = ('kernel-userspace', 'waiting-root', 'root-found',
                  'mounting-root', 'root-mounted', 'init-found', 'switch-root')
        offsets = [MINIMAL_INIT.index(f'minimal_state_stage {stage}') for stage in stages]
        self.assertEqual(offsets, sorted(offsets))
        for failure in ('root-timeout', 'root-mount', 'missing-init',
                        'switch-root-returned'):
            self.assertIn(f'minimal_fail {failure}', MINIMAL_INIT)
        self.assertIn('GTS9_MINIMAL_FAIL=$GTS9_MINIMAL_FAILURE', MINIMAL_STATE)
        self.assertIn('ROOTFS_WAIT_SECONDS=30', MINIMAL_INIT)
        self.assertIn('exec switch_root /newroot "$MINIMAL_INIT"', MINIMAL_INIT)
        self.assertIn('MINIMAL_INIT=/sbin/init', MINIMAL_INIT)
        self.assertIn('if [ ! -x /newroot/sbin/init ]', MINIMAL_INIT)
        self.assertIn('cp /bin/busybox /run/busybox', MINIMAL_INIT)

    def test_minimal_profile_rescue_does_not_depend_on_panel_or_usb(self):
        self.assertIn('cat /proc/partitions', MINIMAL_INIT)
        self.assertIn('ls -l /sys/class/block', MINIMAL_INIT)
        self.assertIn('ls -l /dev/mmcblk*', MINIMAL_INIT)
        self.assertIn('/bin/sh -i </dev/console >/dev/console 2>&1', MINIMAL_INIT)
        for noncritical in ('display_recover', 'setup_usb_gadget', 'gpt_entries',
                            'rtc_write_state', 'regulator_summary', 'clk_summary'):
            self.assertNotIn(noncritical, MINIMAL_INIT)
        self.assertNotIn('reboot', MINIMAL_INIT)
        self.assertNotIn('poweroff', MINIMAL_INIT)

    def test_minimal_initramfs_requires_switch_root_and_installs_profile(self):
        builder = (ROOT / 'scripts' / 'build-bringup-initramfs.sh').read_text()
        pid1 = (ROOT / 'boot' / 'gts9-minimal-pid1.c').read_text()
        self.assertIn("'sh mount umount switch_root", builder)
        self.assertIn('minimal_init_src=', builder)
        self.assertIn('install -m 0755 "$minimal_init_src" "$tree/minimal-rootfs-init"',
                      builder)
        self.assertIn('minimal_state_src=', builder)
        self.assertIn('install -m 0644 "$minimal_state_src" "$tree/minimal-rootfs-state.sh"',
                      builder)
        self.assertIn('gts9-minimal-pid1', builder)
        self.assertIn('GTS9_MINIMAL_FAIL=switch-root-returned', pid1)
        self.assertIn('SYS_execve', pid1)


if __name__ == '__main__':
    unittest.main()
