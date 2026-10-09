#!/usr/bin/env python3
"""Qualified permanent three-file, same-boot userspace transaction; no flash or reboot.

Import is passive. Unknown existing files are never adopted or overwritten.
The caller records full journals before start and after each physical boundary.
"""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess


PATHS = {
    'usr/local/libexec/gts9-usb-typec-lifecycle': 0o755,
    'etc/gts9-usb-typec-profile.json': 0o644,
    'etc/systemd/system/gts9-usb-typec-lifecycle.service': 0o644,
}
UNIT = 'gts9-usb-typec-lifecycle.service'
STATE = 'var/lib/gts9-usb-lifecycle-deployment'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe(root, name):
    if name not in (*PATHS, *(n+'.usb-lifecycle-pending' for n in PATHS), STATE, STATE+'/ledger.json', STATE+'/ledger.json.pending'):
        raise ValueError('unregistered path')
    root = Path(root)
    dest = root/name
    for path in (dest, *dest.parents):
        if path == root:
            break
        if path.is_symlink():
            raise ValueError('symlink in destination')
    return dest


def qualified(rows):
    if set(rows) != set(PATHS):
        raise ValueError('three-file manifest required')
    result = {}
    for name, row in rows.items():
        data = base64.b64decode(row['base64'], validate=True)
        if digest(data) != row['sha256'] or len(data) != row['bytes'] or row['mode'] != PATHS[name]:
            raise ValueError('payload mismatch')
        result[name] = data
    return result


