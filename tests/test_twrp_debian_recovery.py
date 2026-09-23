"""Host checks for the safe TWRP-side Debian mount helper."""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'scripts' / 'twrp-mount-debian.sh'
SCRIPT_TEXT = SCRIPT.read_text()
SCRIPT_CODE = '\n'.join(line for line in SCRIPT_TEXT.splitlines()
                        if not line.lstrip().startswith('#'))

RECORD = """\
format_version=1
origin=initramfs
boot_id=11111111-2222-3333-4444-555555555555
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


def ext4_magic_file(path, magic=b'\x53\xef'):
    data = bytearray(4096)
    data[1080:1082] = magic
    path.write_bytes(bytes(data))


class TwrpMountDebian(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.dev_dir = self.root / 'dev'
        self.dev_dir.mkdir()
        self.mountpoint = self.root / 'mnt' / 'debian'
        self.stub_bin = self.root / 'bin'
        self.stub_bin.mkdir()
        self.log = self.root / 'stub.log'
        self.fixtures = self.root / 'fixtures'
        self.fake_ok = self.root / 'blkid-works'
        self.fake_ok.write_text('1\n')

        # mmcblk0p1: not ext4 (blkid reports vfat).
        (self.dev_dir / 'mmcblk0p1').write_bytes(bytearray(2048))
        # mmcblk1p1: the Debian root, labelled and larger.
        ext4_magic_file(self.dev_dir / 'mmcblk1p1')
        (self.dev_dir / 'mmcblk1p1').write_bytes(
            (self.dev_dir / 'mmcblk1p1').read_bytes() + bytearray(64 * 1024))
        # mmcblk1p2: ext4 with no blkid answer - only the magic identifies it.
        ext4_magic_file(self.dev_dir / 'mmcblk1p2')

        self.write_stubs()

    def write_stubs(self):
        blkid = self.stub_bin / 'blkid'
        blkid.write_text(
            '#!/bin/sh\n'
            'dev=$1\n'
            'case "$dev" in\n'
            '*mmcblk0p1) echo \'/dev/block/mmcblk0p1: LABEL="EFI" UUID="AAAA-BBBB" '
            'TYPE="vfat"\' ;;\n'
            '*mmcblk1p1) echo \'/dev/block/mmcblk1p1: LABEL="DEBIAN" '
            'UUID="1234-5678" TYPE="ext4"\' ;;\n'
            '*) exit 2 ;;\n'
            'esac\n')
        blkid.chmod(0o755)

        mount = self.stub_bin / 'mount'
        mount.write_text(
            '#!/bin/sh\n'
            'echo "mount $*" >> "$STUB_LOG"\n'
            '# -t ext4 -o MODE DEVICE MOUNTPOINT\n'
            'mode=$4\n'
            'dev=$5\n'
            'mnt=$6\n'
            'name=$(basename "$dev")\n'
            'fixture="$STUB_FIXTURES/$name"\n'
            '[ -d "$fixture" ] || exit 32\n'
            'mkdir -p "$mnt"\n'
            'cp -a "$fixture"/. "$mnt"/\n'
            'echo "$mode" > "$STUB_LOG.mode"\n'
            'exit 0\n')
        mount.chmod(0o755)

        umount = self.stub_bin / 'umount'
        umount.write_text(
            '#!/bin/sh\n'
            'echo "umount $*" >> "$STUB_LOG"\n'
            'rm -rf "$1"/*\n'
            'exit 0\n')
        umount.chmod(0o755)

    def add_fixture(self, device, debian=True):
        fixture = self.fixtures / device
        (fixture / 'etc').mkdir(parents=True)
        if debian:
            (fixture / 'etc' / 'debian_version').write_text('13.0\n')
        else:
            (fixture / 'etc' / 'hostname').write_text('not-debian\n')
        (fixture / 'var' / 'log').mkdir(parents=True)
        (fixture / 'var' / 'log' / 'gts9-minimal-last-boot').write_text(RECORD)
        return fixture

    def run_script(self, *args, env=None):
        environment = dict(os.environ,
                           PATH=f'{self.stub_bin}:{os.environ["PATH"]}',
                           GTS9_TWRP_MOUNTPOINT=str(self.mountpoint),
                           GTS9_TWRP_DEV_DIRS=str(self.dev_dir),
                           GTS9_TWRP_ALLOW_REGULAR='1',
                           STUB_LOG=str(self.log),
                           STUB_FIXTURES=str(self.fixtures))
        if env:
            environment.update(env)
        return subprocess.run(['/bin/sh', str(SCRIPT), *args],
                              env=environment, text=True,
                              capture_output=True, check=False)

    def test_listing_reports_mmc_candidates_only(self):
        result = self.run_script('--list')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('mmcblk1p1', result.stdout)
        self.assertIn('DEBIAN', result.stdout)
        self.assertIn('1234-5678', result.stdout)
        self.assertIn('mmcblk1p2', result.stdout)
        # Every MMC partition is listed with its real filesystem type, so a
        # wrong assumption about block numbering is visible before mounting.
        self.assertIn('mmcblk0p1', result.stdout)
        self.assertIn('vfat', result.stdout)
        listed = [line.split()[0] for line in result.stdout.splitlines()
                  if line.startswith('/')]
        self.assertTrue(listed)
        self.assertTrue(all('mmcblk' in dev for dev in listed), listed)
        self.assertIn('UFS devices (/dev/sd*) are never listed or mounted',
                      result.stdout)

    def test_default_run_mounts_read_only_and_prints_the_record(self):
        self.add_fixture('mmcblk1p1')
        self.add_fixture('mmcblk1p2')
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('read-only', result.stdout)
        self.assertIn(f'device={self.dev_dir / "mmcblk1p1"}', result.stdout)
        self.assertIn('stage=switch-root', result.stdout)
        self.assertIn('stage_history=kernel-userspace', result.stdout)
        self.assertEqual((self.root / 'stub.log.mode').read_text().strip(),
                         'ro,noload')
        self.assertIn('nothing was formatted and no fsck ran', result.stdout)

    def test_magic_fallback_identifies_ext4_without_blkid(self):
        # mmcblk1p1 has no blkid answer here, so only the superblock magic can
        # identify it.
        blkid = self.stub_bin / 'blkid'
        blkid.write_text('#!/bin/sh\nexit 2\n')
        self.add_fixture('mmcblk1p1')
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f'device={self.dev_dir / "mmcblk1p1"}', result.stdout)

    def test_rw_is_explicit(self):
        self.add_fixture('mmcblk1p1')
        result = self.run_script('--rw')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('read-write', result.stdout)
        self.assertEqual((self.root / 'stub.log.mode').read_text().strip(), 'rw')

    def test_label_and_uuid_selection(self):
        self.add_fixture('mmcblk1p1')
        by_uuid = self.run_script('--uuid', '1234-5678')
        self.assertEqual(by_uuid.returncode, 0, by_uuid.stderr)
        self.assertIn(f'device={self.dev_dir / "mmcblk1p1"}', by_uuid.stdout)
        missing = self.run_script('--uuid', '0000-0000')
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn('no ext4 MMC partition found', missing.stderr)

    def test_non_debian_candidates_are_rejected_and_unmounted(self):
        self.add_fixture('mmcblk1p1', debian=False)
        self.add_fixture('mmcblk1p2', debian=False)
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('does not contain a Debian userspace', result.stdout)
        self.assertIn('no candidate contained a Debian userspace', result.stderr)
        self.assertIn('umount', self.log.read_text())

    def test_second_candidate_is_used_when_the_first_is_not_debian(self):
        # mmcblk1p2 sorts after the labelled mmcblk1p1: make the label a lie.
        self.add_fixture('mmcblk1p1', debian=False)
        self.add_fixture('mmcblk1p2', debian=True)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f'device={self.dev_dir / "mmcblk1p2"}', result.stdout)

    def test_ufs_devices_are_refused(self):
        result = self.run_script('--device', '/dev/sda1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('refusing UFS device', result.stderr)

    def test_whole_disks_and_non_ext4_are_refused(self):
        whole = self.run_script('--device', '/dev/mmcblk1')
        self.assertNotEqual(whole.returncode, 0)
        self.assertIn('not an MMC partition', whole.stderr)
        non_ext4 = self.run_script('--device', str(self.dev_dir / 'mmcblk0p1'))
        self.assertNotEqual(non_ext4.returncode, 0)
        self.assertIn('not ext4', non_ext4.stderr)

    def test_force_skips_only_the_debian_marker(self):
        self.add_fixture('mmcblk1p1', debian=False)
        result = self.run_script('--device', str(self.dev_dir / 'mmcblk1p1'),
                                 '--force')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f'device={self.dev_dir / "mmcblk1p1"}', result.stdout)

    def test_umount_reports_when_nothing_is_mounted(self):
        result = self.run_script('--umount')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('is not mounted', result.stdout)

    def test_script_never_formats_or_repairs(self):
        # Ignore the messages: only executed commands matter.  Reading a
        # superblock with dd is fine; writing one is not.
        commands = '\n'.join(
            line for line in SCRIPT_CODE.splitlines()
            if not re.match(r'\s*(note|die|echo|printf)\b', line))
        for forbidden in ('mkfs', 'mke2fs', 'fsck', 'e2fsck', 'wipefs',
                          'sgdisk', 'parted', 'dd of=', '> /dev/', 'mount -a'):
            self.assertNotIn(forbidden, commands, forbidden)

    def test_script_is_posix_and_busybox_friendly(self):
        for bashism in ('[[', 'declare ', 'local ', 'function ', '${!'):
            self.assertNotIn(bashism, SCRIPT_CODE, bashism)
        # TWRP's shell is busybox ash; the shebang must not demand bash.
        self.assertTrue(SCRIPT_TEXT.startswith('#!/bin/sh'))
        check = subprocess.run(['dash', '-n', str(SCRIPT)] if shutil.which('dash')
                               else ['/bin/sh', '-n', str(SCRIPT)],
                               text=True, capture_output=True, check=False)
        self.assertEqual(check.returncode, 0, check.stderr)

    def test_record_name_is_the_documented_one(self):
        self.assertIn('gts9-minimal-last-boot', SCRIPT_TEXT)
        self.assertIn('var/log', SCRIPT_TEXT)
        self.assertIn('/etc/debian_version', SCRIPT_TEXT)
        self.assertIn(re.escape('ID=debian'), SCRIPT_TEXT)


if __name__ == '__main__':
    unittest.main()
