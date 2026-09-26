"""Host checks for the RTC offset: Samsung's correct time, read before Debian.

The tablet's PMK8550 RTC counts from 1970 and is never set, so before this change
Debian started ~56 years in the past and, with no network, stayed there. Android
and TWRP show the correct time because userspace adds an offset Samsung's time
daemon keeps in `/persist/time/ats_2`. This is the code that reads it.

Two properties are tested more heavily than the arithmetic, because they are the
ones whose failure would be expensive rather than merely wrong:

  * **nothing writes the PMIC RTC.** An SPMI write blocks this kernel
    uninterruptibly (docs/RTC_REPORT.md, tests 021-027), so the offset is applied
    to CLOCK_REALTIME instead of to the counter. A refactor that reached for
    `/dev/rtc0` would reintroduce a hang that cost this project four test cycles.
  * **the persist partition is mounted without writing to it.** `-o ro` alone is
    NOT enough: ext4 still replays the journal on a filesystem that needs
    recovery, which would write to the owner's data to read one file. `noload` is
    the option that makes this read-only in fact rather than in intent.

The real binary is compiled for the host and executed, so the parser, the bounds
and the report line under test are the same code the tablet runs. Only the
syscall instruction and the CLOCK_REALTIME write differ, and the latter exists so
a test cannot move the clock of the machine running it (see GTS9_HOST_TEST in
boot/gts9-rtc-offset.c).
"""
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'boot' / 'gts9-rtc-offset.c'
INIT = (ROOT / 'boot' / 'minimal-rootfs-init.sh').read_text()
PROD_BUILDER = (ROOT / 'scripts' / 'build-minimal-initramfs.sh').read_text()

# The value measured on the tablet: TWRP logged
#   "Setting time offset from file /persist/time/ats_2, offset 1767701103844"
# in reference/boot-tests/test-165-20260923T061249Z/recovery.log. Every assertion
# about the arithmetic is anchored to it rather than to a number invented here.
DEVICE_OFFSET_MS = 1767701103844

# The raw counter mainstream Linux read on 2026-09-25, from the same board:
#   "setting system clock to 1970-09-20T00:32:38 UTC (22638758)"
# in reference/boot-tests/test-198-20260925T1235Z/klog-4.txt.
DEVICE_RAW_SECONDS = 22638758
# raw + offset = 2026-09-25T12:37:41Z, which is when that log was captured.
DEVICE_EXPECTED_EPOCH = 1790339861


def host_build(tmp, offset_bytes=None, epoch_text='22638758\n',
               offset_path=None, epoch_path=None, create_epoch=True):
    """Compile the real source for this host, pointed at a temporary directory.

    Returns (binary, offset_path).  The binary never sets this machine's clock.
    """
    offset_path = offset_path or os.path.join(tmp, 'persist', 'time', 'ats_2')
    epoch_path = epoch_path or os.path.join(tmp, 'since_epoch')

    if offset_bytes is not None:
        os.makedirs(os.path.dirname(offset_path), exist_ok=True)
        with open(offset_path, 'wb') as handle:
            handle.write(offset_bytes)
    if create_epoch:
        with open(epoch_path, 'w') as handle:
            handle.write(epoch_text)

    binary = os.path.join(tmp, 'gts9-rtc-offset-host')
    command = [
        shutil.which('clang'), '-DGTS9_HOST_TEST',
        f'-DGTS9_OFFSET_PATH="{offset_path}"',
        f'-DGTS9_EPOCH_PATH="{epoch_path}"',
        '-nostdlib', '-static', '-ffreestanding', '-fno-stack-protector',
        '-fno-builtin', '-fuse-ld=lld', '-Wl,--build-id=none', '-Wl,-n',
        '-Wall', '-Wextra', '-O2', '-o', binary, str(SOURCE),
    ]
    build = subprocess.run(command, text=True, capture_output=True, check=False)
    if build.returncode != 0:
        raise AssertionError(f'host build failed:\n{build.stderr}')
    return binary, offset_path


def run_helper(binary):
    return subprocess.run([binary], text=True, capture_output=True, check=False)


def fields_of(output):
    """Parse the helper's one-line key=value report."""
    match = re.search(r'^rtc-offset: (.*)$', output.strip(), re.M)
    if not match:
        return {}
    return dict(token.split('=', 1) for token in match.group(1).split())


def clang_available():
    return bool(shutil.which('clang')) and bool(shutil.which('ld.lld'))


_INITRAMFS_MODULE = None


