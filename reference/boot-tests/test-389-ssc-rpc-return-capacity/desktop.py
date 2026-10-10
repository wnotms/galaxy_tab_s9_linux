#!/usr/bin/env python3
"""Test389 offline desktop overlay; no service start or kernel operation."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile

MACHINE = '3c2a1b8f2d624db4b5ffdc836050fcf6'
STATE = 'var/lib/gts9-test389/desktop.json'
BACKUPS = 'var/lib/gts9-test389/desktop-backups'
TEXT = 'var/lib/gts9-test389/text-scope'
ALLOWED = {'var/lib/gts9-test389/text-scope', 'usr/local/lib/gts9-test389/glink_trace.py', 'etc/systemd/system/gts9-glink-test389.service', 'etc/systemd/system/hexagonrpcd-adsp-rootpd.service.d/91-gts9-test389.conf', 'etc/systemd/system/gdm.service.d/91-gts9-test389.conf', 'etc/systemd/system/hexagonrpcd-adsp-sensorspd.service.d/91-gts9-test389.conf', 'usr/local/lib/gts9-test389/hexagonrpcd', 'etc/systemd/system/multi-user.target.d/91-gts9-test389.conf'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def target(root, name):
    parts = PurePosixPath(name)
    if parts.is_absolute() or '..' in parts.parts or str(parts) != name:
        raise ValueError('unsafe overlay path')
    path = root / name
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('overlay path escapes root')
    return path


def atomic(path, data, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.gts9-test389-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def machine(root):
    if (root / 'etc/machine-id').read_text().strip() != MACHINE:
        raise ValueError('wrong Debian root')


def install(root, incoming, manifest):
    root = root.resolve(); machine(root)
    ledger = target(root, STATE)
    if ledger.exists() or target(root, BACKUPS).exists():
        raise ValueError('overlay already registered; one install only')
    if set(manifest) != ALLOWED:
        raise ValueError('overlay file set')
    rows = {}; data = {}; missing_dirs = set()
    for name, row in manifest.items():
        p = target(root, name)
        filename = row['incoming']
        if Path(filename).name != filename or filename in ('.', '..'):
            raise ValueError('unsafe incoming filename')
        source = incoming / filename
        if source.is_symlink() or not source.is_file():
            raise ValueError('invalid incoming overlay')
        data[name] = source.read_bytes()
        if digest(data[name]) != row['sha256'] or row['mode'] not in (0o644, 0o755):
            raise ValueError('overlay content/mode')
        expected = row['original_sha256']
        if p.exists():
            if not p.is_file() or expected is None or digest(p.read_bytes()) != expected:
                raise ValueError('different original overlay: ' + name)
            stat = p.stat()
            original = dict(sha256=expected, mode=stat.st_mode & 0o777,
                            uid=stat.st_uid, gid=stat.st_gid, mtime_ns=stat.st_mtime_ns)
        elif expected is not None:
            raise ValueError('required original absent: ' + name)
        else:
            original = None
        rows[name] = dict(sha256=row['sha256'], original=original)
        parent = p.parent
        while parent != root and not parent.exists():
            missing_dirs.add(str(parent.relative_to(root))); parent = parent.parent
    state = dict(schema=1, machine_id=MACHINE, files=rows,
                 created_dirs=sorted(missing_dirs), phase='copy-started')
    atomic(ledger, (json.dumps(state, indent=2) + '\n').encode())
    for index, name in enumerate(sorted(rows)):
        p = target(root, name); original = rows[name]['original']
        if original:
            atomic(target(root, BACKUPS + '/' + str(index)), p.read_bytes())
        atomic(p, data[name], manifest[name]['mode'])
    for name, row in rows.items():
        if digest(target(root, name).read_bytes()) != row['sha256']:
            raise ValueError('overlay readback')
    state['phase'] = 'copied-not-started'
    atomic(ledger, (json.dumps(state, indent=2) + '\n').encode())
    return dict(verdict='DESKTOP_OVERLAY_COPIED_NOT_STARTED', files=len(rows))


def restore(root):
    root = root.resolve(); machine(root)
    ledger = target(root, STATE)
    if not ledger.exists():
        return dict(verdict='NO_DESKTOP_LEDGER_NO_MUTATION')
    state = json.loads(ledger.read_text())
    if state.get('schema') != 1 or state.get('machine_id') != MACHINE or set(state['files']) != ALLOWED:
        raise ValueError('unqualified desktop ledger')
    # Check the entire transaction before the first removal/replacement.
    actions = []
    for index, (name, row) in enumerate(sorted(state['files'].items())):
        p = target(root, name); original = row['original']
        observed = digest(p.read_bytes()) if p.exists() and p.is_file() else None
        backup = target(root, BACKUPS + '/' + str(index))
        if original:
            if observed == original['sha256']:
                continue  # Also handles partial install before backup creation.
            if observed != row['sha256'] or not backup.is_file() or digest(backup.read_bytes()) != original['sha256']:
                raise ValueError('unknown current or corrupt original overlay: ' + name)
            actions.append((p, original, backup))
        elif observed is not None:
            if observed != row['sha256']:
                raise ValueError('owned overlay changed: ' + name)
            actions.append((p, None, None))
        elif p.exists():
            raise ValueError('owned path not regular: ' + name)
    allowed_dirs = {str(parent) for name in ALLOWED for parent in PurePosixPath(name).parents
                    if str(parent) != '.'}
    if any(name not in allowed_dirs for name in state['created_dirs']):
        raise ValueError('unqualified created directory')
    for name in state['created_dirs']:
        target(root, name)
    backup_dir = target(root, BACKUPS)
    if backup_dir.exists():
        expected = {str(i) for i, (_, row) in enumerate(sorted(state['files'].items())) if row['original']}
        if any(not x.is_file() or x.is_symlink() or x.name not in expected for x in backup_dir.iterdir()):
            raise ValueError('unknown desktop backup file')
    for p, original, backup in actions:
        if original:
            atomic(p, backup.read_bytes(), original['mode'])
            os.chown(p, original['uid'], original['gid'])
            os.utime(p, ns=(original['mtime_ns'], original['mtime_ns']))
        else:
            p.unlink()
    for name, row in state['files'].items():
        p = target(root, name)
        if row['original']:
            if not p.is_file() or digest(p.read_bytes()) != row['original']['sha256']:
                raise ValueError('original overlay readback')
        elif p.exists():
            raise ValueError('owned overlay not removed')
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    for name in sorted(state['created_dirs'], key=lambda x: len(PurePosixPath(x).parts), reverse=True):
        p = target(root, name)
        if p.exists():
            try: p.rmdir()
            except OSError: pass
    ledger.unlink()
    return dict(verdict='EXACT_DESKTOP_FILES_RESTORED', services_started=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('install', 'restore'))
    parser.add_argument('--root', type=Path, default=Path('/'))
    parser.add_argument('--incoming', type=Path)
    parser.add_argument('--manifest', type=Path)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise ValueError('offline root operation required')
    result = install(args.root, args.incoming, json.loads(args.manifest.read_text())) if args.mode == 'install' else restore(args.root)
    print(json.dumps(result, indent=2))
