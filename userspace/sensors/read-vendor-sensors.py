#!/usr/bin/env python3
"""Read-only export of stock X710 vendor/etc/sensors; no DSP activation.

Only the non-A/B, single-super, single-linear-extent vendor layout is supported.
Metadata offsets/checksums follow AOSP system/core/fs_mgr/liblp/{reader.cpp,
include/liblp/metadata_format.h}. Unsupported layouts are refused, not guessed.
"""
import argparse
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import sys
import tarfile
import tempfile


def sha(data):
    return hashlib.sha256(data).digest()


def vendor_extent(prefix, device_size):
    geometries = []
    for offset in (4096,8192):
        g = prefix[offset:offset+52]
        if len(g) != 52 or struct.unpack_from('<II',g) != (0x616c4467,52):
            raise ValueError('invalid LP geometry')
        if sha(g[:8]+bytes(32)+g[40:]) != g[8:40]:
            raise ValueError('LP geometry checksum mismatch')
        geometries.append(g)
    if geometries[0] != geometries[1]:
        raise ValueError('LP geometry copies disagree')
    maximum, slots, block = struct.unpack_from('<III',geometries[0],40)
    if not 512 <= maximum <= 131072 or maximum % 512 or not 1 <= slots <= 3 or block != 4096:
        raise ValueError('unsupported LP geometry')
    copies = []
    for offset in (12288,12288+maximum*slots):
        raw = prefix[offset:offset+maximum]
        if len(raw) != maximum:
            raise ValueError('short LP metadata')
        magic,major,minor,size = struct.unpack_from('<IHHI',raw)
        if magic != 0x414c5030 or major != 10 or minor not in (0,1,2) or size != (256 if minor == 2 else 128):
            raise ValueError('unsupported LP header version')
        if sha(raw[:12]+bytes(32)+raw[44:size]) != raw[12:44]:
            raise ValueError('LP header checksum mismatch')
        if size == 256 and any(raw[128:256]):
            raise ValueError('unsupported LP flags/reserved fields')
        length = struct.unpack_from('<I',raw,44)[0]
        if size+length > maximum or sha(raw[size:size+length]) != raw[48:80]:
            raise ValueError('LP tables size/checksum mismatch')
        tables = raw[size:size+length]
        decoded = []
        for pos,entry_size in [(80,52),(92,24),(104,48),(116,64)]:
            off,count,step = struct.unpack_from('<III',raw,pos)
            if step != entry_size or not 1 <= count <= 4096 or off+count*step > length:
                raise ValueError('invalid LP table descriptor')
            decoded.append([tables[off+i*step:off+(i+1)*step] for i in range(count)])
        copies.append((raw[:size+length],decoded))
    if copies[0][0] != copies[1][0]:
        raise ValueError('LP slot 0 primary/backup disagree')
    partitions,extents,groups,devices = copies[0][1]
    if len(devices) != 1:
        raise ValueError('only single-super metadata supported')
    first,alignment,align_offset,total,name,flags = struct.unpack('<QIIQ36sI',devices[0])
    if name.rstrip(b'\0') != b'super' or flags or total != device_size:
        raise ValueError('LP super identity/size mismatch')
    matches = [p for p in partitions if p[:36].rstrip(b'\0') == b'vendor']
    if len(matches) != 1:
        raise ValueError('exact unsuffixed vendor partition not found')
    attr,index,count,group = struct.unpack_from('<IIII',matches[0],36)
    if attr != 1 or count != 1 or index >= len(extents) or group >= len(groups):
        raise ValueError('vendor is not one readonly linear extent')
    if struct.unpack_from('<I',groups[group],36)[0]:
        raise ValueError('unsupported slot-suffixed vendor group')
    sectors,kind,target,source = struct.unpack('<QIQI',extents[index])
    minimum = 12288+2*maximum*slots
    if (kind or source or not sectors or target*512 < max(first*512,minimum)
            or (target+sectors)*512 > total or target*512 % block or sectors*512 % block):
        raise ValueError('invalid/out-of-range vendor extent')
    return dict(offset=target*512,bytes=sectors*512,super_bytes=total,
                slot=0,metadata_sha256=sha(copies[0][0]).hex(),
                geometry_sha256=sha(geometries[0]).hex(),primary_backup_agree=True)


def read(path):
    return Path(path).read_text().strip()


def mounted(path):
    return [r.split() for r in read('/proc/mounts').splitlines() if r.split()[1] == str(path)]


