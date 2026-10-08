#!/usr/bin/env python3
"""Copy only registered stock assets into an offline Debian root; no activation."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile

MACHINE = '3c2a1b8f2d624db4b5ffdc836050fcf6'
PREFIX = 'usr/share/qcom/sm8550/Samsung/gts9wifi'
FW = 'usr/lib/firmware/qcom/sm8550/'
STATE = 'var/lib/gts9-test364/assets.json'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def target(root, name):
    parts = PurePosixPath(name)
    if parts.is_absolute() or not parts.parts or '..' in parts.parts or str(parts) != name:
        raise ValueError('unsafe asset path')
    p = root / name
    if not p.resolve().is_relative_to(root.resolve()) or p.is_symlink():
        raise ValueError('asset path escapes root or is a symlink')
    return p


def atomic(path, data, mode=0o644, mtime=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.gts9-test364-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        if mtime is not None:
            os.utime(name, (mtime, mtime))
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def install(root, archive, expected_sha, manifest):
    root = root.resolve()
    if (root / 'etc/machine-id').read_text().strip() != MACHINE:
        raise ValueError('wrong Debian root')
    ledger = target(root, STATE)
    if ledger.exists() or target(root, PREFIX).exists():
        raise ValueError('prior state/isolated registry already exists; no overwrite')
    if archive.is_symlink() or digest(archive.read_bytes()) != expected_sha:
        raise ValueError('archive identity')
    rows = {}
    with tarfile.open(archive) as tar:
        for member in tar:
            name = member.name
            if not member.isfile() or name in rows:
                raise ValueError('duplicate or nonregular asset')
            if not (name.startswith(FW) or name.startswith(PREFIX + '/')):
                raise ValueError('asset outside registered prefix')
            path = target(root, name)
            data = tar.extractfile(member).read()
            expected = manifest.get(name)
            if expected is None or len(data) != expected['bytes'] or digest(data) != expected['sha256'] or member.mtime != expected['mtime']:
                raise ValueError('asset content/mtime mismatch')
            if path.exists() and (not path.is_file() or path.read_bytes() != data or int(path.stat().st_mtime) != member.mtime):
                raise ValueError('refusing existing different asset: ' + name)
            rows[name] = (data, member.mtime, not path.exists())
    if set(rows) != set(manifest):
        raise ValueError('asset set mismatch')
    # Record ownership before the first copy. Partial installation is restorable.
    missing_dirs = set()
    for name in rows:
        parent = target(root, name).parent
        while parent != root and not parent.exists():
            missing_dirs.add(str(parent.relative_to(root)))
            parent = parent.parent
    state = dict(schema=1, machine_id=MACHINE, prefix_owned=True,
                 archive_sha256=expected_sha, phase='copy-started',
                 files={n: {'created': v[2], 'sha256': digest(v[0])} for n, v in rows.items()},
                 created_dirs=sorted(missing_dirs))
    atomic(ledger, (json.dumps(state, indent=2) + '\n').encode(), 0o600)
    for name, (data, mtime, created) in rows.items():
        if created:
            atomic(target(root, name), data, mtime=mtime)
    for name, (data, mtime, _) in rows.items():
        p = target(root, name)
        if digest(p.read_bytes()) != digest(data) or int(p.stat().st_mtime) != mtime:
            raise ValueError('copied asset content/mtime mismatch')
    state['phase'] = 'copied-not-started'
    atomic(ledger, (json.dumps(state, indent=2) + '\n').encode(), 0o600)
    return dict(verdict='EXACT_ASSETS_COPIED_NOT_STARTED', files=len(rows),
                owned_files=sum(v[2] for v in rows.values()), services_started=False,
                remoteproc_started=False, persist_modified=False)


def restore(root):
    root = root.resolve()
    if (root / 'etc/machine-id').read_text().strip() != MACHINE:
        raise ValueError('wrong Debian root')
    ledger = target(root, STATE)
    state = json.loads(ledger.read_text())
    if state.get('schema') != 1 or state.get('machine_id') != MACHINE or state.get('prefix_owned') is not True:
        raise ValueError('unqualified asset ledger')
    prefix = target(root, PREFIX)
    # Validate every ledger path before the first removal. An edited ledger
    # must not turn cleanup into an operation outside the owned trees.
    allowed_dirs = set()
    for name in state['files']:
        parent = PurePosixPath(name).parent
        while str(parent) != '.':
            allowed_dirs.add(str(parent))
            parent = parent.parent
    if any(n not in allowed_dirs for n in state['created_dirs']):
        raise ValueError('unqualified created directory')
    for name in state['created_dirs']:
        target(root, name)
    for name, row in state['files'].items():
        if not (name.startswith(FW) or name.startswith(PREFIX + '/')):
            raise ValueError('unqualified restore prefix')
        p = target(root, name)
        if name.startswith(FW) and row['created'] and p.exists() and digest(p.read_bytes()) != row['sha256']:
            raise ValueError('owned firmware changed; inspect before removal')
    # Registry modifications are confined to this newly created copy; original
    # Android persist is never part of this ledger. rmtree does not follow links.
    if prefix.exists():
        shutil.rmtree(prefix)
    for name, row in state['files'].items():
        if name.startswith(FW) and row['created']:
            target(root, name).unlink(missing_ok=True)
    for name in sorted(state['created_dirs'], key=lambda n: len(PurePosixPath(n).parts), reverse=True):
        p = target(root, name)
        if p.exists():
            try:
                p.rmdir()
            except OSError:
                pass  # Leave directories containing any pre-existing files.
    ledger.unlink()
    return dict(verdict='OWNED_ASSETS_REMOVED', original_firmware_preserved=True,
                services_started=False, remoteproc_started=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('install', 'restore'))
    parser.add_argument('--root', type=Path, default=Path('/'))
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--sha256')
    parser.add_argument('--manifest', type=Path)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise ValueError('offline device operation requires root')
    if args.mode == 'install':
        result = install(args.root, args.archive, args.sha256, json.loads(args.manifest.read_text()))
    else:
        result = restore(args.root)
    print(json.dumps(result, indent=2))
