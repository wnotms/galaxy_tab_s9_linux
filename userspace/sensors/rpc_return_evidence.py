#!/usr/bin/env python3
"""Parse bounded listener2 frames; never equate transport return with DSP parsing."""
import argparse
import hashlib
import json
from pathlib import Path
import posixpath
import re
import struct
from uuid import UUID

LINE = re.compile(r'RPCRETURN seq=(\d+) phase=(tx|next|rx) rctx=(\d+) '
                  r'handle=(\d+) sc=([0-9a-f]{8}) status=(-?\d+) bytes=(\d+) hex=([0-9a-f]+|-)')
UNITS = {'hexagonrpcd-adsp-rootpd.service', 'hexagonrpcd-adsp-sensorspd.service'}
FRAME_MAX = 8192


def _packed_buffers(frame, count):
    """Independent Qualcomm listener2 framing; alignment applies to payload only."""
    offset, decoded = 0, []
    if len(frame) > FRAME_MAX:
        raise ValueError('frame limit')
    for _ in range(count):
        if offset + 4 > len(frame):
            raise ValueError('missing buffer header')
        size, = struct.unpack_from('<I', frame, offset)
        offset += 4
        if size:
            offset = (offset + 7) & ~7
            if size > len(frame) - offset:
                raise ValueError('missing buffer payload')
        decoded.append(frame[offset:offset + size])
        offset += size
    return decoded, offset


def buffers(frame, count):
    decoded, offset = _packed_buffers(frame, count)
    if offset != len(frame):
        raise ValueError('extra frame bytes')
    return decoded


def invocation(frame, scalars):
    """Qualcomm pack_in_bufs followed by unaligned uint32 pack_out_lens.

    listener_buf.h, Android13 r77 blob ee95b1d768fe6ba923dc1bdaf9ebb6c2210f366c.
    These are output capacities, not another packed input buffer or padding.
    """
    decoded, offset = _packed_buffers(frame, (scalars >> 16) & 255)
    count = (scalars >> 8) & 255
    if len(frame) - offset != 4 * count:
        raise ValueError('missing/extra output capacity descriptors')
    capacities = list(struct.unpack_from('<' + 'I' * count, frame, offset)) if count else []
    return decoded, capacities


