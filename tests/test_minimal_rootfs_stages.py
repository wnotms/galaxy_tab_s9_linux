"""Host checks for the persistent minimal-rootfs boot-stage record.

The record is the only boot evidence that survives a black panel and an absent
USB console, so its format, its ordering and its atomic replacement are all
tested here without a tablet.
"""
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INIT = (ROOT / 'boot' / 'minimal-rootfs-init.sh').read_text()
STATE = (ROOT / 'boot' / 'minimal-rootfs-state.sh')
BUILDER = (ROOT / 'scripts' / 'build-bringup-initramfs.sh').read_text()

REQUIRED_KEYS = (
    'format_version', 'origin', 'boot_id', 'kernel_release', 'cmdline',
    'timestamp', 'uptime_seconds', 'root_device', 'stage', 'stage_history',
    'failure', 'mmc_devices',
)
INITRAMFS_STAGES = ('kernel-userspace', 'waiting-root', 'root-found',
                    'mounting-root', 'root-mounted', 'init-found', 'switch-root')


def run_library(tmp, body, extra_env=None):
    """Source minimal-rootfs-state.sh in sh and run body; return CompletedProcess."""
    env = dict(os.environ)
    env['GTS9_MINIMAL_LOG_DIR'] = tmp
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ['/bin/sh', '-c', f'. {STATE}\n{body}'],
        env=env, text=True, capture_output=True, check=False)


def parse_record(path):
    fields = {}
    for line in Path(path).read_text().splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            fields[key] = value
    return fields