def initramfs_module():
    """The initramfs profile test, imported once for its applet scanner.

    Imported rather than reimplemented: the two must agree about what /init runs,
    and a second scanner that drifted would let a missing applet through.
    """
    global _INITRAMFS_MODULE
    if _INITRAMFS_MODULE is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'initramfs_profiles', ROOT / 'tests' / 'test_initramfs_profiles.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules['initramfs_profiles'] = module
        spec.loader.exec_module(module)
        _INITRAMFS_MODULE = module
    return _INITRAMFS_MODULE


def commands_in(path):
    return initramfs_module().commands_in(path)


class TheOffsetIsReadFromSamsungsOwnFile(unittest.TestCase):
    """The value that makes the clock correct comes off the tablet's disk."""

    def test_the_real_binary_applies_the_measured_device_offset(self):
        if not clang_available():
            self.skipTest('clang/ld.lld is unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            binary, _ = host_build(
                tmp, offset_bytes=struct.pack('<q', DEVICE_OFFSET_MS))
            result = run_helper(binary)
            self.assertEqual(result.returncode, 0, result.stderr)
            fields = fields_of(result.stdout)
            self.assertEqual(fields.get('status'), 'applied')
            self.assertEqual(fields.get('offset_ms'), str(DEVICE_OFFSET_MS))
            self.assertEqual(fields.get('raw_ms'),
                             str(DEVICE_RAW_SECONDS * 1000))
            # The whole point, stated as a date the reader can check.
            self.assertEqual(fields.get('realtime_epoch'),
                             str(DEVICE_EXPECTED_EPOCH))
            self.assertEqual(
                time.strftime('%Y-%m-%dT%H:%M:%SZ',
                              time.gmtime(DEVICE_EXPECTED_EPOCH)),
                '2026-09-25T12:37:41Z')

    def test_the_arithmetic_matches_what_twrp_does_with_the_same_file(self):
        """TWRP adds offset/1000 and offset%1000 separately.

        Adding in milliseconds and dividing once must agree with that to the
        second, or the initramfs and TWRP would disagree about the time on the
        same tablet.
        """
        offset = DEVICE_OFFSET_MS
        raw = DEVICE_RAW_SECONDS
        twrp_seconds = raw + offset // 1000
        ours = (raw * 1000 + offset) // 1000
        self.assertEqual(ours, twrp_seconds)

    def test_it_reads_the_file_as_signed_little_endian_milliseconds(self):
        if not clang_available():
            self.skipTest('clang/ld.lld is unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            # The exact eight bytes on the tablet, and the same value expressed
            # two other ways so a wrong endianness or a wrong width cannot pass.
            binary, _ = host_build(
                tmp, offset_bytes=bytes([0xe4, 0x44, 0x32, 0x93, 0x9b, 0x01,
                                         0x00, 0x00]))
            fields = fields_of(run_helper(binary).stdout)
            self.assertEqual(fields.get('offset_ms'), str(DEVICE_OFFSET_MS))
            self.assertEqual(fields.get('offset_ms'),
                             str(struct.unpack('<q', struct.pack(
                                 '<q', DEVICE_OFFSET_MS))[0]))

    def test_the_first_byte_is_the_least_significant(self):
        """A big-endian read would still parse; it would just be wrong."""
        if not clang_available():
            self.skipTest('clang/ld.lld is unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            binary, _ = host_build(tmp, offset_bytes=struct.pack('>q',
                                                                DEVICE_OFFSET_MS))
            fields = fields_of(run_helper(binary).stdout)
            self.assertNotEqual(fields.get('offset_ms'), str(DEVICE_OFFSET_MS))


