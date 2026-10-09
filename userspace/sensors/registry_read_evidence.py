#!/usr/bin/env python3
"""Replay verbose RPC file-read lengths; never infer DSP parsing or SSC success."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from uuid import UUID

UNIT = 'hexagonrpcd-adsp-sensorspd.service'
PHYSICAL = 'usr/share/qcom/sm8550/Samsung/gts9wifi/sensors/registry/'
VIRTUAL = '/mnt/vendor/persist/sensors/registry/registry/'
OPEN = re.compile(r'openat\([^,\r\n]+, ([^)\r\n]+)\) -> (\d+)')
READ = re.compile(r'read\((\d+), (\d+)\) -> (\d+)')
CLOSE = re.compile(r'close\((\d+)\)')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inspect(raw, boot_id, manifest):
    boot = UUID(boot_id).hex
    expected, empty = {}, []
    for name, item in manifest.items():
        if not name.startswith(PHYSICAL):
            continue
        leaf = name[len(PHYSICAL):]
        if (not leaf or '/' in leaf or leaf in ('.', '..') or
                type(item['bytes']) is not int or item['bytes'] < 0 or
                not re.fullmatch('[0-9a-f]{64}', item['sha256'])):
            raise ValueError('invalid registry manifest member')
        if item['bytes']:
            expected[VIRTUAL + leaf] = item
        else:
            # An empty marker is not a positive-length cached group. Report
            # it separately, rather than claiming an unobserved read passed.
            empty.append(VIRTUAL + leaf)
    if not expected:
        raise ValueError('empty positive-length registry reference')

    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if not rows:
        raise ValueError('empty runtime journal')
    fds, sessions, faults, pids = {}, [], [], set()
    previous = -1
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or UUID(row['_BOOT_ID']).hex != boot:
            raise ValueError('runtime journal boot attribution mismatch')
        if row.get('_SYSTEMD_UNIT') != UNIT:
            continue
        pid = row['_PID']
        if not isinstance(pid, str) or not pid.isdecimal():
            raise ValueError('invalid sensor PID')
        pids.add(pid)
        if len(pids) != 1:
            raise ValueError('multiple sensor processes; FD attribution ambiguous')
        timestamp = int(row['__MONOTONIC_TIMESTAMP'])
        if timestamp < 0 or timestamp < previous:
            raise ValueError('invalid or decreasing journal timestamp')
        previous = timestamp
        message = row['MESSAGE']
        if not isinstance(message, str):
            raise ValueError('invalid sensor message')
        opened, read, closed = OPEN.fullmatch(message), READ.fullmatch(message), CLOSE.fullmatch(message)
        if opened:
            path, fd = opened[1], int(opened[2])
            if fd in fds:
                faults.append(dict(row=index, reason='FD reused without close', fd=fd))
            session = dict(path=path, fd=fd, open_row=index, open_monotonic_us=timestamp,
                           returned_bytes=0, read_calls=0, closed=False)
            fds[fd] = session
            if path in expected:
                sessions.append(session)
            elif path.startswith(VIRTUAL) and not path.startswith(VIRTUAL + '../') and path not in empty:
                faults.append(dict(row=index, reason='registry open absent from manifest', path=path))
        elif read:
            fd, requested, returned = map(int, read.groups())
            session = fds.get(fd)
            if session is None or returned > requested:
                faults.append(dict(row=index, reason='unattributed read or invalid length', message=message))
            elif session['path'] in expected:
                session['returned_bytes'] += returned
                session['read_calls'] += 1
                session['last_read_monotonic_us'] = timestamp
        elif closed:
            session = fds.pop(int(closed[1]), None)
            if session is None:
                faults.append(dict(row=index, reason='unattributed close', message=message))
            else:
                session['closed'] = True
        elif message.startswith(('read(', 'openat(', 'close(')):
            faults.append(dict(row=index, reason='unrecognized file trace', message=message))
        elif message.startswith(('seek(', 'lseek(', 'fseek(', 'write(', 'rename(',
                                 'Could not read', 'Could not close', 'Could not seek', 'Could not write')):
            # This replay models linear reads, not seeks, registry rewrites or
            # failed I/O. Do not add lengths across either of those boundaries.
            faults.append(dict(row=index, reason='nonlinear or failed I/O', message=message))
        elif any(message.startswith('Could not open ' + path + ':') for path in expected):
            faults.append(dict(row=index, reason='registry open failed', message=message))

    observed = {s['path'] for s in sessions}
    missing = sorted(set(expected) - observed)
    for session in sessions:
        session['expected_bytes'] = expected[session['path']]['bytes']
        session['source_sha256'] = expected[session['path']]['sha256']
        session['length_matches'] = (session['returned_bytes'] == session['expected_bytes'] and
                                     session['read_calls'] > 0 and session['closed'])
        if not session['length_matches']:
            faults.append(dict(row=session['open_row'], path=session['path'],
                               reason='partial/excess read or unclosed session'))
    complete = not missing and not faults
    return dict(boot_id=str(UUID(boot_id)), sensor_pid=next(iter(pids), None),
                verdict='REGISTRY_READ_LENGTHS_MATCH' if complete else 'REGISTRY_READ_LENGTHS_INCOMPLETE',
                complete=complete, expected_nonempty_groups=len(expected),
                observed_nonempty_groups=len(observed), empty_members=sorted(empty),
                read_calls=sum(s['read_calls'] for s in sessions),
                returned_bytes=sum(s['returned_bytes'] for s in sessions),
                missing=missing, faults=faults, sessions=sessions,
                payload_contents_verified=False, DSP_parsing_proved=False,
                electrical_sensor_response_proved=False, SSC_publication_proved=False,
                device_operations=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--journal', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--journal-sha256', required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--boot-id', required=True)
    args = parser.parse_args()
    raw, manifest = args.journal.read_bytes(), args.manifest.read_bytes()
    if sha(raw) != args.journal_sha256 or sha(manifest) != args.manifest_sha256:
        raise ValueError('input evidence hash mismatch')
    result = inspect(raw.decode(), args.boot_id, json.loads(manifest))
    result['inputs'] = dict(journal_sha256=sha(raw), manifest_sha256=sha(manifest))
    print(json.dumps(result, indent=2) + '\n', end='')
    raise SystemExit(not result['complete'])


if __name__ == '__main__':
    main()
