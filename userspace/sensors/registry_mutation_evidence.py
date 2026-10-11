#!/usr/bin/env python3
"""Read-only isolated sensor snapshots and replay of acknowledged apps_std I/O.

Uses the qualified listener frame parser. Models only the registered copy, not
Android persist; file-byte agreement does not establish DSP parsing or SSC.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import posixpath
import re
import stat
import struct
import subprocess
from uuid import UUID

PREFIX = 'usr/share/qcom/sm8550/Samsung/gts9wifi/sensors/'
MACHINE = '3c2a1b8f2d624db4b5ffdc836050fcf6'
UNIT = 'hexagonrpcd-adsp-sensorspd.service'
MAX_FILE = 128 * 1024
MAX_TOTAL = 2 * 1024 * 1024
MAX_FILES = 2048
SPEC = importlib.util.spec_from_file_location(
    'mutable_registry_return', Path(__file__).with_name('rpc_return_evidence.py'))
RETURN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RETURN)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def relative(name):
    if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?', name)
            or any(p in ('.', '..') for p in name.split('/'))):
        raise ValueError('invalid isolated member path')
    return name


def mapped(path):
    if not path.startswith('/') or '\x00' in path or len(path) > 4096:
        return None
    path = posixpath.normpath(path)
    # Exact shared mappings in the qualified rpcd_builder.c, not a guessed
    # relation between the similarly named sns_reg_config and sns_reg.conf.
    for virtual in ('/mnt/vendor/persist/sensors/registry/', '/persist/sensors/registry/'):
        if path.startswith(virtual):
            return relative(path[len(virtual):])
    for virtual in ('/vendor/etc/sensors/', '/system/vendor/etc/sensors/'):
        if path == virtual + 'sns_reg_config':
            return 'sns_reg.conf'
        if path.startswith(virtual + 'config/'):
            return relative('config/' + path[len(virtual + 'config/'):])
    return None


def writable(name):
    return name == 'sns_reg_version' or (name.startswith('registry/') and name.count('/') == 1)


def capture(boot, phase, *, root=Path('/'), quiescent=None):
    """Bounded regular-file collection, with identity and no running producers."""
    root = Path(root).resolve()
    if phase not in ('before', 'after'):
        raise ValueError('snapshot phase')
    boot = str(UUID(boot))
    if ((root/'etc/machine-id').read_text().strip() != MACHINE
            or str(UUID((root/'proc/sys/kernel/random/boot_id').read_text().strip())) != boot):
        raise ValueError('snapshot machine/boot attribution')
    if quiescent is None:
        def quiescent():
            command = ['systemctl', 'is-active', 'hexagonrpcd-adsp-rootpd', 'hexagonrpcd-adsp-sensorspd']
            r = subprocess.run(command, capture_output=True, text=True, timeout=5)
            return r.stdout.splitlines() == ['inactive', 'inactive']
    if not quiescent():
        raise ValueError('snapshot requires both owned RPC producers inactive')
    prefix = root/PREFIX
    if prefix.is_symlink() or prefix.resolve() != prefix or not prefix.is_dir():
        raise ValueError('unsafe/missing isolated sensor prefix')
    device = prefix.stat().st_dev
    files, total = {}, 0
    for path in sorted(prefix.rglob('*')):
        info = path.lstat()
        if info.st_dev != device or path.is_symlink():
            raise ValueError('snapshot crossed mount/symlink')
        if stat.S_ISDIR(info.st_mode):
            continue
        name = relative(path.relative_to(prefix).as_posix())
        if (not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE
                or stat.S_IMODE(info.st_mode) & (~0o777 | 0o111) or len(files) >= MAX_FILES):
            raise ValueError('snapshot file kind/size/mode/count')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            before = os.fstat(fd)
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                data = stream.read(MAX_FILE + 1)
            after = os.fstat(fd)
        finally:
            os.close(fd)
        now = path.lstat()
        signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if not signature(info) == signature(before) == signature(after) == signature(now) or len(data) != info.st_size:
            raise ValueError('snapshot changed during collection')
        total += len(data)
        if total > MAX_TOTAL:
            raise ValueError('snapshot total size')
        files[name] = dict(bytes=len(data), sha256=digest(data), data_hex=data.hex(),
                           mode=stat.S_IMODE(info.st_mode), uid=info.st_uid, gid=info.st_gid,
                           mtime_ns=info.st_mtime_ns)
    if not quiescent():
        raise ValueError('snapshot producers changed during collection')
    if not files:
        raise ValueError('empty sensor snapshot')
    return dict(schema=1, machine_id=MACHINE, boot_id=boot, phase=phase,
                prefix=PREFIX, producers_inactive=True, files=files, bytes=total,
                device_writes=False, physical_persist_accessed=False)


def decode_snapshot(snapshot, boot, phase):
    if (snapshot.get('schema') != 1 or snapshot.get('machine_id') != MACHINE
            or str(UUID(snapshot['boot_id'])) != str(UUID(boot)) or snapshot.get('phase') != phase
            or snapshot.get('prefix') != PREFIX or snapshot.get('producers_inactive') is not True):
        raise ValueError('snapshot identity/phase/quiescence')
    files = snapshot['files']
    if not isinstance(files, dict) or not 0 < len(files) <= MAX_FILES:
        raise ValueError('snapshot file count')
    result, total = {}, 0
    for name, row in files.items():
        relative(name)
        data = bytes.fromhex(row['data_hex'])
        if (type(row['bytes']) is not int or row['bytes'] != len(data) or len(data) > MAX_FILE
                or row['sha256'] != digest(data)
                or any(type(row[k]) is not int or row[k] < 0 for k in ('uid', 'gid', 'mtime_ns', 'mode'))
                or row['mode'] & (~0o777 | 0o111)):
            raise ValueError('snapshot bytes/hash/metadata')
        total += len(data)
        result[name] = data
    if total > MAX_TOTAL or snapshot['bytes'] != total:
        raise ValueError('snapshot total size')
    return result


def cstring(raw):
    if not raw or raw[-1:] != b'\0' or b'\0' in raw[:-1]:
        raise ValueError('invalid callback string')
    return raw[:-1].decode('utf-8')


def replay(frames, boot, before, after, manifest):
    initial = decode_snapshot(before, boot, 'before')
    final = decode_snapshot(after, boot, 'after')
    expected = {n[len(PREFIX):]:r for n,r in manifest.items() if n.startswith(PREFIX)}
    if set(expected) != set(initial) or any(
            len(initial[n]) != row['bytes'] or digest(initial[n]) != row['sha256']
            or before['files'][n]['mode'] != row['mode']
            or before['files'][n]['mtime_ns'] != row['mtime'] * 1000000000
            for n,row in expected.items()):
        raise ValueError('before snapshot differs from qualified profile')
    if not frames['complete'] or frames['boot_id'] != UUID(boot).hex:
        raise ValueError('incomplete/foreign callback frame source')
    # Nodes preserve open-file identity across rename/replacement.
    nodes = {n:bytearray(data) for n,data in initial.items()}
    live, touched, events, faults, counts = {}, set(), [], [], dict(opens=0, reads=0, writes=0, renames=0, closes=0)
    calls = sorted(((c['tx_row'], s['unit'], s['pid'], c)
                    for s in frames['streams'] for c in s['calls'] +
                    ([s['pending_final_call']] if s['pending_final_call'] else [])), key=lambda x:x[0])
    for _, unit, pid, call in calls:
        req = call.get('response_to')
        if req is None or req['handle'] != 1:
            continue
        event = dict(sequence=call['sequence'], unit=unit, pid=pid)
        try:
            incoming = [bytes.fromhex(x) for x in req['buffers_hex']]
            outgoing = [bytes.fromhex(x) for x in call['returned_buffers_hex']]
            method = req['scalars'] >> 24 & 31
            if method == 31:
                if not incoming or len(incoming[0]) < 4:
                    raise ValueError('missing extended method')
                method = struct.unpack_from('<I', incoming[0])[0]
            key = (unit, pid)
            event = dict(sequence=call['sequence'], unit=unit, pid=pid, method=method)
            acknowledged = not call['status'] and call['transport_return'] == 0
            capacities = req['output_capacities']
            if (len(outgoing) != len(capacities) or any(type(c) is not int or c<0 or c>RETURN.FRAME_MAX
                    or len(data)>c for data,c in zip(outgoing,capacities))):
                raise ValueError('reply exceeds requested output capacity')
            if method == 19:
                if len(incoming) != 5:
                    raise ValueError('open argument count')
                path, mode = cstring(incoming[3]), cstring(incoming[4])
                name = mapped(path)
                if name is None:
                    if mode[:1] in ('w','a') or '+' in mode:
                        raise ValueError('write open outside isolated registry')
                    if acknowledged and len(outgoing)==1 and len(outgoing[0])==4:
                        other_fd,=struct.unpack('<I',outgoing[0])
                        if (unit,pid,other_fd) in live:
                            raise ValueError('tracked descriptor reused by unrelated open')
                    continue
                if not acknowledged or capacities != [4] or len(outgoing) != 1 or len(outgoing[0]) != 4:
                    raise ValueError('mapped open unsuccessful/unacknowledged')
                if mode not in {m+b+p for m in 'rwa' for b,p in (('',''),('b',''),('','+'),('b','+'),('+','b'))}:
                    raise ValueError('unsupported fopen mode')
                write = mode[0] != 'r' or '+' in mode
                if write and (not writable(name) or unit != UNIT):
                    raise ValueError('write outside qualified sensor registry scope')
                fd, = struct.unpack('<I',outgoing[0])
                if (*key,fd) in live:
                    raise ValueError('descriptor reuse without close')
                if mode[0] == 'r' and name not in nodes:
                    raise ValueError('read open lacks registered/generated bytes')
                if mode[0] == 'w':
                    nodes.setdefault(name,bytearray()).clear(); touched.add(name)
                elif mode[0] == 'a' and name not in nodes:
                    nodes[name]=bytearray(); touched.add(name)
                live[(*key,fd)] = dict(name=name,node=nodes[name],offset=0,write=write,
                                       read=mode[0]=='r' or '+' in mode,append=mode[0]=='a')
                counts['opens'] += 1
                events.append(event | dict(path=path,member=name,mode=mode))
            elif method == 33:
                if len(incoming) != 3 or len(incoming[0]) != 4 or outgoing:
                    raise ValueError('rename argument/reply shape')
                source, target = mapped(cstring(incoming[1])), mapped(cstring(incoming[2]))
                if (not acknowledged or source is None or target is None or
                        not writable(source) or not writable(target) or unit != UNIT or source not in nodes):
                    raise ValueError('rename scope/source/acknowledgement')
                nodes[target]=nodes.pop(source); touched.update((source,target))
                counts['renames'] += 1;events.append(event | dict(source=source,target=target))
            elif method in (3,4,5,9):
                if not incoming or len(incoming[0]) < 4:
                    raise ValueError('missing file descriptor')
                fd,=struct.unpack_from('<I',incoming[0]); desc=live.get((*key,fd))
                if desc is None:
                    if method==5:
                        raise ValueError('unattributed write descriptor')
                    continue  # Independent library/SoC callbacks remain in the full frame/status gate.
                if not acknowledged:
                    raise ValueError('file callback unsuccessful/unacknowledged')
                if method == 3:
                    if len(incoming)!=1 or len(incoming[0])!=4 or outgoing:
                        raise ValueError('close shape')
                    del live[(*key,fd)];counts['closes'] += 1
                elif method in (4,5):
                    if len(incoming[0])!=8 or len(outgoing[0])!=8:
                        raise ValueError('read/write numeric shape')
                    _, requested = struct.unpack('<II',incoming[0]);written,eof=struct.unpack('<II',outgoing[0])
                    if written>requested or eof not in (0,1):
                        raise ValueError('read/write count/eof')
                    if method==4:
                        if not desc['read'] or len(incoming)!=1 or capacities != [8,requested] or len(outgoing)!=2 or len(outgoing[1])!=requested:
                            raise ValueError('read shape/permission')
                        expected_bytes=bytes(desc['node'][desc['offset']:desc['offset']+requested])
                        if outgoing[1][:written]!=expected_bytes or written!=len(expected_bytes):
                            raise ValueError('returned read bytes differ from replayed file')
                        counts['reads'] += 1
                    else:
                        if not desc['write'] or len(incoming)!=2 or capacities != [8] or len(outgoing)!=1 or requested>len(incoming[1]) or eof:
                            raise ValueError('write shape/permission')
                        if written!=requested:
                            raise ValueError('short registry write')
                        if desc['append']:desc['offset']=len(desc['node'])
                        end=desc['offset']+written
                        if end>MAX_FILE:
                            raise ValueError('generated file size limit')
                        if end>len(desc['node']):desc['node'].extend(b'\0'*(end-len(desc['node'])))
                        desc['node'][desc['offset']:end]=incoming[1][:written]
                        touched.add(desc['name']);counts['writes'] += 1
                    desc['offset'] += written
                else:
                    if len(incoming)!=1 or len(incoming[0])!=12 or outgoing:
                        raise ValueError('seek shape')
                    _,position,whence=struct.unpack('<III',incoming[0])
                    if whence>2:
                        raise ValueError('seek origin')
                    desc['offset']=(0,desc['offset'],len(desc['node']))[whence]+position
                    if desc['offset']>MAX_FILE:
                        raise ValueError('seek bounds')
                events.append(event | dict(member=desc['name']))
            elif method not in (2,26,27,28,31):
                raise ValueError('unmodelled apps_std method')
        except (ValueError,UnicodeError,IndexError,struct.error) as exc:
            faults.append(event | dict(reason=str(exc)))
    # The bootstrap reader may stay open until process exit. The after snapshot
    # requires both producers stopped; do not invent an RPC close callback.
    # Mutable descriptors still require an acknowledged explicit close.
    open_readonly = [dict(descriptor=list(k),member=d['name'],offset=d['offset'],
                          remaining_bytes=max(0,len(d['node'])-d['offset']))
                     for k,d in live.items() if not d['write']]
    if any(d['write'] for d in live.values()):
        faults.append(dict(reason='unclosed mutable file descriptors',
                           descriptors=[list(k)for k,d in live.items() if d['write']]))
    replayed={n:bytes(data)for n,data in nodes.items()}
    if replayed!=final:
        faults.append(dict(reason='final snapshot differs from acknowledged I/O replay',
                           differing_members=sorted(n for n in set(replayed)|set(final) if replayed.get(n)!=final.get(n))))
    owners={(r['uid'],r['gid'])for r in before['files'].values()}
    for n,row in after['files'].items():
        if row['mode'] & 0o111:
            faults.append(dict(reason='unexpected executable sensor file',member=n))
        if (row['uid'],row['gid']) not in owners:
            faults.append(dict(reason='unexplained final ownership',member=n))
        if n in before['files'] and n not in touched and any(row[k]!=before['files'][n][k] for k in ('mode','uid','gid','mtime_ns')):
            faults.append(dict(reason='unexplained immutable metadata change',member=n))
    changed=sorted(n for n in set(initial)|set(final) if initial.get(n)!=final.get(n))
    return dict(complete=not faults,verdict='ISOLATED_CACHE_IO_REPLAY_MATCHES' if not faults else 'STOP_CACHE_IO_EVIDENCE',
                boot_id=str(UUID(boot)),counts=counts,events=events,faults=faults,changed_members=changed,
                open_readonly_at_journal_boundary=open_readonly,
                before_hashes={n:digest(d)for n,d in initial.items()},after_hashes={n:digest(d)for n,d in final.items()},
                DSP_parsing_proved=False,SSC_publication_proved=False,physical_persist_accessed=False)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--boot-id',required=True)
    parser.add_argument('--phase',choices=('before','after'),required=True)
    args=parser.parse_args()
    print(json.dumps(capture(args.boot_id,args.phase),indent=2,sort_keys=True))