class AMissingOrBadOffsetNeverBreaksTheBoot(unittest.TestCase):
    """Every failure path reports and exits; none of them is fatal to a boot.

    The board booted for months with the raw 1970 clock. Getting the offset wrong
    must degrade to exactly that, never to a tablet that will not start.
    """

    def test_no_partition_or_no_file_is_reported_not_fatal(self):
        if not clang_available():
            self.skipTest('clang/ld.lld is unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            binary, _ = host_build(tmp, offset_path=os.path.join(tmp, 'nope',
                                                                 'ats_2'))
            result = run_helper(binary)
            fields = fields_of(result.stdout)
            self.assertEqual(fields.get('status'), 'offset-file-missing')
            # A distinct, documented exit code per failure, so the boot log says
            # which one happened.
            self.assertEqual(result.returncode, 12)
            self.assertNotIn('realtime_epoch', fields)

    def test_a_wrong_sized_file_is_refused(self):
        """The format has no header or checksum, so its length is the check."""
        if not clang_available():
            self.skipTest('clang/ld.lld is unavailable')
        for label, payload in (('short', b'\x01\x02\x03'),
                               ('empty', b''),
                               ('nine-bytes', struct.pack('<q', DEVICE_OFFSET_MS)
                                + b'\x00')):
            with self.subTest(case=label):
                with tempfile.TemporaryDirectory() as tmp:
                    binary, _ = host_build(tmp, offset_bytes=payload)
                    result = run_helper(binary)
                    self.assertEqual(fields_of(result.stdout).get('status'),
                                     'offset-file-missing', label)
                    self.assertEqual(result.returncode, 12, label)

    def test_an_implausible_offset_is_refused_rather_than_applied(self):
        """A confidently wrong clock is worse than an obviously 1970 one.

        It would break TLS and ssh in ways that look like a network fault, and
        every file written before the network appears would carry a wrong date.
        """
        if not clang_available():
            self.skipTest('clang/ld.lld is unavailable')
        for label, value in (('zero', 0),
                             ('negative', -DEVICE_OFFSET_MS),
                             ('absurd', 10 ** 17)):
            with self.subTest(case=label):
                with tempfile.TemporaryDirectory() as tmp:
                    binary, _ = host_build(
                        tmp, offset_bytes=struct.pack('<q', value))
                    result = run_helper(binary)
                    self.assertEqual(fields_of(result.stdout).get('status'),
                                     'offset-out-of-range', label)
                    self.assertEqual(result.returncode, 13, label)

    def test_a_negative_offset_is_reported_rather_than_hidden(self):
        """A corrupt file must be distinguishable from a missing one."""
        if not clang_available():
            self.skipTest('clang/ld.lld is unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            binary, _ = host_build(
                tmp, offset_bytes=struct.pack('<q', -DEVICE_OFFSET_MS))
            fields = fields_of(run_helper(binary).stdout)
            self.assertEqual(fields.get('offset_ms'), str(-DEVICE_OFFSET_MS))

    def test_an_unreadable_rtc_counter_is_reported(self):
        if not clang_available():
            self.skipTest('clang/ld.lld is unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            binary, _ = host_build(
                tmp, offset_bytes=struct.pack('<q', DEVICE_OFFSET_MS),
                epoch_path=os.path.join(tmp, 'no-such-dir', 'since_epoch'),
                create_epoch=False)
            result = run_helper(binary)
            self.assertEqual(fields_of(result.stdout).get('status'),
                             'rtc-unreadable')
            self.assertEqual(result.returncode, 14)

    def test_a_sum_outside_the_plausible_window_is_refused(self):
        """Both ends of the window, because each fails a different way.

        A one-second offset against a near-zero counter lands in 1970, and an
        absurd counter lands past 2100. Either way the sum is not a time this
        board can actually be at, so applying it would be worse than leaving the
        raw clock alone: a wrong clock that looks plausible breaks TLS and ssh in
        ways that read as a network fault.
        """
        if not clang_available():
            self.skipTest('clang/ld.lld is unavailable')
        cases = (
            # label, offset_ms, raw text, resulting epoch
            ('too-early', 1000, '0\n', 1),                    # 1970-01-01
            ('too-late', DEVICE_OFFSET_MS, '5000000000\n', None),  # past 2100
        )
        for label, offset_ms, raw, _ in cases:
            with self.subTest(case=label):
                with tempfile.TemporaryDirectory() as tmp:
                    binary, _ = host_build(
                        tmp, offset_bytes=struct.pack('<q', offset_ms),
                        epoch_text=raw)
                    result = run_helper(binary)
                    fields = fields_of(result.stdout)
                    self.assertEqual(fields.get('status'),
                                     'realtime-out-of-range', label)
                    self.assertEqual(result.returncode, 15, label)

    def test_the_window_rejects_a_1970_result_but_accepts_the_real_one(self):
        """A guard that rejected real dates would be worse than no guard."""
        if not clang_available():
            self.skipTest('clang/ld.lld is unavailable')
        # The real pair is accepted ...
        with tempfile.TemporaryDirectory() as tmp:
            binary, _ = host_build(
                tmp, offset_bytes=struct.pack('<q', DEVICE_OFFSET_MS))
            self.assertEqual(fields_of(run_helper(binary).stdout).get('status'),
                             'applied')
        # ... and the same offset against a counter near zero is not.
        with tempfile.TemporaryDirectory() as tmp:
            binary, _ = host_build(
                tmp, offset_bytes=struct.pack('<q', 1000), epoch_text='0\n')
            self.assertEqual(fields_of(run_helper(binary).stdout).get('status'),
                             'realtime-out-of-range')

    def test_the_reported_status_always_names_its_source(self):
        """Every line a reader sees in the boot log is self-describing."""
        if not clang_available():
            self.skipTest('clang/ld.lld is unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            binary, _ = host_build(tmp, offset_path=os.path.join(tmp, 'no'))
            fields = fields_of(run_helper(binary).stdout)
            self.assertEqual(fields.get('source'), 'persist/time/ats_2')


class NothingHereCanWriteThePmic(unittest.TestCase):
    """The SPMI write that blocks this kernel must stay unreachable.

    `hwclock -w` and `reboot recovery` both hang this board uninterruptibly
    (docs/RTC_REPORT.md; reference/boot-tests/test-025 and test-024). The raw
    counter is also left alone so Android and TWRP keep working unchanged.
    """

    def test_the_helper_has_no_path_to_an_rtc_device(self):
        text = SOURCE.read_text()
        for forbidden in ('/dev/rtc', 'RTC_SET_TIME', 'RTC_ALM', 'ioctl',
                          'persist-ro/time/ats_2", O_WRONLY', 'O_RDWR',
                          'O_WRONLY', 'O_CREAT', 'SYS_unlink', 'SYS_rename'):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)

    def test_the_helper_sets_only_clock_realtime(self):
        text = SOURCE.read_text()
        self.assertIn('SYS_clock_settime', text)
        self.assertIn('CLOCK_REALTIME', text)
        # Exactly one *call site*: the #define in the host/aarch64 tables and the
        # single use inside set_realtime().  More than one means a second place
        # can move the clock, which is what this test exists to prevent.
        self.assertEqual(len(re.findall(r'sys_call3\(SYS_clock_settime', text)), 1)
        self.assertLess(text.index('static void set_realtime'),
                        text.index('sys_call3(SYS_clock_settime'))
        # And the only clock id it names is CLOCK_REALTIME.
        self.assertEqual(set(re.findall(r'#define\s+(CLOCK_\w+)', text)),
                         {'CLOCK_REALTIME'})

    def test_the_only_file_it_opens_is_read_only(self):
        text = SOURCE.read_text()
        opens = re.findall(r'SYS_openat,\s*AT_FDCWD,\s*\(long\)(\w+),\s*(\w+)', text)
        self.assertTrue(opens, 'expected the helper to open its two inputs')
        for _, flags in opens:
            self.assertEqual(flags, 'O_RDONLY')
        self.assertNotIn('#define O_RDWR', text)
        self.assertNotIn('#define O_WRONLY', text)

    def test_there_is_no_kernel_side_rtc_change(self):
        """The fix must not need a driver patch or a DTS offset cell.

        Adding `nvmem-cells` to the PMK8550 RTC node would point
        rtc-pm8xxx at an NVMEM cell and ARM its write path: pm8xxx_rtc_set_time()
        then calls pm8xxx_rtc_update_offset() on every NTP sync, which writes
        through SPMI - the hang in tests 021-027. Today that path returns -ENODEV
        immediately because the node has neither property, and that is load
        bearing.
        """
        dts = (ROOT / 'kernel' / 'dts' / 'sm8550-samsung-gts9wifi.dts').read_text()
        self.assertNotIn('nvmem-cells', dts)
        self.assertNotIn('allow-set-time', dts)
        self.assertNotIn('qcom,uefi-rtc-info', dts)
        # And no patch adds one behind our back.
        for patch in (ROOT / 'kernel' / 'patches').glob('*.patch'):
            body = patch.read_text()
            self.assertNotIn('allow-set-time', body, patch.name)


