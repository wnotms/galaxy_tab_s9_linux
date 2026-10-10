#!/usr/bin/env python3
"""Recovery-only exact firmware swap; no remoteproc, services or partitions.

Called by a separately registered host flow inside the offline Debian chroot,
with a temporary read-only recovery /proc bind. The existing assets installer
continues to refuse different pre-existing firmware. All 52 originals and their
metadata are durably backed up before the first firmware replacement.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile
import tempfile
from uuid import UUID

MACHINE = '3c2a1b8f2d624db4b5ffdc836050fcf6'
RECOVERY = '5.15.94-Foldiby-+'
BASE_SHA = '6abc10ecdb82c6abe175461ae483670be0c82c8e038cb9acbf5eb5f8ae9231e5'
CANDIDATE_SHA = 'd647dcdf5ecc010080dbd057cec2c9cc66368d9e241cc3883a532e3f648177b3'
FW = 'usr/lib/firmware/qcom/sm8550/'
PATTERN = re.compile(re.escape(FW) + r'adsp(?:_dtb)?\.(?:mdt|b[0-9]{2})\Z')
STATE = 'var/lib/gts9-fedora-adsp-transaction'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def target(root, name):
    p = PurePosixPath(name)
    if not p.parts or p.is_absolute() or '..' in p.parts or str(p) != name:
        raise ValueError('unsafe transaction path')
    path = root / name
    for part in (path, *path.parents):
        if part == root:
            break
        if part.is_symlink():
            raise ValueError('symlink transaction path')
    return path


def recovery_guard(root, proc):
    # uname reports the actual executing kernel even inside chroot. A supplied
    # text marker alone cannot authorize a write on the mainline/GNOME boot.
    if os.geteuid() != 0 or os.uname().release != RECOVERY:
        raise ValueError('requires actual qualified root TWRP kernel')
    if target(root, 'etc/machine-id').read_text().strip() != MACHINE:
        raise ValueError('wrong offline Debian root')
    if ((proc / 'sys/kernel/osrelease').read_text().strip() != RECOVERY
            or int((proc / 'self/stat').read_text().split()[0]) != os.getpid()):
        raise ValueError('missing actual recovery proc bind')
    return str(UUID((proc / 'sys/kernel/random/boot_id').read_text().strip()))


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic(path, data, *, mode=0o600, mtime_ns=None, uid=0, gid=0):
    # Parents are pre-created/validated by the transaction; no implicit mkdir.
    fd, temporary = tempfile.mkstemp(prefix='.adsp-transaction-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fchown(stream.fileno(), uid, gid)
            os.fchmod(stream.fileno(), mode)
            if mtime_ns is not None:
                os.utime(stream.fileno(), ns=(mtime_ns, mtime_ns))
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        sync_dir(path.parent)
    finally:
        Path(temporary).unlink(missing_ok=True)


def save(folder, state):
    atomic(folder / 'ledger.json', (json.dumps(state, indent=2, sort_keys=True)+'\n').encode())


def snapshot(path):
    st = path.lstat()
    if (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_size > 64*1024**2
            or st.st_uid != 0 or st.st_gid != 0):
        raise ValueError('nonregular/hardlinked/nonroot firmware')
    raw = path.read_bytes()
    return dict(sha256=digest(raw), bytes=len(raw), mode=stat.S_IMODE(st.st_mode),
                mtime_ns=st.st_mtime_ns, uid=st.st_uid, gid=st.st_gid)


def archive_files(path, sha):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 64*1024**2:
        raise ValueError('unsafe archive')
    if digest(path.read_bytes()) != sha:
        raise ValueError('archive identity')
    result, seen, expanded = {}, set(), 0
    with tarfile.open(path) as archive:
        for m in archive:
            name = m.name
            p = PurePosixPath(name)
            if (str(p) != name or p.is_absolute() or '..' in p.parts or name in seen
                    or not m.isfile() or m.uid != 0 or m.gid != 0
                    or m.mode not in (0o600, 0o644) or not 0 <= m.size <= 64*1024**2
                    or not isinstance(m.mtime, int) or m.mtime < 0):
                raise ValueError('unsafe archive member')
            seen.add(name)
            expanded += m.size
            if len(seen) > 8192 or expanded > 256*1024**2:
                raise ValueError('archive size bound')
            if PATTERN.fullmatch(name):
                if m.mode != 0o644:
                    raise ValueError('unexpected firmware mode')
                raw = archive.extractfile(m).read()
                if len(raw) != m.size:
                    raise ValueError('short firmware member')
                result[name] = dict(data=raw, sha256=digest(raw), bytes=len(raw),
                                    mode=m.mode, mtime_ns=m.mtime*10**9, uid=0, gid=0)
    if len(result) != 52:
        raise ValueError('complete 52-file pair required')
    return result


def file_state(path):
    return snapshot(path) if path.exists() else None


def install(root, base_path, candidate_path, proc, original_presence='present'):
    root = root.resolve()
    boot = recovery_guard(root, proc)
    base = archive_files(base_path, BASE_SHA)
    candidate = archive_files(candidate_path, CANDIDATE_SHA)
    if set(base) != set(candidate):
        raise ValueError('firmware set changed')
    if original_presence not in ('present', 'absent'):
        raise ValueError('unregistered original presence')
    folder = target(root, STATE)
    if folder.exists():
        raise ValueError('prior transaction exists; inspect/restore, never replay')
    rows = {}
    # Validate the whole installed pair before creating a backup or any write.
    for name in sorted(base):
        before = file_state(target(root, name))
        if original_presence == 'absent' and before is not None:
            raise ValueError('registered absent original unexpectedly exists')
        if original_presence == 'present' and (before is None or
                any(before[k] != base[name][k] for k in ('sha256', 'bytes', 'mode', 'uid', 'gid'))):
            raise ValueError('installed original differs: '+name)
        rows[name] = dict(before=before,
                          after={k: v for k, v in candidate[name].items() if k != 'data'})
    firmware_dir = target(root, FW.rstrip('/'))
    created_firmware_dir = not firmware_dir.exists()
    if not firmware_dir.parent.is_dir():
        raise ValueError('firmware parent missing; no broad directory creation')
    folder.parent.mkdir(parents=True, exist_ok=True)
    folder.mkdir(mode=0o700)
    sync_dir(folder.parent)
    state = dict(schema=2, phase='backing-up', machine_id=MACHINE, recovery_boot_id=boot,
                 base_archive_sha256=BASE_SHA, candidate_archive_sha256=CANDIDATE_SHA,
                 files=rows, written=[], pending=None, original_presence=original_presence,
                 created_firmware_dir=created_firmware_dir)
    save(folder, state)
    for name, row in rows.items():
        if row['before'] is None:
            continue
        raw = target(root, name).read_bytes()
        if digest(raw) != row['before']['sha256']:
            raise ValueError('original changed during backup')
        atomic(folder / Path(name).name, raw)
    for name, row in rows.items():
        if ((row['before'] is not None and
                digest((folder / Path(name).name).read_bytes()) != row['before']['sha256'])
                or file_state(target(root, name)) != row['before']):
            raise ValueError('backup/original identity')
    state['phase'] = 'installing'
    save(folder, state)  # Durable full backup and write intent precede replacement.
    if created_firmware_dir:
        firmware_dir.mkdir(mode=0o755)
        sync_dir(firmware_dir.parent)
    for name, row in rows.items():
        state['pending'] = name
        save(folder, state)
        atomic(target(root, name), candidate[name]['data'],
               **{k: row['after'][k] for k in ('mode', 'mtime_ns', 'uid', 'gid')})
        if snapshot(target(root, name)) != row['after']:
            raise ValueError('firmware write boundary')
        state['written'].append(name)
        state['pending'] = None
        save(folder, state)
    state['phase'] = 'installed'
    save(folder, state)
    return dict(verdict='COMPLETE_FEDORA_PAIR_INSTALLED_OFFLINE', firmware_files=52,
                changed_bytes_files=sum(base[n]['sha256'] != r['after']['sha256'] for n,r in rows.items()),
                original_presence=original_presence,
                recovery_boot_id=boot, services_started=False, remoteproc_started=False)


def restore(root, base_path, candidate_path, proc, original_presence='present'):
    root = root.resolve()
    boot = recovery_guard(root, proc)
    base = archive_files(base_path, BASE_SHA)
    candidate = archive_files(candidate_path, CANDIDATE_SHA)
    folder = target(root, STATE)
    ledger = target(root, STATE+'/ledger.json')
    state = json.loads(ledger.read_text())
    if (state.get('schema') != 2 or state.get('machine_id') != MACHINE
            or state.get('base_archive_sha256') != BASE_SHA
            or state.get('candidate_archive_sha256') != CANDIDATE_SHA
            or set(state.get('files', {})) != set(base) or set(base) != set(candidate)
            or original_presence not in ('present', 'absent')
            or state.get('original_presence') != original_presence
            or type(state.get('created_firmware_dir')) is not bool
            or (original_presence == 'present' and state['created_firmware_dir'])
            or state.get('phase') not in ('backing-up', 'installing', 'installed', 'restoring', 'restored')):
        raise ValueError('unqualified transaction ledger')
    UUID(state['recovery_boot_id'])
    # Validate every row, every current file and every required backup BEFORE
    # restoring any file. Unknown content stops instead of overwriting evidence.
    for name, row in state['files'].items():
        before, after = row['before'], row['after']
        before_valid = (before is None if original_presence == 'absent' else
                        isinstance(before, dict) and set(before) == set(candidate[name])-{'data'}
                        and all(before[k] == base[name][k] for k in ('sha256', 'bytes', 'mode', 'uid', 'gid'))
                        and type(before['mtime_ns']) is int and before['mtime_ns'] >= 0)
        if (not before_valid or after != {k: v for k, v in candidate[name].items() if k != 'data'}):
            raise ValueError('unqualified firmware ledger row')
        current = file_state(target(root, name))
        allowed = (before,) if state['phase'] in ('backing-up', 'restored') else (before, after)
        if current not in allowed:
            raise ValueError('unknown current firmware; retain evidence: '+name)
        if before is not None and state['phase'] not in ('backing-up', 'restored'):
            backup = target(root, STATE+'/'+Path(name).name)
            raw = backup.read_bytes()
            if digest(raw) != before['sha256'] or len(raw) != before['bytes']:
                raise ValueError('backup identity; no restore writes')
    if (state['phase'] in ('backing-up', 'restored') and state['created_firmware_dir']
            and target(root, FW.rstrip('/')).exists()):
        raise ValueError('unexpected firmware directory in unchanged/restored state')
    if state['phase'] == 'restored':
        return dict(verdict='EXACT_ORIGINAL_PAIR_UNCHANGED', firmware_files=52)
    if state['phase'] == 'backing-up':
        # No firmware replacement is reachable before the installing ledger.
        state['phase'] = 'restored'
        state['restore_recovery_boot_id'] = boot
        save(folder, state)
        return dict(verdict='EXACT_ORIGINAL_PAIR_UNCHANGED', firmware_files=52)
    state['phase'] = 'restoring'
    save(folder, state)
    for name, row in state['files'].items():
        if file_state(target(root, name)) != row['before']:
            state['pending'] = name
            save(folder, state)
            if row['before'] is None:
                target(root, name).unlink()
                sync_dir(target(root, name).parent)
            else:
                atomic(target(root, name), (folder / Path(name).name).read_bytes(),
                       **{k: row['before'][k] for k in ('mode', 'mtime_ns', 'uid', 'gid')})
    for name, row in state['files'].items():
        if file_state(target(root, name)) != row['before']:
            raise ValueError('original restore boundary')
    firmware_dir = target(root, FW.rstrip('/'))
    if state['created_firmware_dir'] and firmware_dir.exists():
        firmware_dir.rmdir()  # Never recursively remove unrelated new files.
        sync_dir(firmware_dir.parent)
    state.update(phase='restored', pending=None, restore_recovery_boot_id=boot)
    save(folder, state)
    # Leave original backups and terminal ledger for host collection/qualified
    # cleanup. A second install is rejected even after a successful restoration.
    return dict(verdict='EXACT_ORIGINAL_PAIR_RESTORED', firmware_files=52,
                services_started=False, remoteproc_started=False)


def cleanup(root, base_path, candidate_path, proc, original_presence='present'):
    """Remove owned backups only after exact restoration and host collection.

    The registered host flow must archive the terminal ledger before calling
    this. Unknown entries/changed backups are retained, never recursively erased.
    """
    root = root.resolve()
    recovery_guard(root, proc)
    folder = target(root, STATE)
    state = json.loads(target(root, STATE+'/ledger.json').read_text())
    if state.get('phase') != 'restored':
        raise ValueError('cleanup requires restored terminal ledger')
    restore(root, base_path, candidate_path, proc, original_presence)  # Read/validate only.
    names = {Path(n).name: row for n, row in state['files'].items() if row['before'] is not None}
    entries = list(folder.iterdir())
    if any(p.name not in names.keys() | {'ledger.json'} for p in entries):
        raise ValueError('unknown backup directory entry; retain evidence')
    for p in entries:
        target(root, STATE+'/'+p.name)
        if not p.is_file():
            raise ValueError('nonregular backup directory entry')
        if p.name != 'ledger.json' and digest(p.read_bytes()) != names[p.name]['before']['sha256']:
            raise ValueError('changed backup; retain evidence')
    for p in entries:
        if p.name != 'ledger.json':
            p.unlink()
    (folder/'ledger.json').unlink()
    folder.rmdir()
    sync_dir(folder.parent)
    return dict(verdict='RESTORED_OWNED_BACKUPS_REMOVED', firmware_files=52)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('install', 'restore', 'cleanup'))
    parser.add_argument('--root', type=Path, default=Path('/'))
    parser.add_argument('--proc', type=Path, required=True)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--original-presence', choices=('present', 'absent'), default='present')
    args = parser.parse_args()
    operation = {'install': install, 'restore': restore, 'cleanup': cleanup}[args.mode]
    print(json.dumps(operation(args.root, args.base, args.candidate, args.proc, args.original_presence), indent=2))