def inspect(raw, boot):
    boot = UUID(boot).hex
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    streams, faults, seen_cursors = {}, [], set()
    for index, row in enumerate(rows):
        message = row.get('MESSAGE', '')
        if not message.startswith('RPCRETURN'):
            continue
        unit, pid = row.get('_SYSTEMD_UNIT'), str(row.get('_PID', ''))
        cursor = row.get('__CURSOR')
        if (row.get('_BOOT_ID') != boot or unit not in UNITS or not pid.isdigit()
                or not cursor or cursor in seen_cursors or
                not str(row.get('__MONOTONIC_TIMESTAMP', '')).isdigit()):
            faults.append({'row': index, 'reason': 'trace attribution'})
            continue
        seen_cursors.add(cursor)
        if message.startswith('RPCRETURN_LIMIT'):
            faults.append({'row': index, 'reason': 'observer limit/error', 'message': message})
            continue
        match = LINE.fullmatch(message)
        if not match:
            faults.append({'row': index, 'reason': 'malformed trace'})
            continue
        seq, phase, rctx, handle, sc, status, size, data = match.groups()
        if data != '-' and len(data) % 2:
            faults.append({'row': index, 'reason': 'odd hex length'})
            continue
        event = dict(sequence=int(seq), phase=phase, rctx=int(rctx), handle=int(handle),
                     scalars=int(sc, 16), status=int(status), bytes=int(size),
                     frame=bytes.fromhex(data) if data != '-' else b'', row=index,
                     monotonic_us=int(row['__MONOTONIC_TIMESTAMP']))
        if (event['bytes'] != len(event['frame']) or event['bytes'] > FRAME_MAX or
                any(event[k] > 0xffffffff for k in ('rctx', 'handle'))):
            faults.append({'row': index, 'reason': 'frame size/metadata'})
            continue
        stream = streams.setdefault((unit, pid), [])
        if stream and event['monotonic_us'] < stream[-1]['monotonic_us']:
            faults.append({'row': index, 'reason': 'backwards source time'})
        stream.append(event)
    results = []
    for (unit, pid), events in streams.items():
        calls, pending, previous = [], None, None
        try:
            for event in events:
                phase, seq = event['phase'], event['sequence']
                if phase == 'tx':
                    if pending is not None or seq != len(calls):
                        raise ValueError('missing/duplicate sequence boundary')
                    if previous is None:
                        if (seq or event['rctx'] or event['handle'] or event['scalars'] or
                                event['status'] != 0xffffffff or event['frame']):
                            raise ValueError('invalid first listener call')
                        payloads = []
                    else:
                        if any(event[k] != previous[k] for k in ('rctx', 'handle', 'scalars')):
                            raise ValueError('return context/scalar mismatch')
                        payloads = buffers(event['frame'], (event['scalars'] >> 8) & 255)
                    pending = {'sequence': seq, 'tx_row': event['row'], 'status': event['status'],
                               'transport_return': None, 'request': None,
                               'response_to': (None if previous is None else {
                                   'handle': previous['handle'], 'scalars': previous['scalars'],
                                   'rctx': previous['rctx'], 'buffers_hex':
                                   [p.hex() for p in invocation(previous['frame'],
                                                               previous['scalars'])[0]],
                                   'output_capacities': invocation(previous['frame'],
                                                                   previous['scalars'])[1]}),
                               'returned_buffer_lengths': [len(p) for p in payloads],
                               'returned_buffer_sha256': [hashlib.sha256(p).hexdigest() for p in payloads],
                               'returned_buffers_hex': [p.hex() for p in payloads]}
                elif phase == 'next':
                    if pending is None or seq != pending['sequence'] or pending['transport_return'] is not None:
                        raise ValueError('missing/duplicate next2 boundary')
                    if event['frame']:
                        raise ValueError('unexpected next2 payload')
                    pending['transport_return'] = event['status']
                    pending['next_request_metadata'] = {k: event[k] for k in ('rctx', 'handle', 'scalars')}
                    if event['status'] != 0:
                        calls.append(pending)
                        pending = None
                        # A failed listener call is terminal, not an acknowledged reply.
                        if event is not events[-1]:
                            raise ValueError('events after failed next2')
                else:
                    if pending is None or seq != pending['sequence'] or pending['transport_return'] != 0:
                        raise ValueError('incoming frame without successful next2')
                    if any(event[k] != pending['next_request_metadata'][k] for k in ('rctx', 'handle', 'scalars')):
                        raise ValueError('next2/incoming metadata mismatch')
                    payloads, capacities = invocation(event['frame'], event['scalars'])
                    pending['request'] = {'handle': event['handle'], 'scalars': event['scalars'],
                                          'rctx': event['rctx'], 'buffer_lengths': [len(p) for p in payloads],
                                          'buffers_hex': [p.hex() for p in payloads],
                                          'output_capacities': capacities}
                    calls.append(pending)
                    pending, previous = None, event
            if pending is not None and pending['transport_return'] is not None:
                raise ValueError('missing incoming frame after next2')
        except ValueError as exc:
            faults.append({'unit': unit, 'pid': pid, 'reason': str(exc)})
        results.append({'unit': unit, 'pid': pid, 'calls': calls, 'pending_final_call': pending})
    for unit in UNITS:
        if len([s for s in results if s['unit'] == unit]) != 1:
            faults.append({'unit': unit, 'reason': 'missing/restarted RPC process'})
    return {'boot_id': boot, 'complete': bool(results) and not faults,
            'faults': faults, 'streams': results, 'DSP_content_parsing_proved': False,
            'SSC_publication_proved': False, 'accelerometer_sample_proved': False}


