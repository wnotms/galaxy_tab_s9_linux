#!/usr/bin/env python3
"""Test367's three-file, same-boot userspace transaction; no flash or reboot.

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
UNIT = 'gts9-test367-lifecycle.service'
STATE = 'var/lib/gts9-test367'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe(root, name):
    if name not in (*PATHS, *(n+'.test367-pending' for n in PATHS), STATE, STATE+'/ledger.json', STATE+'/ledger.json.pending'):
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
        if safe(root, name).exists() or safe(root, name+'.test367-pending').exists():
            raise ValueError('pre-existing file; do not overwrite '+name)
    state.mkdir(parents=True, mode=0o700)
    ledger = dict(test=367, boot_id=boot, files={n: {k:v for k,v in r.items() if k!='base64'} for n,r in rows.items()},
                  originals='all absent', status='installing')
    save_ledger(root, ledger)
    # The durable ledger describes even a partially completed install.
    for name, data in payload.items():
        path = safe(root, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        pending = safe(root, name+'.test367-pending')
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
    if (ledger['test'] != 367 or ledger['boot_id'] != boot or ledger['files'] != expected or
            ledger['originals'] != 'all absent'):
        raise ValueError('transaction ownership drift')
    verify_files(root, rows, partial=True)
    payload = qualified(rows)
    for name in PATHS:
        pending = safe(root, name+'.test367-pending')
        if pending.exists():
            st = pending.stat()
            data = pending.read_bytes()
            if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or
                    stat.S_IMODE(st.st_mode) != PATHS[name] or
                    len(data) > len(payload[name]) or data != payload[name][:len(data)]):
                raise ValueError('interrupted temporary drift')
    for name in PATHS:
        safe(root, name).unlink(missing_ok=True)
        safe(root, name+'.test367-pending').unlink(missing_ok=True)
    ledger['status'] = 'rolled_back'
    save_ledger(root, ledger)
    return ledger


def guard(profile, boot, helper_source=None):
    # The installed helper has no .py suffix; SourceFileLoader is explicit.
    if helper_source is None:
        from importlib.machinery import SourceFileLoader
        spec = importlib.util.spec_from_loader('lifecycle', SourceFileLoader('lifecycle', '/usr/local/libexec/gts9-usb-typec-lifecycle'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        constructor = module.Gadget
    else:
        namespace = {'__name__': 'passive_recovery_helper'}
        exec(helper_source, namespace)
        constructor = namespace['Gadget']
    if Path('/proc/sys/kernel/random/boot_id').read_text().strip() != boot:
        raise ValueError('boot changed; stop')
    return constructor('/', profile)


def activate(rows, profile, boot):
    verify_files('/', rows)
    gadget = guard(profile, boot)
    if gadget.state() != 'detached':
        raise ValueError('start requires observed physical unplug')
    subprocess.run(['systemctl', 'daemon-reload'], check=True, timeout=10)
    subprocess.run(['systemd-run', '--unit='+UNIT, '--collect', '--property=RuntimeMaxSec=1200',
                    '--property=TimeoutStopSec=5', '--property=Restart=no',
                    '/usr/bin/python3', '/usr/local/libexec/gts9-usb-typec-lifecycle',
                    '--profile', '/etc/gts9-usb-typec-profile.json'], check=True, timeout=10)


def deactivate(rows, profile, boot):
    # SIGTERM/finally restore owned binding. Unknown state must not be adopted.
    verify_files('/', rows, partial=True)
    state = subprocess.run(['systemctl', 'show', UNIT, '-p', 'LoadState', '--value'],
                           capture_output=True, text=True, timeout=5)
    if state.returncode or state.stdout.strip() != 'not-found':
        subprocess.run(['systemctl', 'stop', UNIT], check=True, timeout=10)
    if subprocess.run(['systemctl', 'is-active', '--quiet', UNIT], timeout=5).returncode == 0:
        raise ValueError('service still active')
    # A partial install may not expose the helper yet. Only frozen source from
    # the host payload is executed; never import a drifted device file.
    guard(profile, boot, qualified(rows)['usr/local/libexec/gts9-usb-typec-lifecycle'].decode())
    result = restore_files('/', rows, boot)
    subprocess.run(['systemctl', 'daemon-reload'], check=True, timeout=10)
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

rows={'usr/local/libexec/gts9-usb-typec-lifecycle': {'mode': 493, 'bytes': 8923, 'sha256': '06789c3c328d9c09d66743981584b54a47973972f597e2b53ee460e3d7734dfa', 'base64': 'IyEvdXNyL2Jpbi9lbnYgcHl0aG9uMwoiIiJCcmlkZ2UgdmVyaWZpZWQgVHlwZS1DIGNhYmxlIGVkZ2VzIHRvIHRoZSBleGlzdGluZyBmaXhlZC1wZXJpcGhlcmFsIGdhZGdldC4KCk5ldmVyIGNoYW5nZSBkZXNjcmlwdG9ycywgcm9sZXMsIGFkYmQsIFBEIHBvbGljeSBvciBjaGFyZ2VyIHJlZ2lzdGVycy4gRGVwbG95bWVudApyZXF1aXJlcyBhbiBpbmRlcGVuZGVudGx5IHJlZ2lzdGVyZWQgcHJvZmlsZTsgaW1wb3J0aW5nIHRoaXMgbW9kdWxlIGlzIHBhc3NpdmUuCiIiIgppbXBvcnQgYXJncGFyc2UKaW1wb3J0IGZjbnRsCmltcG9ydCBnemlwCmltcG9ydCBoYXNobGliCmltcG9ydCBqc29uCmltcG9ydCBzZWxlY3QKaW1wb3J0IHNpZ25hbAppbXBvcnQgc29ja2V0CmltcG9ydCBzdWJwcm9jZXNzCmltcG9ydCB0aW1lCmZyb20gcGF0aGxpYiBpbXBvcnQgUGF0aAoKCmNsYXNzIEd1YXJkRXJyb3IoUnVudGltZUVycm9yKToKICAgIHBhc3MKCgpkZWYgY2FibGVfc3RhdGUocGFydG5lciwgb25saW5lKToKICAgICMgQSBoYXJkIHJlc2V0IG1heSB0ZW1wb3JhcmlseSByZW1vdmUgVkJVUyB3aGlsZSB0aGUgcGFydG5lciByZW1haW5zLgogICAgaWYgcGFydG5lciBpcyBGYWxzZSBhbmQgb25saW5lID09IDA6CiAgICAgICAgcmV0dXJuICdkZXRhY2hlZCcKICAgIGlmIHBhcnRuZXIgaXMgVHJ1ZSBhbmQgb25saW5lID09IDE6CiAgICAgICAgcmV0dXJuICdhdHRhY2hlZCcKICAgIHJldHVybiAndW5rbm93bicKCgpjbGFzcyBDYWJsZUVkZ2VzOgogICAgZGVmIF9faW5pdF9fKHNlbGYsIGRlYm91bmNlPTEuMCk6CiAgICAgICAgc2VsZi5kZWJvdW5jZSA9IGRlYm91bmNlCiAgICAgICAgc2VsZi5wZW5kaW5nID0gTm9uZQogICAgICAgIHNlbGYuc2luY2UgPSBOb25lCgogICAgZGVmIG9ic2VydmUoc2VsZiwgc3RhdGUsIG5vdyk6CiAgICAgICAgaWYgc3RhdGUgPT0gJ3Vua25vd24nOgogICAgICAgICAgICBzZWxmLnBlbmRpbmcgPSBzZWxmLnNpbmNlID0gTm9uZQogICAgICAgICAgICByZXR1cm4gTm9uZQogICAgICAgIGlmIHN0YXRlICE9IHNlbGYucGVuZGluZzoKICAgICAgICAgICAgc2VsZi5wZW5kaW5nLCBzZWxmLnNpbmNlID0gc3RhdGUsIG5vdwogICAgICAgICAgICByZXR1cm4gTm9uZQogICAgICAgIHJldHVybiBzdGF0ZSBpZiBub3cgLSBzZWxmLnNpbmNlID49IHNlbGYuZGVib3VuY2UgZWxzZSBOb25lCgoKY2xhc3MgR2FkZ2V0OgogICAgZGVmIF9faW5pdF9fKHNlbGYsIHJvb3QsIHByb2ZpbGUpOgogICAgICAgIHNlbGYucm9vdCA9IFBhdGgocm9vdCkKICAgICAgICBzZWxmLnByb2ZpbGUgPSBwcm9maWxlCiAgICAgICAgc2VsZi5wYXRoID0gc2VsZi5yb290IC8gJ3N5cy9rZXJuZWwvY29uZmlnL3VzYl9nYWRnZXQvZ3RzOScKICAgICAgICBzZWxmLnVkYyA9IHNlbGYucGF0aCAvICdVREMnCiAgICAgICAgc2VsZi5vd25lZF91bmJvdW5kID0gRmFsc2UKICAgICAgICBzZWxmLmJvb3QgPSBzZWxmLnJlYWQoJ3Byb2Mvc3lzL2tlcm5lbC9yYW5kb20vYm9vdF9pZCcpCiAgICAgICAgc2VsZi5pZGVudGl0eSgpCiAgICAgICAgc2VsZi5maW5nZXJwcmludCA9IHNlbGYuZGVzY3JpYmUoKQogICAgICAgIHNlbGYuY2hlY2tfbGF5b3V0KCkKICAgICAgICBpZiBzZWxmLnVkYy5yZWFkX3RleHQoKS5zdHJpcCgpICE9ICdhNjAwMDAwLnVzYic6CiAgICAgICAgICAgIHJhaXNlIEd1YXJkRXJyb3IoJ2luaXRpYWwgYmluZGluZyB1bmtub3duOyBkbyBub3QgYWRvcHQgYW4gZW1wdHkgVURDJykKCiAgICBkZWYgcmVhZChzZWxmLCBuYW1lKToKICAgICAgICByZXR1cm4gKHNlbGYucm9vdCAvIG5hbWUpLnJlYWRfdGV4dCgpLnN0cmlwKCkKCiAgICBkZWYgaWRlbnRpdHkoc2VsZik6CiAgICAgICAgY29uZmlnID0gZ3ppcC5kZWNvbXByZXNzKChzZWxmLnJvb3QgLyAncHJvYy9jb25maWcuZ3onKS5yZWFkX2J5dGVzKCkpCiAgICAgICAgbm90ZXMgPSAoc2VsZi5yb290IC8gJ3N5cy9rZXJuZWwvbm90ZXMnKS5yZWFkX2J5dGVzKCkKICAgICAgICBpZiAoc2VsZi5yZWFkKCdldGMvbWFjaGluZS1pZCcpICE9IHNlbGYucHJvZmlsZVsnbWFjaGluZV9pZCddIG9yCiAgICAgICAgICAgIHNlbGYucmVhZCgncHJvYy9zeXMva2VybmVsL3JhbmRvbS9ib290X2lkJykgIT0gc2VsZi5ib290IG9yCiAgICAgICAgICAgIHNlbGYucmVhZCgncHJvYy9zeXMva2VybmVsL29zcmVsZWFzZScpICE9IHNlbGYucHJvZmlsZVsncmVsZWFzZSddIG9yCiAgICAgICAgICAgIGhhc2hsaWIuc2hhMjU2KGNvbmZpZykuaGV4ZGlnZXN0KCkgIT0gc2VsZi5wcm9maWxlWydjb25maWdfc2hhMjU2J10gb3IKICAgICAgICAgICAgaGFzaGxpYi5zaGEyNTYobm90ZXMpLmhleGRpZ2VzdCgpICE9IHNlbGYucHJvZmlsZVsnbm90ZXNfc2hhMjU2J10gb3IKICAgICAgICAgICAgYicjIENPTkZJR19IVkNfRENDIGlzIG5vdCBzZXRcbicgbm90IGluIGNvbmZpZyBvcgogICAgICAgICAgICBzZWxmLnJlYWQoJ3N5cy9tb2R1bGUvc201NDQwX2ZlZG9yYS9wYXJhbWV0ZXJzL2RpcmVjdF9jaGFyZ2UnKSBub3QgaW4gKCdOJywgJzAnKSk6CiAgICAgICAgICAgIHJhaXNlIEd1YXJkRXJyb3IoJ3VucmVnaXN0ZXJlZCBib290L2tlcm5lbCBvciBkaXJlY3QtY2hhcmdlIHN0YXRlJykKICAgICAgICBpZiAoc2VsZi5yZWFkKCdzeXMvY2xhc3MvdHlwZWMvcG9ydDAvcG93ZXJfcm9sZScpICE9ICdbc2lua10nIG9yCiAgICAgICAgICAgIHNlbGYucmVhZCgnc3lzL2NsYXNzL3R5cGVjL3BvcnQwL2RhdGFfcm9sZScpICE9ICdbZGV2aWNlXScpOgogICAgICAgICAgICByYWlzZSBHdWFyZEVycm9yKCdub3QgdGhlIHJlZ2lzdGVyZWQgU2luay9EZXZpY2UgcGVyaXBoZXJhbCcpCgogICAgZGVmIGRlc2NyaWJlKHNlbGYpOgogICAgICAgIHJldHVybiBkaWN0KHZlbmRvcj0oc2VsZi5wYXRoIC8gJ2lkVmVuZG9yJykucmVhZF90ZXh0KCkuc3RyaXAoKSwKICAgICAgICAgICAgICAgICAgICBwcm9kdWN0PShzZWxmLnBhdGggLyAnaWRQcm9kdWN0JykucmVhZF90ZXh0KCkuc3RyaXAoKSwKICAgICAgICAgICAgICAgICAgICBmdW5jdGlvbnM9c29ydGVkKHAubmFtZSBmb3IgcCBpbiAoc2VsZi5wYXRoIC8gJ2Z1bmN0aW9ucycpLml0ZXJkaXIoKSksCiAgICAgICAgICAgICAgICAgICAgbGlua3M9c29ydGVkKChzdHIocC5yZWxhdGl2ZV90byhzZWxmLnBhdGgpKSwgc3RyKHAucmVzb2x2ZSgpKSkKICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgZm9yIHAgaW4gKHNlbGYucGF0aCAvICdjb25maWdzJykucmdsb2IoJyonKSBpZiBwLmlzX3N5bWxpbmsoKSkpCgogICAgZGVmIGNoZWNrX2xheW91dChzZWxmKToKICAgICAgICBkID0gc2VsZi5kZXNjcmliZSgpCiAgICAgICAgaWYgKGQgIT0gc2VsZi5maW5nZXJwcmludCBvciBpbnQoZFsndmVuZG9yJ10sIDE2KSAhPSAweDA1MjUgb3IKICAgICAgICAgICAgaW50KGRbJ3Byb2R1Y3QnXSwgMTYpICE9IDB4YTRhNyBvcgogICAgICAgICAgICBkWydmdW5jdGlvbnMnXSAhPSBbJ2Zmcy5hZGInLCAnbmNtLnVzYjAnXSBvcgogICAgICAgICAgICBsZW4oZFsnbGlua3MnXSkgIT0gMiBvcgogICAgICAgICAgICB7eFswXSBmb3IgeCBpbiBkWydsaW5rcyddfSAhPSB7J2NvbmZpZ3MvYy4xL2Zmcy5hZGInLCAnY29uZmlncy9jLjEvbmNtLnVzYjAnfSBvcgogICAgICAgICAgICB7eFsxXSBmb3IgeCBpbiBkWydsaW5rcyddfSAhPSB7c3RyKHNlbGYucGF0aCAvICdmdW5jdGlvbnMvZmZzLmFkYicpLAogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgc3RyKHNlbGYucGF0aCAvICdmdW5jdGlvbnMvbmNtLnVzYjAnKX0pOgogICAgICAgICAgICByYWlzZSBHdWFyZEVycm9yKCdzaGFyZWQgZ2FkZ2V0IGxheW91dCBjaGFuZ2VkJykKCiAgICBkZWYgc3RhdGUoc2VsZik6CiAgICAgICAgc2VsZi5pZGVudGl0eSgpCiAgICAgICAgb25saW5lID0gc2VsZi5yZWFkKCdzeXMvY2xhc3MvcG93ZXJfc3VwcGx5L3NtNTcxNC11c2Ivb25saW5lJykKICAgICAgICBpZiBvbmxpbmUgbm90IGluICgnMCcsICcxJyk6CiAgICAgICAgICAgIHJhaXNlIEd1YXJkRXJyb3IoJ2ludmFsaWQgVVNCIG9ubGluZSBvYnNlcnZhdGlvbicpCiAgICAgICAgcmV0dXJuIGNhYmxlX3N0YXRlKChzZWxmLnJvb3QgLyAnc3lzL2NsYXNzL3R5cGVjL3BvcnQwLXBhcnRuZXInKS5leGlzdHMoKSwgaW50KG9ubGluZSkpCgogICAgZGVmIHdyaXRlX2JpbmRpbmcoc2VsZiwgdmFsdWUpOgogICAgICAgICMgQSBzdG9wIHNpZ25hbCBiZXR3ZWVuIGEgc3VjY2Vzc2Z1bCBzeXNmcyB3cml0ZSBhbmQgb3VyIG93bmVyc2hpcAogICAgICAgICMgdXBkYXRlIG11c3Qgbm90IHN0cmFuZCB0aGUgc2hhcmVkIGdhZGdldC4gU0lHS0lMTCBjYW5ub3QgYmUgaGFuZGxlZDsKICAgICAgICAjIHNlcnZpY2UgYXV0by1yZXN0YXJ0IGlzIGRlbGliZXJhdGVseSBkaXNhYmxlZCBmb3IgdGhhdCB1bmtub3duIHN0YXRlLgogICAgICAgIHNpZ25hbHMgPSB7c2lnbmFsLlNJR1RFUk0sIHNpZ25hbC5TSUdJTlR9CiAgICAgICAgb2xkID0gc2lnbmFsLnB0aHJlYWRfc2lnbWFzayhzaWduYWwuU0lHX0JMT0NLLCBzaWduYWxzKQogICAgICAgIHRyeToKICAgICAgICAgICAgc2VsZi51ZGMud3JpdGVfdGV4dCh2YWx1ZSArICdcbicpCiAgICAgICAgICAgIHNlbGYub3duZWRfdW5ib3VuZCA9IFRydWUKICAgICAgICAgICAgaWYgc2VsZi51ZGMucmVhZF90ZXh0KCkuc3RyaXAoKSAhPSB2YWx1ZToKICAgICAgICAgICAgICAgIHJhaXNlIEd1YXJkRXJyb3IoJ2JpbmRpbmcgd3JpdGUvcmVhZGJhY2sgbWlzbWF0Y2gnKQogICAgICAgICAgICBzZWxmLm93bmVkX3VuYm91bmQgPSBub3QgYm9vbCh2YWx1ZSkKICAgICAgICBmaW5hbGx5OgogICAgICAgICAgICBzaWduYWwucHRocmVhZF9zaWdtYXNrKHNpZ25hbC5TSUdfU0VUTUFTSywgb2xkKQoKICAgIGRlZiBhcHBseShzZWxmLCBzdGFibGUpOgogICAgICAgIHNlbGYuaWRlbnRpdHkoKQogICAgICAgIHNlbGYuY2hlY2tfbGF5b3V0KCkKICAgICAgICBib3VuZCA9IHNlbGYudWRjLnJlYWRfdGV4dCgpLnN0cmlwKCkKICAgICAgICBleHBlY3RlZCA9ICcnIGlmIHNlbGYub3duZWRfdW5ib3VuZCBlbHNlICdhNjAwMDAwLnVzYicKICAgICAgICBpZiBib3VuZCAhPSBleHBlY3RlZDoKICAgICAgICAgICAgcmFpc2UgR3VhcmRFcnJvcignYW5vdGhlciBhY3RvciBjaGFuZ2VkIFVEQzsgcmVmdXNlIHRvIG92ZXJ3cml0ZScpCiAgICAgICAgIyBSZWNoZWNrIGNhYmxlIGltbWVkaWF0ZWx5IGJlZm9yZSB0aGUgd3JpdGUuIE5vIGRlbGF5ZWQgc3RhbGUgYWN0aW9uLgogICAgICAgIGlmIHN0YWJsZSBub3QgaW4gKCdhdHRhY2hlZCcsICdkZXRhY2hlZCcpIG9yIHNlbGYuc3RhdGUoKSAhPSBzdGFibGU6CiAgICAgICAgICAgIHJldHVybiBOb25lCiAgICAgICAgaWYgc3RhYmxlID09ICdkZXRhY2hlZCcgYW5kIG5vdCBzZWxmLm93bmVkX3VuYm91bmQ6CiAgICAgICAgICAgIHNlbGYud3JpdGVfYmluZGluZygnJykKICAgICAgICAgICAgcmV0dXJuICd1bmJpbmQnCiAgICAgICAgaWYgc3RhYmxlID09ICdhdHRhY2hlZCcgYW5kIHNlbGYub3duZWRfdW5ib3VuZDoKICAgICAgICAgICAgc2VsZi53cml0ZV9iaW5kaW5nKCdhNjAwMDAwLnVzYicpCiAgICAgICAgICAgIHJldHVybiAnYmluZCcKICAgICAgICByZXR1cm4gTm9uZQoKICAgIGRlZiByZXN0b3JlKHNlbGYpOgogICAgICAgIGlmIHNlbGYub3duZWRfdW5ib3VuZDoKICAgICAgICAgICAgc2VsZi5pZGVudGl0eSgpCiAgICAgICAgICAgIHNlbGYuY2hlY2tfbGF5b3V0KCkKICAgICAgICAgICAgYm91bmQgPSBzZWxmLnVkYy5yZWFkX3RleHQoKS5zdHJpcCgpCiAgICAgICAgICAgIGlmIGJvdW5kID09ICdhNjAwMDAwLnVzYic6CiAgICAgICAgICAgICAgICBzZWxmLm93bmVkX3VuYm91bmQgPSBGYWxzZQogICAgICAgICAgICAgICAgcmV0dXJuCiAgICAgICAgICAgIGlmIGJvdW5kOgogICAgICAgICAgICAgICAgcmFpc2UgR3VhcmRFcnJvcignb3duZWQgZW1wdHkgYmluZGluZyBjaGFuZ2VkOyByZWNvdmVyeSByZWZ1c2VkJykKICAgICAgICAgICAgc2VsZi53cml0ZV9iaW5kaW5nKCdhNjAwMDAwLnVzYicpCgoKZGVmIHJlbGV2YW50X3VldmVudChkYXRhLCBzZW5kZXIpOgogICAgaWYgc2VuZGVyWzBdICE9IDAgb3IgbGVuKGRhdGEpID49IDY1NTM2OgogICAgICAgIHJldHVybiBGYWxzZQogICAgZmllbGRzID0ge30KICAgIGZvciBwYXJ0IGluIGRhdGEuc3BsaXQoYidcMCcpWzE6XToKICAgICAgICBpZiBiJz0nIGluIHBhcnQ6CiAgICAgICAgICAgIGtleSwgdmFsdWUgPSBwYXJ0LnNwbGl0KGInPScsIDEpCiAgICAgICAgICAgIGlmIGtleSBpbiBmaWVsZHM6CiAgICAgICAgICAgICAgICByZXR1cm4gRmFsc2UKICAgICAgICAgICAgZmllbGRzW2tleV0gPSB2YWx1ZQogICAgcmV0dXJuIChmaWVsZHMuZ2V0KGInU1VCU1lTVEVNJykgPT0gYid0eXBlYycgb3IKICAgICAgICAgICAgKGZpZWxkcy5nZXQoYidTVUJTWVNURU0nKSA9PSBiJ3Bvd2VyX3N1cHBseScgYW5kCiAgICAgICAgICAgICBmaWVsZHMuZ2V0KGInREVWUEFUSCcsIGInJykuZW5kc3dpdGgoYicvc201NzE0LXVzYicpKSkKCgpkZWYgc2VydmUoZ2FkZ2V0LCBzb2NrLCBjbG9jaz10aW1lLm1vbm90b25pYyk6CiAgICBlZGdlcyA9IENhYmxlRWRnZXMoKQogICAgcGVuZGluZ19jaGVjayA9IGNsb2NrKCkgICMgSW5pdGlhbCBkZXRhY2hlZCBzdGFsZSBzdGF0ZSBpcyBhbHNvIHJlcGFpcmVkLgogICAgdHJ5OgogICAgICAgIHdoaWxlIFRydWU6CiAgICAgICAgICAgIG5vdyA9IGNsb2NrKCkKICAgICAgICAgICAgdGltZW91dCA9IE5vbmUgaWYgcGVuZGluZ19jaGVjayBpcyBOb25lIGVsc2UgbWF4KDAsIHBlbmRpbmdfY2hlY2sgLSBub3cpCiAgICAgICAgICAgIGlmIHNlbGVjdC5zZWxlY3QoW3NvY2tdLCBbXSwgW10sIHRpbWVvdXQpWzBdOgogICAgICAgICAgICAgICAgZGF0YSwgc2VuZGVyID0gc29jay5yZWN2ZnJvbSg2NTUzNikKICAgICAgICAgICAgICAgIGlmIHJlbGV2YW50X3VldmVudChkYXRhLCBzZW5kZXIpIGFuZCBwZW5kaW5nX2NoZWNrIGlzIE5vbmU6CiAgICAgICAgICAgICAgICAgICAgcGVuZGluZ19jaGVjayA9IGNsb2NrKCkgKyAwLjEKICAgICAgICAgICAgaWYgcGVuZGluZ19jaGVjayBpcyBub3QgTm9uZSBhbmQgY2xvY2soKSA+PSBwZW5kaW5nX2NoZWNrOgogICAgICAgICAgICAgICAgc3RhdGUgPSBnYWRnZXQuc3RhdGUoKQogICAgICAgICAgICAgICAgc3RhYmxlID0gZWRnZXMub2JzZXJ2ZShzdGF0ZSwgY2xvY2soKSkKICAgICAgICAgICAgICAgIGlmIHN0YWJsZSBpcyBub3QgTm9uZToKICAgICAgICAgICAgICAgICAgICBhY3Rpb24gPSBnYWRnZXQuYXBwbHkoc3RhYmxlKQogICAgICAgICAgICAgICAgICAgIGlmIGFjdGlvbjoKICAgICAgICAgICAgICAgICAgICAgICAgcHJpbnQoanNvbi5kdW1wcyhkaWN0KGJvb3RfaWQ9Z2FkZ2V0LmJvb3QsIGV2ZW50PWFjdGlvbiwKICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNhYmxlPXN0YWJsZSwgbW9ub3RvbmljPWNsb2NrKCkpKSwgZmx1c2g9VHJ1ZSkKICAgICAgICAgICAgICAgICAgICBwZW5kaW5nX2NoZWNrID0gTm9uZQogICAgICAgICAgICAgICAgZWxpZiBzdGF0ZSA9PSAndW5rbm93bic6CiAgICAgICAgICAgICAgICAgICAgIyBBd2FpdCBhIHJlYWwgbmV3IFR5cGUtQy9VU0IgZXZlbnQuIERvIG5vdCBwb2xsIHRoZSBJMkMKICAgICAgICAgICAgICAgICAgICAjIHN1cHBseSBvciByZXNldCBhIGxpdmUgbGluayB0aHJvdWdoIGEgUEQgdHJhbnNpZW50LgogICAgICAgICAgICAgICAgICAgIHBlbmRpbmdfY2hlY2sgPSBOb25lCiAgICAgICAgICAgICAgICBlbHNlOgogICAgICAgICAgICAgICAgICAgIHBlbmRpbmdfY2hlY2sgPSBjbG9jaygpICsgZWRnZXMuZGVib3VuY2UKICAgIGZpbmFsbHk6CiAgICAgICAgZ2FkZ2V0LnJlc3RvcmUoKQoKCmRlZiBtYWluKCk6CiAgICBhcCA9IGFyZ3BhcnNlLkFyZ3VtZW50UGFyc2VyKGRlc2NyaXB0aW9uPV9fZG9jX18pCiAgICBhcC5hZGRfYXJndW1lbnQoJy0tcHJvZmlsZScsIHR5cGU9UGF0aCwgcmVxdWlyZWQ9VHJ1ZSkKICAgIGFyZ3MgPSBhcC5wYXJzZV9hcmdzKCkKICAgIHByb2ZpbGUgPSBqc29uLmxvYWRzKGFyZ3MucHJvZmlsZS5yZWFkX3RleHQoKSkKICAgIHdpdGggUGF0aCgnL3J1bi9ndHM5LXVzYi10eXBlYy1saWZlY3ljbGUubG9jaycpLm9wZW4oJ3cnKSBhcyBsb2NrOgogICAgICAgIGZjbnRsLmZsb2NrKGxvY2ssIGZjbnRsLkxPQ0tfRVggfCBmY250bC5MT0NLX05CKQogICAgICAgIGdhZGdldCA9IEdhZGdldCgnLycsIHByb2ZpbGUpCiAgICAgICAgaWYgc3VicHJvY2Vzcy5ydW4oWydzeXN0ZW1jdGwnLCAnaXMtYWN0aXZlJywgJy0tcXVpZXQnLCAnZ3RzOS1hZGJkJ10sIHRpbWVvdXQ9NSkucmV0dXJuY29kZToKICAgICAgICAgICAgcmFpc2UgR3VhcmRFcnJvcignYWRiZCBub3QgcmVhZHk7IG5vIFVEQyBhY3Rpb24nKQogICAgICAgIGRlZiBzdG9wKHNpZ251bSwgZnJhbWUpOgogICAgICAgICAgICByYWlzZSBJbnRlcnJ1cHRlZEVycm9yKCdsaWZlY3ljbGUgc2VydmljZSBzdG9wcGVkJykKICAgICAgICBzaWduYWwuc2lnbmFsKHNpZ25hbC5TSUdURVJNLCBzdG9wKQogICAgICAgIHNpZ25hbC5zaWduYWwoc2lnbmFsLlNJR0lOVCwgc3RvcCkKICAgICAgICB3aXRoIHNvY2tldC5zb2NrZXQoc29ja2V0LkFGX05FVExJTkssIHNvY2tldC5TT0NLX0RHUkFNLCAxNSkgYXMgc29jazoKICAgICAgICAgICAgc29jay5iaW5kKCgwLCAxKSkKICAgICAgICAgICAgc2VydmUoZ2FkZ2V0LCBzb2NrKQoKCmlmIF9fbmFtZV9fID09ICdfX21haW5fXyc6CiAgICB0cnk6CiAgICAgICAgbWFpbigpCiAgICBleGNlcHQgSW50ZXJydXB0ZWRFcnJvcjoKICAgICAgICBwYXNzCg=='}, 'etc/gts9-usb-typec-profile.json': {'mode': 420, 'bytes': 269, 'sha256': '50df83ab2a01dac30049520a188673ab9e22327796ced3999610989fdf22d8fe', 'base64': 'ewogICJjb25maWdfc2hhMjU2IjogIjUxYmE2YTljMmJhM2QxZDVjNmViZDkyODhmYjZkMDQ3NjVlOGMyMDBjZTU4ZmQ5MzI5NzVmMTE1ODhjNjZjNmEiLAogICJtYWNoaW5lX2lkIjogIjNjMmExYjhmMmQ2MjRkYjRiNWZmZGM4MzYwNTBmY2Y2IiwKICAibm90ZXNfc2hhMjU2IjogIjAzYzljNDZlMjFmY2M1ODdkYmZkNWEzMzdmNWM5Y2Y2OGQ5Y2JmYTYwNWUwNzRkNWE3NGQyZjlhODA3M2RjOTUiLAogICJyZWxlYXNlIjogIjcuMi4wLXJjMy1ndHM5d2lmaS1kaXJ0eSIKfQo='}, 'etc/systemd/system/gts9-usb-typec-lifecycle.service': {'mode': 420, 'bytes': 420, 'sha256': '8ff7d6a4a35b3607b210cae45ba9c28fe00c1f7866d6589e3d12353408b3d75f', 'base64': 'W1VuaXRdCkRlc2NyaXB0aW9uPUdUUzkgZml4ZWQtcGVyaXBoZXJhbCBVU0IgVHlwZS1DIGxpZmVjeWNsZQpBZnRlcj1ndHM5LXVzYi1hY20uc2VydmljZSBndHM5LWFkYmQuc2VydmljZQpXYW50cz1ndHM5LXVzYi1hY20uc2VydmljZSBndHM5LWFkYmQuc2VydmljZQpDb25kaXRpb25QYXRoRXhpc3RzPS9ldGMvZ3RzOS11c2ItdHlwZWMtcHJvZmlsZS5qc29uCgpbU2VydmljZV0KVHlwZT1zaW1wbGUKRXhlY1N0YXJ0PS91c3IvYmluL3B5dGhvbjMgL3Vzci9sb2NhbC9saWJleGVjL2d0czktdXNiLXR5cGVjLWxpZmVjeWNsZSAtLXByb2ZpbGUgL2V0Yy9ndHM5LXVzYi10eXBlYy1wcm9maWxlLmpzb24KUmVzdGFydD1ubwpUaW1lb3V0U3RvcFNlYz01cwpVTWFzaz0wMDc3CgpbSW5zdGFsbF0KV2FudGVkQnk9bXVsdGktdXNlci50YXJnZXQK'}}
profile={'config_sha256': '51ba6a9c2ba3d1d5c6ebd9288fb6d04765e8c200ce58fd932975f11588c66c6a', 'machine_id': '3c2a1b8f2d624db4b5ffdc836050fcf6', 'notes_sha256': '03c9c46e21fcc587dbfd5a337f5c9cf68d9cbfa605e074d5a74d2f9a8073dc95', 'release': '7.2.0-rc3-gts9wifi-dirty'}
boot='78ec1906-4713-4837-9acc-fe245647d7cf'
ns={'__name__':'passive_helper'}
exec('#!/usr/bin/env python3\n"""Bridge verified Type-C cable edges to the existing fixed-peripheral gadget.\n\nNever change descriptors, roles, adbd, PD policy or charger registers. Deployment\nrequires an independently registered profile; importing this module is passive.\n"""\nimport argparse\nimport fcntl\nimport gzip\nimport hashlib\nimport json\nimport select\nimport signal\nimport socket\nimport subprocess\nimport time\nfrom pathlib import Path\n\n\nclass GuardError(RuntimeError):\n    pass\n\n\ndef cable_state(partner, online):\n    # A hard reset may temporarily remove VBUS while the partner remains.\n    if partner is False and online == 0:\n        return \'detached\'\n    if partner is True and online == 1:\n        return \'attached\'\n    return \'unknown\'\n\n\nclass CableEdges:\n    def __init__(self, debounce=1.0):\n        self.debounce = debounce\n        self.pending = None\n        self.since = None\n\n    def observe(self, state, now):\n        if state == \'unknown\':\n            self.pending = self.since = None\n            return None\n        if state != self.pending:\n            self.pending, self.since = state, now\n            return None\n        return state if now - self.since >= self.debounce else None\n\n\nclass Gadget:\n    def __init__(self, root, profile):\n        self.root = Path(root)\n        self.profile = profile\n        self.path = self.root / \'sys/kernel/config/usb_gadget/gts9\'\n        self.udc = self.path / \'UDC\'\n        self.owned_unbound = False\n        self.boot = self.read(\'proc/sys/kernel/random/boot_id\')\n        self.identity()\n        self.fingerprint = self.describe()\n        self.check_layout()\n        if self.udc.read_text().strip() != \'a600000.usb\':\n            raise GuardError(\'initial binding unknown; do not adopt an empty UDC\')\n\n    def read(self, name):\n        return (self.root / name).read_text().strip()\n\n    def identity(self):\n        config = gzip.decompress((self.root / \'proc/config.gz\').read_bytes())\n        notes = (self.root / \'sys/kernel/notes\').read_bytes()\n        if (self.read(\'etc/machine-id\') != self.profile[\'machine_id\'] or\n            self.read(\'proc/sys/kernel/random/boot_id\') != self.boot or\n            self.read(\'proc/sys/kernel/osrelease\') != self.profile[\'release\'] or\n            hashlib.sha256(config).hexdigest() != self.profile[\'config_sha256\'] or\n            hashlib.sha256(notes).hexdigest() != self.profile[\'notes_sha256\'] or\n            b\'# CONFIG_HVC_DCC is not set\\n\' not in config or\n            self.read(\'sys/module/sm5440_fedora/parameters/direct_charge\') not in (\'N\', \'0\')):\n            raise GuardError(\'unregistered boot/kernel or direct-charge state\')\n        if (self.read(\'sys/class/typec/port0/power_role\') != \'[sink]\' or\n            self.read(\'sys/class/typec/port0/data_role\') != \'[device]\'):\n            raise GuardError(\'not the registered Sink/Device peripheral\')\n\n    def describe(self):\n        return dict(vendor=(self.path / \'idVendor\').read_text().strip(),\n                    product=(self.path / \'idProduct\').read_text().strip(),\n                    functions=sorted(p.name for p in (self.path / \'functions\').iterdir()),\n                    links=sorted((str(p.relative_to(self.path)), str(p.resolve()))\n                                 for p in (self.path / \'configs\').rglob(\'*\') if p.is_symlink()))\n\n    def check_layout(self):\n        d = self.describe()\n        if (d != self.fingerprint or int(d[\'vendor\'], 16) != 0x0525 or\n            int(d[\'product\'], 16) != 0xa4a7 or\n            d[\'functions\'] != [\'ffs.adb\', \'ncm.usb0\'] or\n            len(d[\'links\']) != 2 or\n            {x[0] for x in d[\'links\']} != {\'configs/c.1/ffs.adb\', \'configs/c.1/ncm.usb0\'} or\n            {x[1] for x in d[\'links\']} != {str(self.path / \'functions/ffs.adb\'),\n                                        str(self.path / \'functions/ncm.usb0\')}):\n            raise GuardError(\'shared gadget layout changed\')\n\n    def state(self):\n        self.identity()\n        online = self.read(\'sys/class/power_supply/sm5714-usb/online\')\n        if online not in (\'0\', \'1\'):\n            raise GuardError(\'invalid USB online observation\')\n        return cable_state((self.root / \'sys/class/typec/port0-partner\').exists(), int(online))\n\n    def write_binding(self, value):\n        # A stop signal between a successful sysfs write and our ownership\n        # update must not strand the shared gadget. SIGKILL cannot be handled;\n        # service auto-restart is deliberately disabled for that unknown state.\n        signals = {signal.SIGTERM, signal.SIGINT}\n        old = signal.pthread_sigmask(signal.SIG_BLOCK, signals)\n        try:\n            self.udc.write_text(value + \'\\n\')\n            self.owned_unbound = True\n            if self.udc.read_text().strip() != value:\n                raise GuardError(\'binding write/readback mismatch\')\n            self.owned_unbound = not bool(value)\n        finally:\n            signal.pthread_sigmask(signal.SIG_SETMASK, old)\n\n    def apply(self, stable):\n        self.identity()\n        self.check_layout()\n        bound = self.udc.read_text().strip()\n        expected = \'\' if self.owned_unbound else \'a600000.usb\'\n        if bound != expected:\n            raise GuardError(\'another actor changed UDC; refuse to overwrite\')\n        # Recheck cable immediately before the write. No delayed stale action.\n        if stable not in (\'attached\', \'detached\') or self.state() != stable:\n            return None\n        if stable == \'detached\' and not self.owned_unbound:\n            self.write_binding(\'\')\n            return \'unbind\'\n        if stable == \'attached\' and self.owned_unbound:\n            self.write_binding(\'a600000.usb\')\n            return \'bind\'\n        return None\n\n    def restore(self):\n        if self.owned_unbound:\n            self.identity()\n            self.check_layout()\n            bound = self.udc.read_text().strip()\n            if bound == \'a600000.usb\':\n                self.owned_unbound = False\n                return\n            if bound:\n                raise GuardError(\'owned empty binding changed; recovery refused\')\n            self.write_binding(\'a600000.usb\')\n\n\ndef relevant_uevent(data, sender):\n    if sender[0] != 0 or len(data) >= 65536:\n        return False\n    fields = {}\n    for part in data.split(b\'\\0\')[1:]:\n        if b\'=\' in part:\n            key, value = part.split(b\'=\', 1)\n            if key in fields:\n                return False\n            fields[key] = value\n    return (fields.get(b\'SUBSYSTEM\') == b\'typec\' or\n            (fields.get(b\'SUBSYSTEM\') == b\'power_supply\' and\n             fields.get(b\'DEVPATH\', b\'\').endswith(b\'/sm5714-usb\')))\n\n\ndef serve(gadget, sock, clock=time.monotonic):\n    edges = CableEdges()\n    pending_check = clock()  # Initial detached stale state is also repaired.\n    try:\n        while True:\n            now = clock()\n            timeout = None if pending_check is None else max(0, pending_check - now)\n            if select.select([sock], [], [], timeout)[0]:\n                data, sender = sock.recvfrom(65536)\n                if relevant_uevent(data, sender) and pending_check is None:\n                    pending_check = clock() + 0.1\n            if pending_check is not None and clock() >= pending_check:\n                state = gadget.state()\n                stable = edges.observe(state, clock())\n                if stable is not None:\n                    action = gadget.apply(stable)\n                    if action:\n                        print(json.dumps(dict(boot_id=gadget.boot, event=action,\n                                              cable=stable, monotonic=clock())), flush=True)\n                    pending_check = None\n                elif state == \'unknown\':\n                    # Await a real new Type-C/USB event. Do not poll the I2C\n                    # supply or reset a live link through a PD transient.\n                    pending_check = None\n                else:\n                    pending_check = clock() + edges.debounce\n    finally:\n        gadget.restore()\n\n\ndef main():\n    ap = argparse.ArgumentParser(description=__doc__)\n    ap.add_argument(\'--profile\', type=Path, required=True)\n    args = ap.parse_args()\n    profile = json.loads(args.profile.read_text())\n    with Path(\'/run/gts9-usb-typec-lifecycle.lock\').open(\'w\') as lock:\n        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)\n        gadget = Gadget(\'/\', profile)\n        if subprocess.run([\'systemctl\', \'is-active\', \'--quiet\', \'gts9-adbd\'], timeout=5).returncode:\n            raise GuardError(\'adbd not ready; no UDC action\')\n        def stop(signum, frame):\n            raise InterruptedError(\'lifecycle service stopped\')\n        signal.signal(signal.SIGTERM, stop)\n        signal.signal(signal.SIGINT, stop)\n        with socket.socket(socket.AF_NETLINK, socket.SOCK_DGRAM, 15) as sock:\n            sock.bind((0, 1))\n            serve(gadget, sock)\n\n\nif __name__ == \'__main__\':\n    try:\n        main()\n    except InterruptedError:\n        pass\n',ns)
g=ns['Gadget']('/',profile)
assert g.boot==boot and g.state()=='detached'
print(json.dumps(install('/',rows,boot)))
activate(rows,profile,boot)
