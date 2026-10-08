#!/usr/bin/env python3
"""Device-side read-only stock asset export. No installation or DSP startup."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import stat
import subprocess
import sys
import tarfile
import tempfile


def read(path):
    return Path(path).read_text().strip()


def mounts():
    return [line.split() for line in read('/proc/mounts').splitlines()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--boot-id', required=True)
    args = parser.parse_args()
    boot_path = '/proc/sys/kernel/random/boot_id'
    if read(boot_path) != args.boot_id:
        raise ValueError('boot changed; collect a fresh read-only layout first')
    compatible = Path('/sys/firmware/devicetree/base/compatible').read_bytes().split(b'\0')
    if b'samsung,gts9wifi' not in compatible or read('/sys/class/remoteproc/remoteproc0/state') != 'offline':
        raise ValueError('unexpected board or ADSP state')
    report = dict(boot_id=args.boot_id, purpose='READ_ONLY_STOCK_SENSOR_ASSETS',
                  firmware_installed=False, remoteproc_started=False,
                  partitions={}, files={}, skipped_links=[])
    work = Path(tempfile.mkdtemp(prefix='gts9-ssc-stock-', dir='/run'))
    destinations = []
    total = 0
    try:
        with tarfile.open(fileobj=sys.stdout.buffer, mode='w|gz') as archive:
            try:
                for label, filesystem in [('apnhlos','vfat'),('dsp','ext4'),('persist','ext4')]:
                    device = Path('/dev/disk/by-partlabel') / label
                    if not stat.S_ISBLK(device.stat().st_mode):
                        raise ValueError('source is not a block device')
                    kind = subprocess.check_output(['blkid','-p','-s','TYPE','-o','value',str(device)],
                                                   text=True,timeout=5).strip()
                    if kind != filesystem:
                        raise ValueError('unexpected stock filesystem')
                    if any(str(device.resolve()) == str(Path(row[0]).resolve()) for row in mounts()):
                        raise ValueError('stock source is already mounted; do not change it')
                    destination = work / label
                    destination.mkdir()
                    destinations.append(destination)
                    options = 'ro,nosuid,nodev,noexec' + (',noload' if filesystem == 'ext4' else '')
                    command = ['mount','-t',filesystem,'-o',options,str(device),str(destination)]
                    subprocess.run(command,check=True,capture_output=True,timeout=10)
                    rows = [row for row in mounts() if row[1] == str(destination)]
                    if len(rows) != 1 or rows[0][2] != filesystem or not {
                            'ro','nosuid','nodev','noexec'}.issubset(set(rows[0][3].split(','))):
                        raise ValueError('read-only mount verification failed')
                    report['partitions'][label] = dict(device=str(device.resolve()),
                        mount_command=command, verified_mount=rows[0])
                    root = destination / 'sensors' if label == 'persist' else destination
                    if not root.is_dir() or root.is_symlink():
                        raise ValueError('required stock subtree absent')
                    candidates = sorted(root.rglob('*'))
                    if label == 'apnhlos':
                        candidates = [p for p in candidates if p.name.lower().startswith('adsp')]
                        if not any(p.name.lower() == 'adsp.mdt' for p in candidates):
                            raise ValueError('stock ADSP MDT absent')
                    for path in candidates:
                        relative = path.relative_to(destination)
                        name = label + '/' + str(relative)
                        if path.is_symlink():
                            report['skipped_links'].append(dict(path=name,target=str(path.readlink())))
                            continue
                        if path.is_dir():
                            continue
                        info = path.stat()
                        if not stat.S_ISREG(info.st_mode):
                            raise ValueError('unexpected stock special file')
                        total += info.st_size
                        if total > 192*1024*1024 or info.st_size > 64*1024*1024 or len(report['files']) >= 8192:
                            raise ValueError('asset export bounds exceeded')
                        data = path.read_bytes()
                        if len(data) != info.st_size:
                            raise ValueError('stock file changed during read')
                        member = tarfile.TarInfo(name)
                        member.size, member.mode, member.mtime = len(data), info.st_mode & 0o777, int(info.st_mtime)
                        archive.addfile(member,io.BytesIO(data))
                        report['files'][name] = dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),
                                                     source_mtime_ns=info.st_mtime_ns,archive_mtime=member.mtime)
            finally:
                errors = []
                for destination in reversed(destinations):
                    if any(row[1] == str(destination) for row in mounts()):
                        process = subprocess.run(['umount',str(destination)],capture_output=True,text=True,timeout=10)
                        if process.returncode:
                            errors.append(process.stderr)
                    try:destination.rmdir()
                    except OSError as error:errors.append(str(error))
                report['temporary_mounts_removed'] = not errors
                report['cleanup_errors'] = errors
                if errors:
                    raise RuntimeError('read-only mount cleanup failed: ' + repr(errors))
            if read(boot_path) != args.boot_id or read('/sys/class/remoteproc/remoteproc0/state') != 'offline':
                raise ValueError('boot or ADSP state changed during read-only export')
            report['total_bytes'] = total
            data = (json.dumps(report,indent=2)+'\n').encode()
            member = tarfile.TarInfo('MANIFEST.json')
            member.size = len(data)
            archive.addfile(member,io.BytesIO(data))
    finally:
        # Never recursively remove a path that might still be mounted.
        work.rmdir()
    print(json.dumps(dict(verdict='READ_ONLY_ASSETS_EXPORTED_NOT_INSTALLED',
        boot_id=args.boot_id,files=len(report['files']),bytes=total,
        temporary_mounts_removed=report['temporary_mounts_removed'])),file=sys.stderr)


if __name__ == '__main__':
    main()
