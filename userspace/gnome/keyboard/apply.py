#!/usr/bin/env python3
"""Apply the reviewed ms Wayland option after native keymap validation."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import pwd
import subprocess
from validate import validate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--boot-id',required=True)
    parser.add_argument('--evidence',type=Path,required=True)
    args=parser.parse_args()
    if os.geteuid()!=0 or Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=args.boot_id:
        raise ValueError('root/same-boot gate')
    ms=pwd.getpwnam('ms');home=Path(ms.pw_dir);root=home/'.config/xkb'
    if root.exists() or root.is_symlink():raise ValueError('prior custom XKB tree; do not overwrite')
    bus=Path('/run/user')/str(ms.pw_uid)/'bus'
    if not bus.exists():raise ValueError('active GNOME user bus required')
    schema='org.gnome.desktop.input-sources'
    command=['runuser','-u','ms','--','env','DBUS_SESSION_BUS_ADDRESS=unix:path='+str(bus),'gsettings']
    def settings(*argv):return subprocess.check_output(command+list(argv),text=True).strip()
    before=settings('get',schema,'xkb-options');sources=settings('get',schema,'sources')
    if ast.literal_eval(sources)!=[('xkb','us')]:raise ValueError('unreviewed input source')
    options=ast.literal_eval(before.removeprefix('@as '))
    if not isinstance(options,list) or any(not isinstance(x,str) for x in options):raise ValueError('invalid option list')
    args.evidence.mkdir(parents=True,exist_ok=False)
    (args.evidence/'before.json').write_text(json.dumps(dict(boot_id=args.boot_id,xkb_options=before,sources=sources,created_root=str(root)),indent=2)+'\n')
    # Validate in an isolated temporary tree before changing active user data.
    import tempfile,shutil
    here=Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix='gts9-xkb-check-') as temp:
        stage=Path(temp);(stage/'rules').mkdir();(stage/'symbols').mkdir()
        shutil.copyfile(here/'evdev',stage/'rules/evdev');shutil.copyfile(here/'gts9',stage/'symbols/gts9')
        compiled=validate(stage)
    (args.evidence/'native-validation.json').write_text(json.dumps(compiled,indent=2)+'\n')
    files={}
    for name,source in (('rules/evdev','evdev'),('symbols/gts9','gts9')):
        target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
        data=(here/source).read_bytes();target.write_bytes(data);os.chmod(target,0o644)
        files[str(target)]=hashlib.sha256(data).hexdigest()
    for directory in (root,root/'rules',root/'symbols'):
        os.chmod(directory,0o755);os.chown(directory,ms.pw_uid,ms.pw_gid)
    for filename in files:os.chown(filename,ms.pw_uid,ms.pw_gid)
    (args.evidence/'owned-files.json').write_text(json.dumps(files,indent=2)+'\n')
    option='gts9:swap_escape_grave'
    if option not in options:options.append(option)
    try:
        settings('set',schema,'xkb-options',repr(options))
        after=settings('get',schema,'xkb-options')
        if ast.literal_eval(after)!=options or settings('get',schema,'sources')!=sources:
            raise ValueError('keymap settings readback changed')
    except Exception:
        settings('set',schema,'xkb-options',before)
        raise
    result=dict(boot_id=args.boot_id,xkb_options=after,sources=sources,compiled=compiled,physical_confirmation_pending=True)
    (args.evidence/'after.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
