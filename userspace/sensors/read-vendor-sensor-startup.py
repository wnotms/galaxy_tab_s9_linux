#!/usr/bin/env python3
"""Export X710 stock sensor startup inputs from a temporary read-only vendor mount.

Never load/execute these Android binaries, activate DSP, or write vendor/persist.
Reuse the separately tested single-super layout parser; unsupported layouts stop.
"""
import argparse
from contextlib import contextmanager
import fcntl
import fnmatch
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import struct
import sys
import tarfile
import tempfile

PATTERNS = {
    'bin': ('sscrpcd', 'adsprpcd', '*sensor*'),
    'bin/hw': ('*sensor*',),
    'etc/init': ('*sensor*.rc', '*ssc*.rc', '*sns*.rc', '*adsprpc*.rc'),
    'lib': ('*sns*.so', '*ssc*.so', '*sensor*.so', 'libadsprpc.so', 'libadsp_default_listener.so'),
    'lib64': ('*sns*.so', '*ssc*.so', '*sensor*.so', 'libadsprpc.so', 'libadsp_default_listener.so'),
    'lib/hw': ('sensors.*.so',),
    'lib64/hw': ('sensors.*.so',),
}
MAX_FILES = 128
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024


def selected(directory, name):
    if directory not in PATTERNS or '/' in name or name in ('', '.', '..'):
        return False
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in PATTERNS[directory])


def inspect_tree(root):
    contents, files, inventory = {}, {}, {}
    total = 0
    for directory in PATTERNS:
        folder = root / directory
        # Reject symlinks in every selected parent, including lib -> another tree.
        for parent in (folder, *folder.parents):
            if parent == root:
                break
            if parent.is_symlink():
                raise ValueError('linked vendor startup directory')
        if not folder.exists():
            inventory[directory] = None
            continue
        if not folder.is_dir():
            raise ValueError('vendor startup directory is not a directory')
        paths = sorted(folder.iterdir())
        if len(paths) > 4096:
            raise ValueError('vendor directory entry bound')
        inventory[directory] = [path.name for path in paths]
        for path in paths:
            if not selected(directory, path.name):
                continue
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode):
                raise ValueError('selected startup member is not a regular file')
            if (info.st_size > MAX_FILE_BYTES or len(files) >= MAX_FILES or
                    total + info.st_size > MAX_TOTAL_BYTES):
                raise ValueError('vendor startup export bound')
            data = path.read_bytes()
            after = path.lstat()
            if (len(data) != info.st_size or
                    (after.st_ino, after.st_size, after.st_mtime_ns) !=
                    (info.st_ino, info.st_size, info.st_mtime_ns)):
                raise ValueError('vendor startup file changed during read')
            name = 'vendor/' + str(path.relative_to(root))
            contents[name] = data
            files[name] = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                               source_mtime_ns=info.st_mtime_ns,
                               archive_mtime=int(info.st_mtime),
                               elf_machine=struct.unpack_from('<H', data, 18)[0]
                               if len(data) >= 20 and data[:4] == b'\x7fELF' and data[5] == 1 else None)
            total += len(data)
    if not files:
        raise ValueError('no stock sensor startup inputs found')
    return contents, files, inventory


@contextmanager
def readonly_vendor(layout, device, extent):
    work = Path(tempfile.mkdtemp(prefix='gts9-sensor-startup-', dir='/run'))
    loop = None
    try:
        loop = Path(layout.run(['losetup', '--read-only', '--find', '--show',
            '--offset', str(extent['offset']), '--sizelimit', str(extent['bytes']), str(device)]))
        if not loop.name.startswith('loop') or layout.read('/sys/block/' + loop.name + '/ro') != '1':
            raise ValueError('startup loop not read-only')
        kind = layout.run(['blkid', '-p', '-s', 'TYPE', '-o', 'value', str(loop)])
        if kind not in ('ext4', 'erofs'):
            raise ValueError('unsupported vendor filesystem')
        options = 'ro,nosuid,nodev,noexec' + (',noload' if kind == 'ext4' else '')
        layout.run(['mount', '-t', kind, '-o', options, str(loop), str(work)])
        rows = layout.mounted(work)
        if (len(rows) != 1 or rows[0][0] != str(loop) or rows[0][2] != kind or
                not {'ro', 'nosuid', 'nodev', 'noexec'}.issubset(rows[0][3].split(','))):
            raise ValueError('startup vendor mount verification failed')
        yield work, rows[0]
    finally:
        # An unmount failure intentionally prevents detach/removal and success.
        # Do not force-unmount or touch any other process's loop/mount.
        if layout.mounted(work):
            layout.run(['umount', str(work)])
        if loop is not None:
            layout.run(['losetup', '--detach', str(loop)])
        work.rmdir()


def main(layout):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--boot-id', required=True)
    args = parser.parse_args()
    def gate():
        if (os.geteuid() != 0 or layout.read('/proc/sys/kernel/random/boot_id') != args.boot_id or
                layout.read('/sys/class/remoteproc/remoteproc0/state') != 'offline' or
                b'samsung,gts9wifi' not in Path('/sys/firmware/devicetree/base/compatible').read_bytes().split(b'\0')):
            raise ValueError('root/same-boot/X710/offline-ADSP gate')
    gate()
    device = Path('/dev/disk/by-partlabel/super').resolve(strict=True)
    if not stat.S_ISBLK(device.stat().st_mode):
        raise ValueError('super is not a block device')
    with device.open('rb', buffering=0) as stream:
        size = struct.unpack('<Q', fcntl.ioctl(stream, 0x80081272, bytes(8)))[0]
        extent = layout.vendor_extent(os.pread(stream.fileno(), 1024 * 1024, 0), size)
    with readonly_vendor(layout, device, extent) as (work, mount):
        contents, files, inventory = inspect_tree(work)
        report = dict(boot_id=args.boot_id, purpose='READ_ONLY_X710_SENSOR_STARTUP_INPUTS',
            source_device=str(device), extent=extent, verified_mount=mount,
            files=files, directory_inventory=inventory, binaries_executed=False,
            DSP_started=False, partitions_written=False, registry_written=False)
    gate()
    report['temporary_mount_and_loop_removed'] = True
    contents['MANIFEST.json'] = (json.dumps(report, indent=2) + '\n').encode()
    # No successful archive is emitted until cleanup and final gate have passed.
    with tarfile.open(fileobj=sys.stdout.buffer, mode='w|gz') as archive:
        for name, data in contents.items():
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), 0o600
            info.mtime = files[name]['archive_mtime'] if name != 'MANIFEST.json' else 0
            archive.addfile(info, io.BytesIO(data))


if __name__ == '__main__':
    spec = importlib.util.spec_from_file_location('vendor_layout', Path(__file__).with_name('read-vendor-sensors.py'))
    layout = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(layout)
    main(layout)