class TheInitAppliesItBeforeAnythingRecordsATimestamp(unittest.TestCase):
    """Ordering is the on-device proof, so it is asserted, not commented.

    The boot record's `timestamp=` is how a reader in TWRP knows the fix worked:
    it read 2026-04-13 on a tablet whose real date was 2026-09-26. If the clock
    were set after minimal_state_init(), that evidence would keep lying.
    """

    def test_it_runs_after_sysfs_exists_and_before_the_first_timestamp(self):
        proc = INIT.index('mount -t proc proc /proc')
        sysfs = INIT.index('mount_pseudo_if_missing sysfs sysfs /sys')
        offset_call = INIT.index('\nminimal_apply_rtc_offset\n')
        state_init = INIT.index('\nminimal_state_init\n')
        self.assertLess(proc, sysfs)
        # /sys is needed for both the block-device labels and since_epoch.
        self.assertLess(sysfs, offset_call)
        # ... and the clock must be right before the record is first stamped.
        self.assertLess(offset_call, state_init)

    def test_it_is_called_exactly_once(self):
        self.assertEqual(INIT.count('\nminimal_apply_rtc_offset\n'), 1)

    def test_it_is_not_in_the_rescue_path(self):
        """The rescue shell must not grow work, and must not wait on I/O."""
        start = INIT.index('minimal_rescue_shell()')
        end = INIT.index('\n}\n', start)
        self.assertNotIn('minimal_apply_rtc_offset', INIT[start:end])

    def test_it_cannot_fail_the_boot(self):
        start = INIT.index('minimal_apply_rtc_offset()')
        body = INIT[start:INIT.index('\n}\n', start)]
        self.assertNotIn('minimal_fail', body)
        self.assertNotIn('minimal_rescue_shell', body)
        # Every branch returns success, so a broken offset cannot stop Debian.
        for line in body.splitlines():
            if line.strip().startswith('return'):
                self.assertEqual(line.strip(), 'return 0', line)


