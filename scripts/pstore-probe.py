#!/usr/bin/env python3
"""Generate and verify bounded known-data probes; never contacts a device."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import uuid


def make_probe(boot_id, capture_id):
    boot_id, capture_id = str(uuid.UUID(boot_id)), str(uuid.UUID(capture_id))
    seed = (boot_id + capture_id).encode('ascii')
    pattern = b''.join(bytes([v]) * 4096 for v in (0, 255, 85, 170))
    pattern += b''.join(hashlib.sha256(seed + i.to_bytes(4, 'little')).digest()
                        for i in range(512))
    header = f'GTS9_PMSG_BEGIN id={capture_id} boot={boot_id} bytes={len(pattern)} sha256={hashlib.sha256(pattern).hexdigest()}\n'.encode()
    return header + pattern + f'\nGTS9_PMSG_END id={capture_id}\n'.encode()


def compare(expected, recovered):
    """Only a full byte-exact unique occurrence passes; no marker repair."""
    identity = re.match(rb'GTS9_PMSG_BEGIN id=([0-9a-f-]{36}) boot=([0-9a-f-]{36}) ', expected)
    if not identity or make_probe(identity[2].decode(), identity[1].decode()) != expected:
        raise ValueError('invalid or corrupt expected probe')
    offsets = []
    offset = recovered.find(expected)
    while offset >= 0:
        offsets.append(offset)
        offset = recovered.find(expected, offset + 1)
    result = {'expected_bytes': len(expected), 'recovered_bytes': len(recovered),
              'expected_sha256': hashlib.sha256(expected).hexdigest(),
              'recovered_sha256': hashlib.sha256(recovered).hexdigest(),
              'verdict': 'exact' if len(offsets) == 1 else 'absent_or_corrupt',
              'exact_offsets': offsets, 'ready_for_wedge_series': False}
    if not offsets:
        # An exact header permits positional damage measurement, never trust.
        header = expected.split(b'\n', 1)[0] + b'\n'
        start = recovered.find(header)
        if start >= 0 and recovered.find(header, start + 1) < 0:
            observed = recovered[start:start + len(expected)]
            changes = [{'offset': i, 'expected': a, 'observed': b, 'xor': a ^ b}
                       for i, (a, b) in enumerate(zip(expected, observed)) if a != b]
            result.update(aligned_offset=start, truncated=len(observed) < len(expected),
                          changed_bytes=len(changes),
                          changed_bits=sum(c['xor'].bit_count() for c in changes),
                          changes=changes)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    make = sub.add_parser('make')
    make.add_argument('--boot-id', required=True)
    make.add_argument('--capture-id', required=True)
    make.add_argument('--output', type=Path, required=True)
    check = sub.add_parser('check')
    check.add_argument('expected', type=Path)
    check.add_argument('recovered', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'make':
            payload = make_probe(args.boot_id, args.capture_id)
            with args.output.open('xb') as f:
                f.write(payload)
            print(json.dumps({'capture_id': str(uuid.UUID(args.capture_id)),
                              'boot_id': str(uuid.UUID(args.boot_id)),
                              'bytes': len(payload),
                              'sha256': hashlib.sha256(payload).hexdigest()}, indent=2))
            return 0
        result = compare(args.expected.read_bytes(), args.recovered.read_bytes())
        print(json.dumps(result, indent=2))
        return 0 if result['verdict'] == 'exact' else 2
    except (OSError, ValueError) as exc:
        parser.exit(2, f'{exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