def run(argv):
    return subprocess.check_output(argv,text=True,stderr=subprocess.PIPE,timeout=10).strip()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--boot-id',required=True)
    args = p.parse_args()
    boot = '/proc/sys/kernel/random/boot_id'
    state = '/sys/class/remoteproc/remoteproc0/state'
    if (read(boot) != args.boot_id or read(state) != 'offline'
            or b'samsung,gts9wifi' not in Path('/sys/firmware/devicetree/base/compatible').read_bytes().split(b'\0')):
        raise ValueError('unexpected boot/board/ADSP state')
    device = Path('/dev/disk/by-partlabel/super').resolve(strict=True)
    if not stat.S_ISBLK(device.stat().st_mode):
        raise ValueError('super is not a block device')
    with device.open('rb',buffering=0) as f:
        size = struct.unpack('<Q',fcntl.ioctl(f,0x80081272,bytes(8)))[0]  # BLKGETSIZE64, read-only
        extent = vendor_extent(os.pread(f.fileno(),1024*1024,0),size)
    work = Path(tempfile.mkdtemp(prefix='gts9-vendor-sensors-',dir='/run'))
    loop = None
    contents = {}
    report = dict(boot_id=args.boot_id,purpose='READ_ONLY_VENDOR_SENSOR_CONFIG',
                  source_device=str(device),extent=extent,files={},device_deployment=False)
    try:
        loop = Path(run(['losetup','--read-only','--find','--show','--offset',str(extent['offset']),
                         '--sizelimit',str(extent['bytes']),str(device)]))
        if not loop.name.startswith('loop') or read('/sys/block/'+loop.name+'/ro') != '1':
            raise ValueError('loop is not read-only')
        kind = run(['blkid','-p','-s','TYPE','-o','value',str(loop)])
        if kind not in ('ext4','erofs'):
            raise ValueError('unsupported vendor filesystem')
        options = 'ro,nosuid,nodev,noexec'+(',noload' if kind == 'ext4' else '')
        run(['mount','-t',kind,'-o',options,str(loop),str(work)])
        rows = mounted(work)
        if len(rows) != 1 or rows[0][2] != kind or not {'ro','nosuid','nodev','noexec'}.issubset(rows[0][3].split(',')):
            raise ValueError('read-only vendor mount verification failed')
        report['verified_mount'] = rows[0]
        root = work/'etc/sensors'
        if not root.is_dir() or root.is_symlink():
            raise ValueError('vendor sensors subtree absent')
        for path in sorted(root.rglob('*')):
            info = path.lstat()
            if stat.S_ISDIR(info.st_mode):
                continue
            if not stat.S_ISREG(info.st_mode) or info.st_size > 1024*1024:
                raise ValueError('unexpected vendor sensor member')
            if len(contents) >= 512 or sum(len(b) for b in contents.values())+info.st_size > 8*1024*1024:
                raise ValueError('sensor export bounds exceeded')
            name = 'vendor/'+str(path.relative_to(work))
            data = path.read_bytes()
            if len(data) != info.st_size:
                raise ValueError('vendor file changed')
            contents[name] = data
            report['files'][name] = dict(bytes=len(data),sha256=sha(data).hex(),
                                        source_mtime_ns=info.st_mtime_ns,archive_mtime=int(info.st_mtime))
        if not any(n.startswith('vendor/etc/sensors/config/') for n in contents):
            raise ValueError('no vendor sensor config inputs')
    finally:
        # Never detach a device while our mount still exists, or force cleanup.
        if mounted(work):
            run(['umount',str(work)])
        if loop is not None:
            run(['losetup','--detach',str(loop)])
        work.rmdir()
    if read(boot) != args.boot_id or read(state) != 'offline':
        raise ValueError('boot/ADSP changed during collection')
    report['temporary_mount_and_loop_removed'] = True
    contents['MANIFEST.json'] = (json.dumps(report,indent=2)+'\n').encode()
    with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as archive:
        for name,data in contents.items():
            info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o600
            info.mtime=report['files'][name]['archive_mtime'] if name != 'MANIFEST.json' else 0
            archive.addfile(info,io.BytesIO(data))
    print(json.dumps(dict(verdict='VENDOR_SENSOR_CONFIG_EXPORTED_NOT_INSTALLED',
                         files=len(report['files']),temporary_mount_and_loop_removed=True)),file=sys.stderr)


if __name__ == '__main__':
    main()