def save_ledger(root, ledger):
    pending=safe(root, STATE+'/ledger.json.pending')
    with pending.open('x') as stream:
        json.dump(ledger, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    target=safe(root, STATE+'/ledger.json')
    os.replace(pending,target)
    fd=os.open(target.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def verify_files(root, rows, *, partial=False):
    qualified(rows)
    for name, row in rows.items():
        path = safe(root, name)
        if not path.exists() and partial:
            continue
        st = path.stat()
        if (not stat.S_ISREG(st.st_mode) or digest(path.read_bytes()) != row['sha256'] or
                stat.S_IMODE(st.st_mode) != row['mode'] or st.st_uid != os.geteuid()):
            raise ValueError('installed file drift: '+name)


def install(root, rows, boot):
    payload = qualified(rows)
    state = safe(root, STATE)
    if state.exists():
        raise ValueError('one attempt only; transaction already exists')
    # Validate the entire transaction before making the first directory/file.
    for name in PATHS:
        if safe(root, name).exists() or safe(root, name+'.usb-lifecycle-pending').exists():
            raise ValueError('pre-existing file; do not overwrite '+name)
    state.mkdir(parents=True, mode=0o700)
    ledger = dict(test='permanent-1', boot_id=boot, files={n: {k:v for k,v in r.items() if k!='base64'} for n,r in rows.items()},
                  originals='all absent', status='installing')
    save_ledger(root, ledger)
    # The durable ledger describes even a partially completed install.
    for name, data in payload.items():
        path = safe(root, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        pending = safe(root, name+'.usb-lifecycle-pending')
        with pending.open('xb') as stream:
            os.fchmod(stream.fileno(), PATHS[name])
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        # Expose only a complete file; an interrupted temporary is ledger-owned.
        os.link(pending, path)
        pending.unlink()
    verify_files(root, rows)
    ledger['status'] = 'installed_not_enabled'
    # Status is advisory. Recovery always verifies the exact frozen manifest.
    save_ledger(root, ledger)
    return ledger


def restore_files(root, rows, boot):
    ledger_path = safe(root, STATE+'/ledger.json')
    ledger = json.loads(ledger_path.read_text())
    expected = {n: {k:v for k,v in r.items() if k!='base64'} for n,r in rows.items()}
    if (ledger['test'] != 'permanent-1' or ledger['boot_id'] != boot or ledger['files'] != expected or
            ledger['originals'] != 'all absent'):
        raise ValueError('transaction ownership drift')
    verify_files(root, rows, partial=True)
    payload = qualified(rows)
    for name in PATHS:
        pending = safe(root, name+'.usb-lifecycle-pending')
        if pending.exists():
            st = pending.stat()
            data = pending.read_bytes()
            if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or
                    stat.S_IMODE(st.st_mode) != PATHS[name] or
                    len(data) > len(payload[name]) or data != payload[name][:len(data)]):
                raise ValueError('interrupted temporary drift')
    for name in PATHS:
        safe(root, name).unlink(missing_ok=True)
        safe(root, name+'.usb-lifecycle-pending').unlink(missing_ok=True)
    ledger['status'] = 'rolled_back'
    save_ledger(root, ledger)
    return ledger


def guard(profile, boot, helper_source=None):
    # Execute hash-qualified source without importing or creating helper pyc.
    if helper_source is None:
        raise ValueError('frozen helper source required; no bytecode import')
    namespace = {'__name__': 'passive_recovery_helper'}
    exec(helper_source, namespace)
    constructor = namespace['Gadget']
    if Path('/proc/sys/kernel/random/boot_id').read_text().strip() != boot:
        raise ValueError('boot changed; stop')
    return constructor('/', profile)


LINK = 'etc/systemd/system/multi-user.target.wants/'+UNIT


def enabled_link(root):
    path=Path(root)/LINK
    for parent in path.parents:
        if parent==Path(root):break
        if parent.is_symlink():raise ValueError('enabled-link parent symlink')
    if path.exists() or path.is_symlink():
        if not path.is_symlink() or os.readlink(path)!='../'+UNIT:
            raise ValueError('unknown enabled link')
        return path
    return None


def install_permanent(root, rows, boot):
    if enabled_link(root) is not None:
        raise ValueError('pre-existing enabled link')
    ledger=install(root,rows,boot)
    ledger['enabled_link']=dict(path=LINK,target='../'+UNIT,original='absent')
    ledger['status']='enabling'
    save_ledger(root,ledger)
    link=Path(root)/LINK
    link.parent.mkdir(parents=True,exist_ok=True)
    link.symlink_to('../'+UNIT)
    ledger['status']='enabled_not_started'
    save_ledger(root,ledger)
    return ledger


def rollback_permanent(root, rows, boot):
    ledger=json.loads(safe(root,STATE+'/ledger.json').read_text())
    if ledger.get('enabled_link') not in (None,dict(path=LINK,target='../'+UNIT,original='absent')):
        raise ValueError('link ownership drift')
    verify_files(root,rows,partial=True)
    link=enabled_link(root)
    # Validate the complete transaction before removing either link or files.
    expected={n:{k:v for k,v in row.items() if k!='base64'} for n,row in rows.items()}
    if ledger['test']!='permanent-1' or ledger['boot_id']!=boot or ledger['files']!=expected or ledger['originals']!='all absent':
        raise ValueError('transaction ownership drift')
    result=restore_files(root,rows,boot)
    if link is not None:link.unlink()
    return result


def activate(rows,profile,boot):
    verify_files('/',rows)
    gadget=guard(profile,boot,qualified(rows)['usr/local/libexec/gts9-usb-typec-lifecycle'].decode())
    if gadget.state()!='attached' or enabled_link('/') is None:
        raise ValueError('require healthy attached PC and owned enablement')
    subprocess.run(['systemctl','daemon-reload'],check=True,timeout=10)
    subprocess.run(['systemctl','start',UNIT],check=True,timeout=10)


def deactivate(rows,profile,boot):
    verify_files('/',rows,partial=True)
    enabled_link('/')
    subprocess.run(['systemctl','stop',UNIT],check=True,timeout=10)
    if subprocess.run(['systemctl','is-active','--quiet',UNIT],timeout=5).returncode==0:
        raise ValueError('service still active')
    guard(profile,boot,qualified(rows)['usr/local/libexec/gts9-usb-typec-lifecycle'].decode())
    result=rollback_permanent('/',rows,boot)
    subprocess.run(['systemctl','daemon-reload'],check=True,timeout=10)
    return result


def capture():
    root = Path('/')
    def read(name):
        return (root/name).read_text().strip()
    def command(*args):
        p = subprocess.run(args, capture_output=True, text=True, timeout=10)
        return dict(status=p.returncode, stdout=p.stdout, stderr=p.stderr)
    import gzip
    return dict(boot_id=read('proc/sys/kernel/random/boot_id'), machine_id=read('etc/machine-id'),
                uptime=read('proc/uptime'), cmdline=read('proc/cmdline'),
                release=read('proc/sys/kernel/osrelease'), config_sha256=digest(gzip.decompress((root/'proc/config.gz').read_bytes())),
                notes_sha256=digest((root/'sys/kernel/notes').read_bytes()),
                direct=read('sys/module/sm5440_fedora/parameters/direct_charge'),
                roles={n:read('sys/class/typec/port0/'+n) for n in ('power_role','data_role')},
                battery=dict(line.split('=',1) for line in read('sys/class/power_supply/sm5714-battery/uevent').splitlines()),
                usb_online=read('sys/class/power_supply/sm5714-usb/online'),
                partner=(root/'sys/class/typec/port0-partner').exists(),
                udc=read('sys/kernel/config/usb_gadget/gts9/UDC'),
                udc_state=read('sys/class/udc/a600000.usb/state'),
                failed=command('systemctl','--failed','--no-legend','--plain','--no-pager'),
                services=command('systemctl','is-active','ssh','gdm','gts9-adbd','gts9-usb-acm'),
                network=command('ip','-br','addr'),
                kernel=command('journalctl','-k','-b','-o','json','--no-pager'),
                lifecycle=command('journalctl','-b','-u',UNIT,'-o','json','--no-pager'),
                lifecycle_state=command('systemctl','show',UNIT,'-p','ActiveState','-p','Result','-p','MainPID'))
