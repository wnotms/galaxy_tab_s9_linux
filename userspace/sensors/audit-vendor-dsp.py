#!/usr/bin/env python3
"""Read-only X710 RFSA inventory; no export, driver, firmware or service changes."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import struct
import tempfile


def audit(layout, boot_id):
    def read(p):return Path(p).read_text().strip()
    boot='/proc/sys/kernel/random/boot_id';state='/sys/class/remoteproc/remoteproc0/state'
    if os.geteuid()!=0 or read(boot)!=boot_id or read(state)!='offline' or b'samsung,gts9wifi' not in Path('/sys/firmware/devicetree/base/compatible').read_bytes().split(b'\0'):
        raise ValueError('root/same-boot/X710/offline-ADSP gate')
    device=Path('/dev/disk/by-partlabel/super').resolve(strict=True)
    if not stat.S_ISBLK(device.stat().st_mode):raise ValueError('super not a block device')
    with device.open('rb',buffering=0) as stream:
        size=struct.unpack('<Q',fcntl.ioctl(stream,0x80081272,bytes(8)))[0]
        extent=layout.vendor_extent(os.pread(stream.fileno(),1024*1024,0),size)
    work=Path(tempfile.mkdtemp(prefix='gts9-rfsa-audit-',dir='/run'));loop=None
    report=dict(boot_id=boot_id,purpose='READ_ONLY_X710_RFSA_DSP_INVENTORY',source_device=str(device),extent=extent,files={},device_deployment=False,remoteproc_started=False,partitions_written=False)
    try:
        loop=Path(layout.run(['losetup','--read-only','--find','--show','--offset',str(extent['offset']),'--sizelimit',str(extent['bytes']),str(device)]))
        if not loop.name.startswith('loop') or read('/sys/block/'+loop.name+'/ro')!='1':raise ValueError('loop not read-only')
        kind=layout.run(['blkid','-p','-s','TYPE','-o','value',str(loop)])
        if kind not in ('ext4','erofs'):raise ValueError('unsupported vendor filesystem')
        options='ro,nosuid,nodev,noexec'+(',noload' if kind=='ext4' else '')
        layout.run(['mount','-t',kind,'-o',options,str(loop),str(work)])
        rows=layout.mounted(work)
        if len(rows)!=1 or not {'ro','nosuid','nodev','noexec'}.issubset(rows[0][3].split(',')):raise ValueError('mount not read-only')
        report['verified_mount']=rows[0]
        report['roots']={}
        for name in ('lib/rfsa/adsp','lib64/rfsa/adsp','dsp'):
            root=work/name;report['roots'][name]=root.is_dir()
            if root.is_symlink():raise ValueError('unexpected RFSA root link')
            if not root.is_dir():continue
            for path in sorted(root.rglob('*')):
                info=path.lstat()
                if stat.S_ISDIR(info.st_mode):continue
                relative='vendor/'+str(path.relative_to(work))
                if stat.S_ISLNK(info.st_mode):
                    report['files'][relative]={'link':os.readlink(path)};continue
                if not stat.S_ISREG(info.st_mode) or info.st_size>64*1024*1024 or len(report['files'])>=4096:
                    raise ValueError('unexpected/oversized RFSA member')
                with path.open('rb') as stream:prefix=stream.read(64)
                meta={'bytes':info.st_size,'elf_machine':struct.unpack_from('<H',prefix,18)[0] if prefix[:4]==b'\x7fELF' and len(prefix)>=20 and prefix[5]==1 else None}
                if path.name=='oemconfig.so':
                    with path.open('rb') as stream:meta['sha256']=hashlib.file_digest(stream,'sha256').hexdigest()
                report['files'][relative]=meta
    finally:
        if layout.mounted(work):layout.run(['umount',str(work)])
        if loop is not None:layout.run(['losetup','--detach',str(loop)])
        work.rmdir()
    if read(boot)!=boot_id or read(state)!='offline':raise ValueError('boot/ADSP changed')
    report['temporary_mount_and_loop_removed']=True
    report['oemconfig_paths']=[n for n in report['files'] if Path(n).name=='oemconfig.so']
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--boot-id',required=True);args=parser.parse_args()
    spec=importlib.util.spec_from_file_location('vendor_layout',Path(__file__).with_name('read-vendor-sensors.py'));layout=importlib.util.module_from_spec(spec);spec.loader.exec_module(layout)
    print(json.dumps(audit(layout,args.boot_id),indent=2))