class ThePersistMountIsReadOnlyInFactNotJustInIntent(unittest.TestCase):
    """`ro` alone still writes: ext4 replays the journal for recovery.

    From fs/ext4/super.c: with a journal that `needs_recovery`, `-o ro` prints
    "write access will be enabled during recovery" and does it. That would write
    to the owner's persist partition to read one file. `noload` skips
    ext4_load_and_init_journal() entirely, so nothing is written at all.
    """

    def test_the_mount_uses_ro_and_noload(self):
        start = INIT.index('minimal_apply_rtc_offset()')
        body = INIT[start:INIT.index('\n}\n', start)]
        mount = re.search(r'timeout \d+ mount -t ext4 -o (\S+) "\$persist_dev"', body)
        self.assertIsNotNone(mount, 'expected a bounded ext4 mount')
        options = set(mount.group(1).split(','))
        self.assertIn('ro', options)
        self.assertIn('noload', options,
                      'without noload ext4 replays the journal, which writes')

    def test_the_mount_is_bounded(self):
        start = INIT.index('minimal_apply_rtc_offset()')
        body = INIT[start:INIT.index('\n}\n', start)]
        self.assertIn('timeout 10 mount', body)
        self.assertIn('timeout 10 "$RTC_OFFSET_HELPER"', body)

    def test_it_is_unmounted_before_switch_root(self):
        """A superblock held across switch_root outlives the initramfs."""
        start = INIT.index('minimal_apply_rtc_offset()')
        body = INIT[start:INIT.index('\n}\n', start)]
        self.assertIn('umount "$PERSIST_MOUNT"', body)
        self.assertLess(body.index('umount "$PERSIST_MOUNT"'),
                        body.index('minimal_emit "${rtc_offset_line'))

    def test_the_partition_is_found_by_the_kernels_own_label(self):
        start = INIT.index('minimal_apply_rtc_offset()')
        body = INIT[start:INIT.index('\n}\n', start)]
        self.assertIn('minimal_label_device persist 1', body)
        # Never a device number: that is how a read lands in somebody else's
        # partition on a different layout.
        self.assertNotIn('sda5', body)
        self.assertNotIn('/dev/block/by-name', body)

    def test_the_label_helper_still_refuses_the_microsd(self):
        """The shared helper must keep the property the BCB path depends on."""
        start = INIT.index('minimal_label_device()')
        fn = INIT[start:INIT.index('\n}\n', start)]
        self.assertIn('PARTNAME=', fn)
        self.assertIn('uevent', fn)
        self.assertIn('basename', fn)
        self.assertIn('mmcblk*) continue', fn)
        self.assertNotIn('sda10', fn)

    def test_the_waits_are_finite(self):
        start = INIT.index('minimal_apply_rtc_offset()')
        body = INIT[start:INIT.index('\n}\n', start)]
        self.assertIn('"$rtc_offset_waited" -lt 5', body)


