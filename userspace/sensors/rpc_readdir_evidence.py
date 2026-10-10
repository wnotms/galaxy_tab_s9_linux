#!/usr/bin/env python3
"""Check deterministic method-28 replies after the strict return-frame parser."""
import struct


def inspect(returned):
    faults, replies, ends = [], [], 0
    if not returned.get('complete') or returned.get('faults'):
        return dict(complete=False, faults=['return framing incomplete'], replies=[], eof_replies=0,
                    SSC_publication_proved=False)
    for stream in returned['streams']:
        for call in stream['calls']:
            req = call['response_to']
            if not req or req['handle'] != 1 or req['scalars'] >> 24 != 28:
                continue
            reason = None
            try:
                bufs = call['returned_buffers_hex']
                if call['status'] != 0 or len(bufs) != 1:
                    raise ValueError('failed or incomplete readdir reply')
                buf = bytes.fromhex(bufs[0])
                if len(buf) != 264:
                    raise ValueError('method28 reply length')
                inode, = struct.unpack_from('<I', buf)
                eof, = struct.unpack_from('<I', buf, 260)
                name = buf[4:259]
                end = name.index(0)
                if inode != 0 or eof not in (0, 1) or (eof and end != 0):
                    raise ValueError('unexpected fixed readdir fields')
                if buf[259] or any(name[end+1:]):
                    raise ValueError('nonzero reply tail/padding')
                ends += eof
                replies.append(dict(sequence=call['sequence'], eof=bool(eof), name_hex=name[:end].hex()))
            except (ValueError, KeyError, TypeError, struct.error) as exc:
                reason = str(exc)
            if reason:
                faults.append(dict(sequence=call['sequence'], reason=reason))
    if not replies or not ends:
        faults.append('no successful readdir/EOF coverage')
    return dict(complete=not faults, faults=faults, replies=replies, eof_replies=ends,
                SSC_publication_proved=False)