class MinimalRootfsStateTests(unittest.TestCase):
    def test_record_is_installed_and_sourced_by_the_profile(self):
        self.assertIn('/minimal-rootfs-state.sh', INIT)
        self.assertIn('. "$MINIMAL_STATE_LIB"', INIT)
        self.assertIn('install -m 0644 "$minimal_state_src" "$tree/minimal-rootfs-state.sh"',
                      BUILDER)

    def test_persistence_begins_only_after_the_root_mount(self):
        mount = INIT.index('mount -t ext4 -o rw "$ROOTFS_DEVICE" /newroot')
        root_mounted = INIT.index('minimal_state_stage root-mounted')
        persist = INIT.index('minimal_state_persist_enable /newroot/var/log')
        init_found = INIT.index('minimal_state_stage init-found')
        self.assertLess(mount, root_mounted)
        self.assertLess(root_mounted, persist)
        self.assertLess(persist, init_found)
        # The record is written into the mounted Debian root, never into the
        # initramfs, and there is exactly one place that enables persistence.
        self.assertEqual(INIT.count('minimal_state_persist_enable /newroot/var/log'), 1)
        self.assertIn('GTS9_MINIMAL_PERSIST=${GTS9_MINIMAL_PERSIST:-0}',
                      STATE.read_text())
        self.assertIn('[ "$GTS9_MINIMAL_PERSIST" = 1 ] || return 0',
                      STATE.read_text())

    def test_switch_root_marker_is_flushed_before_the_handoff(self):
        marker = INIT.index('minimal_state_stage switch-root')
        sync = INIT.index('\nsync\n', marker)
        synced = INIT.index('minimal_state_stage switch-root-synced')
        exec_ = INIT.index('exec switch_root /newroot "$MINIMAL_INIT"')
        self.assertLess(marker, sync)
        self.assertLess(sync, synced)
        self.assertLess(synced, exec_)
        # switch-root-synced is the last thing written before the handoff, and
        # it is what separates "the standalone sync hung" from "the handoff
        # failed" when the record stops there.
        self.assertEqual(INIT[synced:exec_].splitlines()[-1].strip(),
                         'minimal_state_stage switch-root-synced')

    def test_trampoline_is_self_tested_before_the_handoff(self):
        # Bounded, so a hung trampoline cannot freeze PID 1 (test 178 #3).
        self.assertIn('timeout 5 /run/gts9-minimal-pid1 selftest "$SELFTEST_FILE"',
                      INIT)
        self.assertIn('minimal_state_stage switch-root-selftest-ok', INIT)
        self.assertIn('minimal_state_stage switch-root-selftest-failed', INIT)
        self.assertIn('MINIMAL_INIT=/sbin/init', INIT)
        selftest = INIT.index('selftest "$SELFTEST_FILE"')
        move = INIT.index('MOVED_VFS=')
        self.assertLess(selftest, move)

    def test_the_handoff_checks_the_staged_helper_in_the_new_root(self):
        self.assertIn('[ ! -x /newroot/run/gts9-minimal-pid1 ]', INIT)
        self.assertIn('gts9_minimal_init=*) MINIMAL_INIT=${arg#gts9_minimal_init=}',
                      INIT)
        # The handoff init is a variable: the proven direct /sbin/init path is
        # the default, and the trampoline is opt-in from the cmdline.
        self.assertIn('MINIMAL_INIT=/sbin/init', INIT)
        self.assertIn('gts9_minimal_init=*) MINIMAL_INIT=${arg#gts9_minimal_init=}',
                      INIT)

    def test_every_required_stage_is_recorded_in_order(self):
        offsets = [INIT.index(f'minimal_state_stage {stage}')
                   for stage in INITRAMFS_STAGES]
        self.assertEqual(offsets, sorted(offsets))

    def test_record_fields_are_documented_by_the_writer(self):
        for key in REQUIRED_KEYS:
            self.assertIn(f"printf '{key}=", STATE.read_text(), key)

    def test_stage_history_stays_in_ram_until_the_root_is_mounted(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_library(tmp, (
                'minimal_state_init\n'
                'minimal_state_stage kernel-userspace\n'
                'minimal_state_stage waiting-root\n'
                'minimal_state_stage root-found\n'
                f'[ ! -e {tmp}/gts9-minimal-last-boot ]\n'
                'echo "history=$GTS9_MINIMAL_STAGE_HISTORY"\n'
            ))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('GTS9_MINIMAL_STAGE=kernel-userspace', result.stdout)
            self.assertIn('GTS9_MINIMAL_STAGE=waiting-root', result.stdout)
            self.assertIn('history=kernel-userspace,waiting-root,root-found',
                          result.stdout)
            self.assertFalse(os.path.exists(f'{tmp}/gts9-minimal-last-boot'))

    def test_full_history_is_written_once_the_root_is_mounted(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_library(tmp, (
                'minimal_state_init\n'
                + ''.join(f'minimal_state_stage {stage}\n' for stage in INITRAMFS_STAGES)
                + 'minimal_state_persist_enable "$GTS9_MINIMAL_LOG_DIR"\n'
            ))
            self.assertEqual(result.returncode, 0, result.stderr)
            record = f'{tmp}/gts9-minimal-last-boot'
            self.assertTrue(os.path.exists(record))
            fields = parse_record(record)
            self.assertEqual(set(fields), set(REQUIRED_KEYS))
            self.assertEqual(fields['format_version'], '1')
            self.assertEqual(fields['origin'], 'initramfs')
            self.assertEqual(fields['stage'], 'switch-root')
            self.assertEqual(fields['stage_history'], ','.join(INITRAMFS_STAGES))
            self.assertEqual(fields['failure'], 'none')
            self.assertTrue(fields['boot_id'])
            self.assertTrue(fields['kernel_release'])
            self.assertNotEqual(fields['stage_history'], '')
            self.assertFalse(os.path.exists(f'{record}.tmp'))

    def test_later_stages_update_the_record_without_losing_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_library(tmp, (
                'minimal_state_init\n'
                'minimal_state_stage root-mounted\n'
                'minimal_state_persist_enable "$GTS9_MINIMAL_LOG_DIR"\n'
                'minimal_state_stage init-found\n'
                'minimal_state_stage switch-root\n'
            ))
            self.assertEqual(result.returncode, 0, result.stderr)
            record = f'{tmp}/gts9-minimal-last-boot'
            fields = parse_record(record)
            self.assertEqual(fields['stage'], 'switch-root')
            self.assertEqual(fields['stage_history'],
                             'root-mounted,init-found,switch-root')
            self.assertFalse(os.path.exists(f'{record}.tmp'))

    def test_failure_is_recorded_with_the_last_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_library(tmp, (
                'minimal_state_init\n'
                'minimal_state_stage kernel-userspace\n'
                'minimal_state_stage waiting-root\n'
                'minimal_state_persist_enable "$GTS9_MINIMAL_LOG_DIR"\n'
                'minimal_state_fail root-timeout\n'
            ))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('GTS9_MINIMAL_FAIL=root-timeout', result.stdout)
            self.assertIn('GTS9_MINIMAL_LAST_STAGE=waiting-root', result.stdout)
            fields = parse_record(f'{tmp}/gts9-minimal-last-boot')
            self.assertEqual(fields['failure'], 'root-timeout')
            self.assertEqual(fields['stage'], 'waiting-root')

    def test_repeated_stages_do_not_grow_the_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_library(tmp, (
                'minimal_state_init\n'
                'minimal_state_stage root-mounted\n'
                'minimal_state_stage root-mounted\n'
                'minimal_state_persist_enable "$GTS9_MINIMAL_LOG_DIR"\n'
            ))
            self.assertEqual(result.returncode, 0, result.stderr)
            fields = parse_record(f'{tmp}/gts9-minimal-last-boot')
            self.assertEqual(fields['stage_history'], 'root-mounted')

    def test_record_is_replaced_atomically_while_being_updated(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = f'{tmp}/gts9-minimal-last-boot'
            writer = subprocess.Popen(
                ['/bin/sh', '-c',
                 f'. {STATE}\n'
                 'minimal_state_init\n'
                 'minimal_state_stage root-mounted\n'
                 'minimal_state_persist_enable "$GTS9_MINIMAL_LOG_DIR"\n'
                 'i=0\n'
                 'while [ "$i" -lt 20 ]; do\n'
                 '  i=$((i + 1))\n'
                 '  minimal_state_stage "stage-$i"\n'
                 'done\n'],
                env=dict(os.environ, GTS9_MINIMAL_LOG_DIR=tmp),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            deadline = time.time() + 30
            observations = 0
            try:
                while writer.poll() is None and time.time() < deadline:
                    if os.path.exists(record):
                        fields = parse_record(record)
                        # A half-written file would miss fields or be empty.
                        self.assertEqual(set(fields), set(REQUIRED_KEYS))
                        observations += 1
                    time.sleep(0.005)
            finally:
                writer.wait(timeout=30)
            self.assertEqual(writer.returncode, 0)
            self.assertGreater(observations, 0)
            self.assertFalse(os.path.exists(f'{record}.tmp'))

    def test_record_is_created_when_var_log_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, 'newroot', 'var', 'log')
            result = run_library(tmp, (
                'minimal_state_init\n'
                'minimal_state_stage root-mounted\n'
                f'minimal_state_persist_enable {target}\n'
            ))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(os.path.exists(os.path.join(target,
                                                        'gts9-minimal-last-boot')))

    def test_library_has_no_dependency_on_bash_only_features(self):
        # The initramfs runs BusyBox ash; keep the library POSIX.
        for bashism in ('[[', 'declare ', 'local ', 'function ', '${!'):
            self.assertNotIn(bashism, STATE.read_text(), bashism)


    def test_boot_facts_are_frozen_before_the_vfs_move(self):
        """After /dev /proc /sys /run move, the old paths are empty.

        The switch-root write happens after that move, so the facts must be
        captured while they are still readable - otherwise the record that
        TWRP reads says cmdline=unavailable and boot_id=unknown.
        """
        with tempfile.TemporaryDirectory() as tmp:
            result = run_library(tmp, (
                'minimal_state_init\n'
                'minimal_state_stage root-mounted\n'
                'minimal_state_persist_enable "$GTS9_MINIMAL_LOG_DIR"\n'
                # Simulate the move: the old paths no longer answer.
                'minimal_state_boot_id() { echo unknown; }\n'
                'minimal_state_kernel_release() { echo unknown; }\n'
                'minimal_state_cmdline() { echo unavailable; }\n'
                'minimal_state_mmc_devices() { echo none; }\n'
                'minimal_state_stage switch-root\n'
            ))
            self.assertEqual(result.returncode, 0, result.stderr)
            fields = parse_record(f'{tmp}/gts9-minimal-last-boot')
            self.assertEqual(fields['stage'], 'switch-root')
            self.assertNotEqual(fields['cmdline'], 'unavailable')
            self.assertNotEqual(fields['boot_id'], 'unknown')
            self.assertNotEqual(fields['kernel_release'], 'unknown')
            self.assertNotEqual(fields['mmc_devices'], 'none')

    def test_the_builder_links_every_applet_the_minimal_path_calls(self):
        """A missing applet only fails on the tablet; catch it at build time.

        rm was absent from the linked applets until the state library started
        removing its temporary file, which would have printed 'rm: not found'
        on a device whose only report channel is that file.
        """
        required = BUILDER.split("required_applets='", 1)[1].split("'", 1)[0].split()
        report = BUILDER.split("report_applets='", 1)[1].split("'", 1)[0].split()
        linked = set(required) | set(report)
        used = ('sh', 'mount', 'umount', 'switch_root', 'cat', 'uname', 'ls',
                'mkdir', 'cp', 'mv', 'rm', 'chmod', 'sync', 'sleep', 'grep',
                'printf', 'cut', 'date')
        for applet in used:
            self.assertIn(applet, linked,
                          f'{applet} must be linked into the initramfs')


class MinimalPid1HandoverEvidence(unittest.TestCase):
    """The trampoline is the last place that can write evidence to disk."""

    SOURCE = (ROOT / 'boot' / 'gts9-minimal-pid1.c').read_text()

    def test_trampoline_records_its_handover_on_the_debian_root(self):
        for marker in ('trampoline=entered', 'trampoline=exec-init /sbin/init',
                       'trampoline=exec-failed errno=',
                       'trampoline=watchdog-started', 'trampoline=alive-',
                       'trampoline=pid1 ', 'trampoline=diagnostics-dumped',
                       'trampoline=selftest-ok',
                       '/var/log/gts9-minimal-dmesg.txt'):
            self.assertIn(marker, self.SOURCE, marker)
        # The selftest must be an early branch that exits, and must be able to
        # write to the path it is given.
        self.assertIn('str_eq(argv[1], "selftest")', self.SOURCE)
        self.assertIn('exit_now(0)', self.SOURCE)
        # Markers must be durable: a force power-off after a hang lost the
        # unsynced appends once already.
        self.assertIn('SYS_sync', self.SOURCE)
        self.assertIn('sys_call6(SYS_sync, 0, 0, 0, 0, 0, 0);', self.SOURCE)
        self.assertIn('/var/log/gts9-minimal-last-boot', self.SOURCE)
        self.assertIn('/proc/1/comm', self.SOURCE)
        self.assertIn('O_APPEND', self.SOURCE)
        self.assertIn('O_CREAT', self.SOURCE)

    def test_watchdog_survives_the_exec_and_record_is_opened_once(self):
        # The watchdog is forked before exec'ing init, so it outlives the
        # handover; and the record descriptor is opened exactly once, so a
        # later write can never recreate a half file at the record path.
        self.assertLess(self.SOURCE.index('watchdog_loop();'),
                        self.SOURCE.index('record_write(marker_exec);'))
        # Opened once for the real handover (the selftest opens its own path).
        self.assertEqual(self.SOURCE.count('record_open_at(RECORD_PATH);'), 1)
        self.assertIn('static long record_fd = -1;', self.SOURCE)

    def test_trampoline_compiles_static_and_contains_the_markers(self):
        clang = shutil.which('clang')
        if not clang or not shutil.which('ld.lld'):
            self.skipTest('clang/ld.lld is unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            binary = os.path.join(tmp, 'gts9-minimal-pid1')
            build = subprocess.run(
                [clang, '--target=aarch64-linux-gnu', '-nostdlib', '-static',
                 '-ffreestanding', '-fno-stack-protector', '-fno-builtin',
                 '-fuse-ld=lld', '-Wl,--build-id=none', '-Wl,-n',
                 '-o', binary, str(ROOT / 'boot' / 'gts9-minimal-pid1.c')],
                text=True, capture_output=True, check=False)
            self.assertEqual(build.returncode, 0, build.stderr)
            strings = subprocess.run(['strings', '-a', binary], text=True,
                                     capture_output=True, check=True).stdout
            for marker in ('trampoline=entered', 'trampoline=exec-init',
                           'trampoline=diagnostics-dumped',
                           '/var/log/gts9-minimal-last-boot',
                           '/var/log/gts9-minimal-dmesg.txt',
                           '/proc/1/comm'):
                self.assertIn(marker, strings, marker)
            headers = subprocess.run(['readelf', '-l', binary], text=True,
                                     capture_output=True, check=True).stdout
            self.assertNotIn('INTERP', headers)


class MinimalRootfsStateHostSupport(unittest.TestCase):
    def test_sh_is_available_for_the_functional_tests(self):
        self.assertTrue(shutil.which('sh'))


if __name__ == '__main__':
    unittest.main()