def registry_contents(evidence, manifest):
    """Replay actual apps_std1 open/read/close replies, hashing returned file bytes."""
    physical = 'usr/share/qcom/sm8550/Samsung/gts9wifi/sensors/registry/'
    virtual = '/mnt/vendor/persist/sensors/registry/registry/'
    expected = {}
    for name, item in manifest.items():
        if not name.startswith(physical):
            continue
        leaf = name[len(physical):]
        if (not leaf or '/' in leaf or leaf in ('.', '..') or type(item['bytes']) is not int
                or item['bytes'] < 0 or not re.fullmatch('[0-9a-f]{64}', item['sha256'])):
            raise ValueError('invalid registry manifest')
        if item['bytes']:
            expected[virtual + leaf] = item
    faults, sessions = [], []
    for stream in evidence['streams']:
        if stream['unit'] != 'hexagonrpcd-adsp-sensorspd.service':
            continue
        live = {}
        calls = stream['calls'] + ([stream['pending_final_call']] if stream['pending_final_call'] else [])
        for call in calls:
            request = call.get('response_to')
            if not request or request['handle'] != 1:
                continue
            method = (request['scalars'] >> 24) & 31
            incoming = [bytes.fromhex(p) for p in request['buffers_hex']]
            outgoing = [bytes.fromhex(p) for p in call['returned_buffers_hex']]
            try:
                if method == 19:
                    if len(incoming) != 5 or not incoming[3].endswith(b'\0'):
                        raise ValueError('invalid open arguments')
                    path = posixpath.normpath(incoming[3][:-1].decode('utf-8'))
                    if not path.startswith(virtual):
                        continue
                    if path not in expected:
                        raise ValueError('registry file absent from manifest')
                    if call['status'] or call['transport_return'] != 0 or len(outgoing) != 1 or len(outgoing[0]) != 4:
                        raise ValueError('registry open response unsuccessful/unacknowledged')
                    fd, = struct.unpack('<I', outgoing[0])
                    if fd in live:
                        raise ValueError('registry descriptor reused before close')
                    session = {'path': path, 'fd': fd, 'data': bytearray(), 'closed': False,
                               'read_calls': 0, 'open_sequence': call['sequence']}
                    live[fd] = session
                    sessions.append(session)
                elif method in (3, 4, 5, 9):
                    if not incoming or len(incoming[0]) < 4:
                        raise ValueError('missing descriptor')
                    fd, = struct.unpack_from('<I', incoming[0])
                    if fd not in live:
                        continue
                    if call['status'] or call['transport_return'] != 0:
                        raise ValueError('registry response unsuccessful/unacknowledged')
                    session = live[fd]
                    if method == 3:
                        session['closed'] = True
                        del live[fd]
                    elif method == 4:
                        if len(incoming[0]) != 8 or len(outgoing) != 2 or len(outgoing[0]) != 8:
                            raise ValueError('invalid read arguments')
                        _, requested = struct.unpack('<II', incoming[0])
                        written, eof = struct.unpack('<II', outgoing[0])
                        if len(outgoing[1]) != requested or written > requested or eof not in (0, 1):
                            raise ValueError('invalid read reply length')
                        session['data'].extend(outgoing[1][:written])
                        session['read_calls'] += 1
                    else:
                        raise ValueError('nonlinear registry I/O')
            except (ValueError, UnicodeDecodeError, struct.error) as exc:
                faults.append({'sequence': call['sequence'], 'reason': str(exc)})
    for session in sessions:
        data = bytes(session.pop('data'))
        session['returned_bytes'] = len(data)
        session['returned_sha256'] = hashlib.sha256(data).hexdigest()
        reference = expected[session['path']]
        session['content_matches'] = (session['closed'] and session['read_calls'] > 0
                                      and len(data) == reference['bytes']
                                      and session['returned_sha256'] == reference['sha256'])
        if not session['content_matches']:
            faults.append({'path': session['path'], 'reason': 'partial/unclosed/mismatched registry content'})
    missing = sorted(set(expected) - {s['path'] for s in sessions})
    return {'complete': bool(expected) and evidence['complete'] and not faults and not missing,
            'expected_nonempty_groups': len(expected), 'observed_sessions': len(sessions),
            'missing': missing, 'faults': faults, 'sessions': sessions,
            'DSP_content_parsing_proved': False, 'SSC_publication_proved': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--journal', type=Path, required=True)
    parser.add_argument('--boot-id', required=True)
    args = parser.parse_args()
    result = inspect(args.journal.read_text(), args.boot_id)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['complete'] else 2)