class ItCanBeTurnedOffForOneBoot(unittest.TestCase):
    """A diagnostic that needs a rebuild is not a diagnostic."""

    def test_the_cmdline_parser_accepts_the_option(self):
        self.assertIn("gts9_rtc_offset=*) GTS9_RTC_OFFSET=${arg#gts9_rtc_offset=}",
                      INIT)
        self.assertIn('GTS9_RTC_OFFSET=${GTS9_RTC_OFFSET:-1}', INIT)

    def test_it_defaults_on_because_a_wrong_clock_is_a_fault(self):
        start = INIT.index('minimal_apply_rtc_offset()')
        body = INIT[start:INIT.index('\n}\n', start)]
        self.assertIn('"${GTS9_RTC_OFFSET:-1}" != 1', body)
        self.assertIn('disabled-by-cmdline', body)


class TheProductionImageShipsItAndTheDebugImageDoesNotNeedTo(unittest.TestCase):
    def test_the_builder_compiles_it_as_aarch64_and_static(self):
        self.assertIn('gts9-rtc-offset.c', PROD_BUILDER)
        self.assertIn('--target=aarch64-linux-gnu', PROD_BUILDER)
        # Checked at build time: a helper that cannot run would be discovered on
        # a tablet that will not boot, which is the expensive place to find out.
        self.assertIn("readelf -h \"$rtc_helper\" | grep -q 'Machine:.*AArch64'",
                      PROD_BUILDER)
        self.assertIn("readelf -l \"$rtc_helper\" 2>/dev/null | grep -q INTERP",
                      PROD_BUILDER)

    def test_it_is_installed_to_sbin_where_the_init_looks_for_it(self):
        self.assertIn('rtc_helper="$tree/sbin/gts9-rtc-offset"', PROD_BUILDER)
        self.assertIn('RTC_OFFSET_HELPER=/sbin/gts9-rtc-offset', INIT)

    def test_no_new_busybox_applet_was_needed(self):
        """The offset is parsed in C precisely so the applet list stays small.

        `od` is forbidden in production (it is the debug image's raw-GPT tool),
        and eight decimal bytes of little-endian 64-bit is not something to do by
        hand in POSIX shell.
        """
        used = commands_in(ROOT / 'boot' / 'minimal-rootfs-init.sh')
        used = used | commands_in(ROOT / 'boot' / 'minimal-rootfs-state.sh')
        declared = set(re.search(r"required_applets='([^']*)'", PROD_BUILDER)
                       .group(1).split())
        declared |= set(re.search(r"sbin_applets='([^']*)'", PROD_BUILDER)
                        .group(1).split())
        builtins = initramfs_module().ProductionAppletsMatchWhatItRuns.BUILTINS
        # Anything not a builtin and not declared is a real gap; this mirrors the
        # existing test so the two cannot disagree.
        unexpected = {name for name in used
                      if name not in builtins and name not in declared
                      and name != 'sh' and not name.isupper()}
        # Only the long-standing prose false positives are tolerated here; the
        # authoritative check is ProductionAppletsMatchWhatItRuns.
        self.assertFalse(
            unexpected - {'boot', 'case', 'continue', 'do', 'done', 'elif',
                          'else', 'esac', 'fi', 'for', 'found', 'if', 'in',
                          'inspect', 'it', 'kernel', 'losing', 'never',
                          'nothing', 'opportunistically', 'sourcing', 'the',
                          'then', 'type', 'waited', 'waiting', 'while', 'with',
                          'without', 'error', 'record', 'state', 'root',
                          'device', 'mount', 'minimal', 'pseudo_type',
                          'pseudo_source', 'pseudo_target', 'vfs', 'arg',
                          'line', 'dir', 'file', 'mode', 'msg', 'step'},
            'production /init runs a command that is not in the applet list')


class TheHelperIsDocumentedWhereItsEvidenceLives(unittest.TestCase):
    def test_the_report_document_exists_and_states_the_mechanism(self):
        doc = ROOT / 'docs' / 'RTC_OFFSET.md'
        self.assertTrue(doc.is_file(), 'docs/RTC_OFFSET.md must exist')
        text = doc.read_text()
        for needed in ('ats_2', 'persist', '1767701103844',
                       '/persist/time/ats_2'):
            with self.subTest(needed=needed):
                self.assertIn(needed, text)

    def test_the_source_names_the_file_and_the_document(self):
        text = SOURCE.read_text()
        self.assertIn('/persist/time/ats_2', text)
        self.assertIn('docs/RTC_OFFSET.md', text)


if __name__ == '__main__':
    unittest.main()
