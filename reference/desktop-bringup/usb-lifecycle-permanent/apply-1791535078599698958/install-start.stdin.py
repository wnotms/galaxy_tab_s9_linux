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

rows={'usr/local/libexec/gts9-usb-typec-lifecycle': {'mode': 493, 'bytes': 8923, 'sha256': '06789c3c328d9c09d66743981584b54a47973972f597e2b53ee460e3d7734dfa', 'base64': 'IyEvdXNyL2Jpbi9lbnYgcHl0aG9uMwoiIiJCcmlkZ2UgdmVyaWZpZWQgVHlwZS1DIGNhYmxlIGVkZ2VzIHRvIHRoZSBleGlzdGluZyBmaXhlZC1wZXJpcGhlcmFsIGdhZGdldC4KCk5ldmVyIGNoYW5nZSBkZXNjcmlwdG9ycywgcm9sZXMsIGFkYmQsIFBEIHBvbGljeSBvciBjaGFyZ2VyIHJlZ2lzdGVycy4gRGVwbG95bWVudApyZXF1aXJlcyBhbiBpbmRlcGVuZGVudGx5IHJlZ2lzdGVyZWQgcHJvZmlsZTsgaW1wb3J0aW5nIHRoaXMgbW9kdWxlIGlzIHBhc3NpdmUuCiIiIgppbXBvcnQgYXJncGFyc2UKaW1wb3J0IGZjbnRsCmltcG9ydCBnemlwCmltcG9ydCBoYXNobGliCmltcG9ydCBqc29uCmltcG9ydCBzZWxlY3QKaW1wb3J0IHNpZ25hbAppbXBvcnQgc29ja2V0CmltcG9ydCBzdWJwcm9jZXNzCmltcG9ydCB0aW1lCmZyb20gcGF0aGxpYiBpbXBvcnQgUGF0aAoKCmNsYXNzIEd1YXJkRXJyb3IoUnVudGltZUVycm9yKToKICAgIHBhc3MKCgpkZWYgY2FibGVfc3RhdGUocGFydG5lciwgb25saW5lKToKICAgICMgQSBoYXJkIHJlc2V0IG1heSB0ZW1wb3JhcmlseSByZW1vdmUgVkJVUyB3aGlsZSB0aGUgcGFydG5lciByZW1haW5zLgogICAgaWYgcGFydG5lciBpcyBGYWxzZSBhbmQgb25saW5lID09IDA6CiAgICAgICAgcmV0dXJuICdkZXRhY2hlZCcKICAgIGlmIHBhcnRuZXIgaXMgVHJ1ZSBhbmQgb25saW5lID09IDE6CiAgICAgICAgcmV0dXJuICdhdHRhY2hlZCcKICAgIHJldHVybiAndW5rbm93bicKCgpjbGFzcyBDYWJsZUVkZ2VzOgogICAgZGVmIF9faW5pdF9fKHNlbGYsIGRlYm91bmNlPTEuMCk6CiAgICAgICAgc2VsZi5kZWJvdW5jZSA9IGRlYm91bmNlCiAgICAgICAgc2VsZi5wZW5kaW5nID0gTm9uZQogICAgICAgIHNlbGYuc2luY2UgPSBOb25lCgogICAgZGVmIG9ic2VydmUoc2VsZiwgc3RhdGUsIG5vdyk6CiAgICAgICAgaWYgc3RhdGUgPT0gJ3Vua25vd24nOgogICAgICAgICAgICBzZWxmLnBlbmRpbmcgPSBzZWxmLnNpbmNlID0gTm9uZQogICAgICAgICAgICByZXR1cm4gTm9uZQogICAgICAgIGlmIHN0YXRlICE9IHNlbGYucGVuZGluZzoKICAgICAgICAgICAgc2VsZi5wZW5kaW5nLCBzZWxmLnNpbmNlID0gc3RhdGUsIG5vdwogICAgICAgICAgICByZXR1cm4gTm9uZQogICAgICAgIHJldHVybiBzdGF0ZSBpZiBub3cgLSBzZWxmLnNpbmNlID49IHNlbGYuZGVib3VuY2UgZWxzZSBOb25lCgoKY2xhc3MgR2FkZ2V0OgogICAgZGVmIF9faW5pdF9fKHNlbGYsIHJvb3QsIHByb2ZpbGUpOgogICAgICAgIHNlbGYucm9vdCA9IFBhdGgocm9vdCkKICAgICAgICBzZWxmLnByb2ZpbGUgPSBwcm9maWxlCiAgICAgICAgc2VsZi5wYXRoID0gc2VsZi5yb290IC8gJ3N5cy9rZXJuZWwvY29uZmlnL3VzYl9nYWRnZXQvZ3RzOScKICAgICAgICBzZWxmLnVkYyA9IHNlbGYucGF0aCAvICdVREMnCiAgICAgICAgc2VsZi5vd25lZF91bmJvdW5kID0gRmFsc2UKICAgICAgICBzZWxmLmJvb3QgPSBzZWxmLnJlYWQoJ3Byb2Mvc3lzL2tlcm5lbC9yYW5kb20vYm9vdF9pZCcpCiAgICAgICAgc2VsZi5pZGVudGl0eSgpCiAgICAgICAgc2VsZi5maW5nZXJwcmludCA9IHNlbGYuZGVzY3JpYmUoKQogICAgICAgIHNlbGYuY2hlY2tfbGF5b3V0KCkKICAgICAgICBpZiBzZWxmLnVkYy5yZWFkX3RleHQoKS5zdHJpcCgpICE9ICdhNjAwMDAwLnVzYic6CiAgICAgICAgICAgIHJhaXNlIEd1YXJkRXJyb3IoJ2luaXRpYWwgYmluZGluZyB1bmtub3duOyBkbyBub3QgYWRvcHQgYW4gZW1wdHkgVURDJykKCiAgICBkZWYgcmVhZChzZWxmLCBuYW1lKToKICAgICAgICByZXR1cm4gKHNlbGYucm9vdCAvIG5hbWUpLnJlYWRfdGV4dCgpLnN0cmlwKCkKCiAgICBkZWYgaWRlbnRpdHkoc2VsZik6CiAgICAgICAgY29uZmlnID0gZ3ppcC5kZWNvbXByZXNzKChzZWxmLnJvb3QgLyAncHJvYy9jb25maWcuZ3onKS5yZWFkX2J5dGVzKCkpCiAgICAgICAgbm90ZXMgPSAoc2VsZi5yb290IC8gJ3N5cy9rZXJuZWwvbm90ZXMnKS5yZWFkX2J5dGVzKCkKICAgICAgICBpZiAoc2VsZi5yZWFkKCdldGMvbWFjaGluZS1pZCcpICE9IHNlbGYucHJvZmlsZVsnbWFjaGluZV9pZCddIG9yCiAgICAgICAgICAgIHNlbGYucmVhZCgncHJvYy9zeXMva2VybmVsL3JhbmRvbS9ib290X2lkJykgIT0gc2VsZi5ib290IG9yCiAgICAgICAgICAgIHNlbGYucmVhZCgncHJvYy9zeXMva2VybmVsL29zcmVsZWFzZScpICE9IHNlbGYucHJvZmlsZVsncmVsZWFzZSddIG9yCiAgICAgICAgICAgIGhhc2hsaWIuc2hhMjU2KGNvbmZpZykuaGV4ZGlnZXN0KCkgIT0gc2VsZi5wcm9maWxlWydjb25maWdfc2hhMjU2J10gb3IKICAgICAgICAgICAgaGFzaGxpYi5zaGEyNTYobm90ZXMpLmhleGRpZ2VzdCgpICE9IHNlbGYucHJvZmlsZVsnbm90ZXNfc2hhMjU2J10gb3IKICAgICAgICAgICAgYicjIENPTkZJR19IVkNfRENDIGlzIG5vdCBzZXRcbicgbm90IGluIGNvbmZpZyBvcgogICAgICAgICAgICBzZWxmLnJlYWQoJ3N5cy9tb2R1bGUvc201NDQwX2ZlZG9yYS9wYXJhbWV0ZXJzL2RpcmVjdF9jaGFyZ2UnKSBub3QgaW4gKCdOJywgJzAnKSk6CiAgICAgICAgICAgIHJhaXNlIEd1YXJkRXJyb3IoJ3VucmVnaXN0ZXJlZCBib290L2tlcm5lbCBvciBkaXJlY3QtY2hhcmdlIHN0YXRlJykKICAgICAgICBpZiAoc2VsZi5yZWFkKCdzeXMvY2xhc3MvdHlwZWMvcG9ydDAvcG93ZXJfcm9sZScpICE9ICdbc2lua10nIG9yCiAgICAgICAgICAgIHNlbGYucmVhZCgnc3lzL2NsYXNzL3R5cGVjL3BvcnQwL2RhdGFfcm9sZScpICE9ICdbZGV2aWNlXScpOgogICAgICAgICAgICByYWlzZSBHdWFyZEVycm9yKCdub3QgdGhlIHJlZ2lzdGVyZWQgU2luay9EZXZpY2UgcGVyaXBoZXJhbCcpCgogICAgZGVmIGRlc2NyaWJlKHNlbGYpOgogICAgICAgIHJldHVybiBkaWN0KHZlbmRvcj0oc2VsZi5wYXRoIC8gJ2lkVmVuZG9yJykucmVhZF90ZXh0KCkuc3RyaXAoKSwKICAgICAgICAgICAgICAgICAgICBwcm9kdWN0PShzZWxmLnBhdGggLyAnaWRQcm9kdWN0JykucmVhZF90ZXh0KCkuc3RyaXAoKSwKICAgICAgICAgICAgICAgICAgICBmdW5jdGlvbnM9c29ydGVkKHAubmFtZSBmb3IgcCBpbiAoc2VsZi5wYXRoIC8gJ2Z1bmN0aW9ucycpLml0ZXJkaXIoKSksCiAgICAgICAgICAgICAgICAgICAgbGlua3M9c29ydGVkKChzdHIocC5yZWxhdGl2ZV90byhzZWxmLnBhdGgpKSwgc3RyKHAucmVzb2x2ZSgpKSkKICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgZm9yIHAgaW4gKHNlbGYucGF0aCAvICdjb25maWdzJykucmdsb2IoJyonKSBpZiBwLmlzX3N5bWxpbmsoKSkpCgogICAgZGVmIGNoZWNrX2xheW91dChzZWxmKToKICAgICAgICBkID0gc2VsZi5kZXNjcmliZSgpCiAgICAgICAgaWYgKGQgIT0gc2VsZi5maW5nZXJwcmludCBvciBpbnQoZFsndmVuZG9yJ10sIDE2KSAhPSAweDA1MjUgb3IKICAgICAgICAgICAgaW50KGRbJ3Byb2R1Y3QnXSwgMTYpICE9IDB4YTRhNyBvcgogICAgICAgICAgICBkWydmdW5jdGlvbnMnXSAhPSBbJ2Zmcy5hZGInLCAnbmNtLnVzYjAnXSBvcgogICAgICAgICAgICBsZW4oZFsnbGlua3MnXSkgIT0gMiBvcgogICAgICAgICAgICB7eFswXSBmb3IgeCBpbiBkWydsaW5rcyddfSAhPSB7J2NvbmZpZ3MvYy4xL2Zmcy5hZGInLCAnY29uZmlncy9jLjEvbmNtLnVzYjAnfSBvcgogICAgICAgICAgICB7eFsxXSBmb3IgeCBpbiBkWydsaW5rcyddfSAhPSB7c3RyKHNlbGYucGF0aCAvICdmdW5jdGlvbnMvZmZzLmFkYicpLAogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgc3RyKHNlbGYucGF0aCAvICdmdW5jdGlvbnMvbmNtLnVzYjAnKX0pOgogICAgICAgICAgICByYWlzZSBHdWFyZEVycm9yKCdzaGFyZWQgZ2FkZ2V0IGxheW91dCBjaGFuZ2VkJykKCiAgICBkZWYgc3RhdGUoc2VsZik6CiAgICAgICAgc2VsZi5pZGVudGl0eSgpCiAgICAgICAgb25saW5lID0gc2VsZi5yZWFkKCdzeXMvY2xhc3MvcG93ZXJfc3VwcGx5L3NtNTcxNC11c2Ivb25saW5lJykKICAgICAgICBpZiBvbmxpbmUgbm90IGluICgnMCcsICcxJyk6CiAgICAgICAgICAgIHJhaXNlIEd1YXJkRXJyb3IoJ2ludmFsaWQgVVNCIG9ubGluZSBvYnNlcnZhdGlvbicpCiAgICAgICAgcmV0dXJuIGNhYmxlX3N0YXRlKChzZWxmLnJvb3QgLyAnc3lzL2NsYXNzL3R5cGVjL3BvcnQwLXBhcnRuZXInKS5leGlzdHMoKSwgaW50KG9ubGluZSkpCgogICAgZGVmIHdyaXRlX2JpbmRpbmcoc2VsZiwgdmFsdWUpOgogICAgICAgICMgQSBzdG9wIHNpZ25hbCBiZXR3ZWVuIGEgc3VjY2Vzc2Z1bCBzeXNmcyB3cml0ZSBhbmQgb3VyIG93bmVyc2hpcAogICAgICAgICMgdXBkYXRlIG11c3Qgbm90IHN0cmFuZCB0aGUgc2hhcmVkIGdhZGdldC4gU0lHS0lMTCBjYW5ub3QgYmUgaGFuZGxlZDsKICAgICAgICAjIHNlcnZpY2UgYXV0by1yZXN0YXJ0IGlzIGRlbGliZXJhdGVseSBkaXNhYmxlZCBmb3IgdGhhdCB1bmtub3duIHN0YXRlLgogICAgICAgIHNpZ25hbHMgPSB7c2lnbmFsLlNJR1RFUk0sIHNpZ25hbC5TSUdJTlR9CiAgICAgICAgb2xkID0gc2lnbmFsLnB0aHJlYWRfc2lnbWFzayhzaWduYWwuU0lHX0JMT0NLLCBzaWduYWxzKQogICAgICAgIHRyeToKICAgICAgICAgICAgc2VsZi51ZGMud3JpdGVfdGV4dCh2YWx1ZSArICdcbicpCiAgICAgICAgICAgIHNlbGYub3duZWRfdW5ib3VuZCA9IFRydWUKICAgICAgICAgICAgaWYgc2VsZi51ZGMucmVhZF90ZXh0KCkuc3RyaXAoKSAhPSB2YWx1ZToKICAgICAgICAgICAgICAgIHJhaXNlIEd1YXJkRXJyb3IoJ2JpbmRpbmcgd3JpdGUvcmVhZGJhY2sgbWlzbWF0Y2gnKQogICAgICAgICAgICBzZWxmLm93bmVkX3VuYm91bmQgPSBub3QgYm9vbCh2YWx1ZSkKICAgICAgICBmaW5hbGx5OgogICAgICAgICAgICBzaWduYWwucHRocmVhZF9zaWdtYXNrKHNpZ25hbC5TSUdfU0VUTUFTSywgb2xkKQoKICAgIGRlZiBhcHBseShzZWxmLCBzdGFibGUpOgogICAgICAgIHNlbGYuaWRlbnRpdHkoKQogICAgICAgIHNlbGYuY2hlY2tfbGF5b3V0KCkKICAgICAgICBib3VuZCA9IHNlbGYudWRjLnJlYWRfdGV4dCgpLnN0cmlwKCkKICAgICAgICBleHBlY3RlZCA9ICcnIGlmIHNlbGYub3duZWRfdW5ib3VuZCBlbHNlICdhNjAwMDAwLnVzYicKICAgICAgICBpZiBib3VuZCAhPSBleHBlY3RlZDoKICAgICAgICAgICAgcmFpc2UgR3VhcmRFcnJvcignYW5vdGhlciBhY3RvciBjaGFuZ2VkIFVEQzsgcmVmdXNlIHRvIG92ZXJ3cml0ZScpCiAgICAgICAgIyBSZWNoZWNrIGNhYmxlIGltbWVkaWF0ZWx5IGJlZm9yZSB0aGUgd3JpdGUuIE5vIGRlbGF5ZWQgc3RhbGUgYWN0aW9uLgogICAgICAgIGlmIHN0YWJsZSBub3QgaW4gKCdhdHRhY2hlZCcsICdkZXRhY2hlZCcpIG9yIHNlbGYuc3RhdGUoKSAhPSBzdGFibGU6CiAgICAgICAgICAgIHJldHVybiBOb25lCiAgICAgICAgaWYgc3RhYmxlID09ICdkZXRhY2hlZCcgYW5kIG5vdCBzZWxmLm93bmVkX3VuYm91bmQ6CiAgICAgICAgICAgIHNlbGYud3JpdGVfYmluZGluZygnJykKICAgICAgICAgICAgcmV0dXJuICd1bmJpbmQnCiAgICAgICAgaWYgc3RhYmxlID09ICdhdHRhY2hlZCcgYW5kIHNlbGYub3duZWRfdW5ib3VuZDoKICAgICAgICAgICAgc2VsZi53cml0ZV9iaW5kaW5nKCdhNjAwMDAwLnVzYicpCiAgICAgICAgICAgIHJldHVybiAnYmluZCcKICAgICAgICByZXR1cm4gTm9uZQoKICAgIGRlZiByZXN0b3JlKHNlbGYpOgogICAgICAgIGlmIHNlbGYub3duZWRfdW5ib3VuZDoKICAgICAgICAgICAgc2VsZi5pZGVudGl0eSgpCiAgICAgICAgICAgIHNlbGYuY2hlY2tfbGF5b3V0KCkKICAgICAgICAgICAgYm91bmQgPSBzZWxmLnVkYy5yZWFkX3RleHQoKS5zdHJpcCgpCiAgICAgICAgICAgIGlmIGJvdW5kID09ICdhNjAwMDAwLnVzYic6CiAgICAgICAgICAgICAgICBzZWxmLm93bmVkX3VuYm91bmQgPSBGYWxzZQogICAgICAgICAgICAgICAgcmV0dXJuCiAgICAgICAgICAgIGlmIGJvdW5kOgogICAgICAgICAgICAgICAgcmFpc2UgR3VhcmRFcnJvcignb3duZWQgZW1wdHkgYmluZGluZyBjaGFuZ2VkOyByZWNvdmVyeSByZWZ1c2VkJykKICAgICAgICAgICAgc2VsZi53cml0ZV9iaW5kaW5nKCdhNjAwMDAwLnVzYicpCgoKZGVmIHJlbGV2YW50X3VldmVudChkYXRhLCBzZW5kZXIpOgogICAgaWYgc2VuZGVyWzBdICE9IDAgb3IgbGVuKGRhdGEpID49IDY1NTM2OgogICAgICAgIHJldHVybiBGYWxzZQogICAgZmllbGRzID0ge30KICAgIGZvciBwYXJ0IGluIGRhdGEuc3BsaXQoYidcMCcpWzE6XToKICAgICAgICBpZiBiJz0nIGluIHBhcnQ6CiAgICAgICAgICAgIGtleSwgdmFsdWUgPSBwYXJ0LnNwbGl0KGInPScsIDEpCiAgICAgICAgICAgIGlmIGtleSBpbiBmaWVsZHM6CiAgICAgICAgICAgICAgICByZXR1cm4gRmFsc2UKICAgICAgICAgICAgZmllbGRzW2tleV0gPSB2YWx1ZQogICAgcmV0dXJuIChmaWVsZHMuZ2V0KGInU1VCU1lTVEVNJykgPT0gYid0eXBlYycgb3IKICAgICAgICAgICAgKGZpZWxkcy5nZXQoYidTVUJTWVNURU0nKSA9PSBiJ3Bvd2VyX3N1cHBseScgYW5kCiAgICAgICAgICAgICBmaWVsZHMuZ2V0KGInREVWUEFUSCcsIGInJykuZW5kc3dpdGgoYicvc201NzE0LXVzYicpKSkKCgpkZWYgc2VydmUoZ2FkZ2V0LCBzb2NrLCBjbG9jaz10aW1lLm1vbm90b25pYyk6CiAgICBlZGdlcyA9IENhYmxlRWRnZXMoKQogICAgcGVuZGluZ19jaGVjayA9IGNsb2NrKCkgICMgSW5pdGlhbCBkZXRhY2hlZCBzdGFsZSBzdGF0ZSBpcyBhbHNvIHJlcGFpcmVkLgogICAgdHJ5OgogICAgICAgIHdoaWxlIFRydWU6CiAgICAgICAgICAgIG5vdyA9IGNsb2NrKCkKICAgICAgICAgICAgdGltZW91dCA9IE5vbmUgaWYgcGVuZGluZ19jaGVjayBpcyBOb25lIGVsc2UgbWF4KDAsIHBlbmRpbmdfY2hlY2sgLSBub3cpCiAgICAgICAgICAgIGlmIHNlbGVjdC5zZWxlY3QoW3NvY2tdLCBbXSwgW10sIHRpbWVvdXQpWzBdOgogICAgICAgICAgICAgICAgZGF0YSwgc2VuZGVyID0gc29jay5yZWN2ZnJvbSg2NTUzNikKICAgICAgICAgICAgICAgIGlmIHJlbGV2YW50X3VldmVudChkYXRhLCBzZW5kZXIpIGFuZCBwZW5kaW5nX2NoZWNrIGlzIE5vbmU6CiAgICAgICAgICAgICAgICAgICAgcGVuZGluZ19jaGVjayA9IGNsb2NrKCkgKyAwLjEKICAgICAgICAgICAgaWYgcGVuZGluZ19jaGVjayBpcyBub3QgTm9uZSBhbmQgY2xvY2soKSA+PSBwZW5kaW5nX2NoZWNrOgogICAgICAgICAgICAgICAgc3RhdGUgPSBnYWRnZXQuc3RhdGUoKQogICAgICAgICAgICAgICAgc3RhYmxlID0gZWRnZXMub2JzZXJ2ZShzdGF0ZSwgY2xvY2soKSkKICAgICAgICAgICAgICAgIGlmIHN0YWJsZSBpcyBub3QgTm9uZToKICAgICAgICAgICAgICAgICAgICBhY3Rpb24gPSBnYWRnZXQuYXBwbHkoc3RhYmxlKQogICAgICAgICAgICAgICAgICAgIGlmIGFjdGlvbjoKICAgICAgICAgICAgICAgICAgICAgICAgcHJpbnQoanNvbi5kdW1wcyhkaWN0KGJvb3RfaWQ9Z2FkZ2V0LmJvb3QsIGV2ZW50PWFjdGlvbiwKICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNhYmxlPXN0YWJsZSwgbW9ub3RvbmljPWNsb2NrKCkpKSwgZmx1c2g9VHJ1ZSkKICAgICAgICAgICAgICAgICAgICBwZW5kaW5nX2NoZWNrID0gTm9uZQogICAgICAgICAgICAgICAgZWxpZiBzdGF0ZSA9PSAndW5rbm93bic6CiAgICAgICAgICAgICAgICAgICAgIyBBd2FpdCBhIHJlYWwgbmV3IFR5cGUtQy9VU0IgZXZlbnQuIERvIG5vdCBwb2xsIHRoZSBJMkMKICAgICAgICAgICAgICAgICAgICAjIHN1cHBseSBvciByZXNldCBhIGxpdmUgbGluayB0aHJvdWdoIGEgUEQgdHJhbnNpZW50LgogICAgICAgICAgICAgICAgICAgIHBlbmRpbmdfY2hlY2sgPSBOb25lCiAgICAgICAgICAgICAgICBlbHNlOgogICAgICAgICAgICAgICAgICAgIHBlbmRpbmdfY2hlY2sgPSBjbG9jaygpICsgZWRnZXMuZGVib3VuY2UKICAgIGZpbmFsbHk6CiAgICAgICAgZ2FkZ2V0LnJlc3RvcmUoKQoKCmRlZiBtYWluKCk6CiAgICBhcCA9IGFyZ3BhcnNlLkFyZ3VtZW50UGFyc2VyKGRlc2NyaXB0aW9uPV9fZG9jX18pCiAgICBhcC5hZGRfYXJndW1lbnQoJy0tcHJvZmlsZScsIHR5cGU9UGF0aCwgcmVxdWlyZWQ9VHJ1ZSkKICAgIGFyZ3MgPSBhcC5wYXJzZV9hcmdzKCkKICAgIHByb2ZpbGUgPSBqc29uLmxvYWRzKGFyZ3MucHJvZmlsZS5yZWFkX3RleHQoKSkKICAgIHdpdGggUGF0aCgnL3J1bi9ndHM5LXVzYi10eXBlYy1saWZlY3ljbGUubG9jaycpLm9wZW4oJ3cnKSBhcyBsb2NrOgogICAgICAgIGZjbnRsLmZsb2NrKGxvY2ssIGZjbnRsLkxPQ0tfRVggfCBmY250bC5MT0NLX05CKQogICAgICAgIGdhZGdldCA9IEdhZGdldCgnLycsIHByb2ZpbGUpCiAgICAgICAgaWYgc3VicHJvY2Vzcy5ydW4oWydzeXN0ZW1jdGwnLCAnaXMtYWN0aXZlJywgJy0tcXVpZXQnLCAnZ3RzOS1hZGJkJ10sIHRpbWVvdXQ9NSkucmV0dXJuY29kZToKICAgICAgICAgICAgcmFpc2UgR3VhcmRFcnJvcignYWRiZCBub3QgcmVhZHk7IG5vIFVEQyBhY3Rpb24nKQogICAgICAgIGRlZiBzdG9wKHNpZ251bSwgZnJhbWUpOgogICAgICAgICAgICByYWlzZSBJbnRlcnJ1cHRlZEVycm9yKCdsaWZlY3ljbGUgc2VydmljZSBzdG9wcGVkJykKICAgICAgICBzaWduYWwuc2lnbmFsKHNpZ25hbC5TSUdURVJNLCBzdG9wKQogICAgICAgIHNpZ25hbC5zaWduYWwoc2lnbmFsLlNJR0lOVCwgc3RvcCkKICAgICAgICB3aXRoIHNvY2tldC5zb2NrZXQoc29ja2V0LkFGX05FVExJTkssIHNvY2tldC5TT0NLX0RHUkFNLCAxNSkgYXMgc29jazoKICAgICAgICAgICAgc29jay5iaW5kKCgwLCAxKSkKICAgICAgICAgICAgc2VydmUoZ2FkZ2V0LCBzb2NrKQoKCmlmIF9fbmFtZV9fID09ICdfX21haW5fXyc6CiAgICB0cnk6CiAgICAgICAgbWFpbigpCiAgICBleGNlcHQgSW50ZXJydXB0ZWRFcnJvcjoKICAgICAgICBwYXNzCg=='}, 'etc/gts9-usb-typec-profile.json': {'mode': 420, 'bytes': 269, 'sha256': '8507ce5a61ca59c826fc9f56e8c316e8497e545020b901b5ae01faec78b1f33e', 'base64': 'ewogICJjb25maWdfc2hhMjU2IjogIjU5OWNhNDdhYjQxYTI5NDY5YzNkNTgzMGU0NzUwNDlmY2E5ZjMzYmQyYWIwOTIzYWQwMTRlNWJhM2ZhNmVjNmMiLAogICJtYWNoaW5lX2lkIjogIjNjMmExYjhmMmQ2MjRkYjRiNWZmZGM4MzYwNTBmY2Y2IiwKICAibm90ZXNfc2hhMjU2IjogIjVjMGU4MjMzN2FmZmFmZWZmZjU4NjYxM2Q0YTg0YzRmMTM4OGM5NzE2Y2UyNTFmZTY5ZDNjNzBhYWQxOGE1MTgiLAogICJyZWxlYXNlIjogIjcuMi4wLXJjMy1ndHM5d2lmaS1kaXJ0eSIKfQo='}, 'etc/systemd/system/gts9-usb-typec-lifecycle.service': {'mode': 420, 'bytes': 420, 'sha256': '8ff7d6a4a35b3607b210cae45ba9c28fe00c1f7866d6589e3d12353408b3d75f', 'base64': 'W1VuaXRdCkRlc2NyaXB0aW9uPUdUUzkgZml4ZWQtcGVyaXBoZXJhbCBVU0IgVHlwZS1DIGxpZmVjeWNsZQpBZnRlcj1ndHM5LXVzYi1hY20uc2VydmljZSBndHM5LWFkYmQuc2VydmljZQpXYW50cz1ndHM5LXVzYi1hY20uc2VydmljZSBndHM5LWFkYmQuc2VydmljZQpDb25kaXRpb25QYXRoRXhpc3RzPS9ldGMvZ3RzOS11c2ItdHlwZWMtcHJvZmlsZS5qc29uCgpbU2VydmljZV0KVHlwZT1zaW1wbGUKRXhlY1N0YXJ0PS91c3IvYmluL3B5dGhvbjMgL3Vzci9sb2NhbC9saWJleGVjL2d0czktdXNiLXR5cGVjLWxpZmVjeWNsZSAtLXByb2ZpbGUgL2V0Yy9ndHM5LXVzYi10eXBlYy1wcm9maWxlLmpzb24KUmVzdGFydD1ubwpUaW1lb3V0U3RvcFNlYz01cwpVTWFzaz0wMDc3CgpbSW5zdGFsbF0KV2FudGVkQnk9bXVsdGktdXNlci50YXJnZXQK'}}
profile={'config_sha256': '599ca47ab41a29469c3d5830e475049fca9f33bd2ab0923ad014e5ba3fa6ec6c', 'machine_id': '3c2a1b8f2d624db4b5ffdc836050fcf6', 'notes_sha256': '5c0e82337affafefff586613d4a84c4f1388c9716ce251fe69d3c70aad18a518', 'release': '7.2.0-rc3-gts9wifi-dirty'}
boot='d1977159-8330-4c90-b5be-e7cf8c67ea0f'
print(json.dumps(install_permanent('/',rows,boot)))
activate(rows,profile,boot)
