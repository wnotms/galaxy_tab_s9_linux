#!/usr/bin/env python3
"""One bounded, read-only Servreg GET_DOMAIN_LIST; never activate a DSP.

Use a registered QRTR service64 endpoint, not a guessed node/port. The response
layout is explicit: pinned Linux pdr_internal.h uses 65-byte strings (u8
length), pd-mapper v1.1 servreg_loc.h uses 256 (u16 length). Do not auto-detect
or equate a mapper answer with the separate SSC service (0x190) or samples.
"""
import argparse
import json
from pathlib import Path
import socket
import struct
import time
from uuid import UUID

HEADER = struct.Struct('<BHHH')
METHOD = 0x21
TRANSACTION = 1
SERVICE = b'tms/servreg'
LAYOUTS = {'linux-7.2': (1, 64, 32), 'pd-mapper-1.1': (2, 255, 255)}


class EvidenceError(ValueError):
    def __init__(self, message, evidence):
        super().__init__(message)
        self.evidence = evidence


def request():
    # qcom_pdr_msg.c: top-level QMI_STRING has no inner length prefix.
    body = struct.pack('<BH', 1, len(SERVICE)) + SERVICE
    return HEADER.pack(0, TRANSACTION, METHOD, len(body)) + body


def decode(data, layout):
    width, max_name, max_rows = LAYOUTS[layout]
    if len(data) < HEADER.size:
        raise ValueError('truncated QMI header')
    kind, transaction, method, size = HEADER.unpack_from(data)
    if (kind, transaction, method) != (2, TRANSACTION, METHOD):
        raise ValueError('not the requested QMI response')
    if size != len(data) - HEADER.size:
        raise ValueError('QMI payload length mismatch')
    values = {}
    offset = HEADER.size
    while offset < len(data):
        if len(data) - offset < 3:
            raise ValueError('truncated TLV header')
        tag, size = struct.unpack_from('<BH', data, offset)
        offset += 3
        if tag in values or size > len(data) - offset:
            raise ValueError('duplicate or truncated TLV')
        values[tag] = data[offset:offset + size]
        offset += size
    if len(values.get(2, b'')) != 4:
        raise ValueError('missing QMI result')
    result, error = struct.unpack('<HH', values[2])
    if result or error:
        raise ValueError(f'Servreg failure result={result} error={error}')
    if len(values.get(0x10, b'')) != 2 or len(values.get(0x11, b'')) != 2:
        raise ValueError('missing total domains/database revision')
    total = struct.unpack('<H', values[0x10])[0]
    revision = struct.unpack('<H', values[0x11])[0]
    rows = []
    raw = values.get(0x12, b'\0')
    if not raw or raw[0] > max_rows:
        raise ValueError('invalid domain count')
    offset = 1
    for _ in range(raw[0]):
        if len(raw) - offset < width:
            raise ValueError('truncated domain name length')
        size = int.from_bytes(raw[offset:offset + width], 'little')
        offset += width
        if not 0 < size <= max_name or len(raw) - offset < size + 9:
            raise ValueError('invalid/truncated domain entry')
        name = raw[offset:offset + size].decode('ascii')
        offset += size
        instance, valid, service_data = struct.unpack_from('<IBI', raw, offset)
        offset += 9
        if '\0' in name or valid not in (0, 1):
            raise ValueError('invalid domain name/service data flag')
        row = dict(name=name, instance=instance, service_data_valid=bool(valid),
                   service_data=service_data)
        if any((r['name'], r['instance']) == (name, instance) for r in rows):
            raise ValueError('duplicate domain entry')
        rows.append(row)
    if offset != len(raw) or total < len(rows):
        raise ValueError('domain list length/count mismatch')
    return dict(domains=rows, total_domains=total, database_revision=revision,
                complete=total == len(rows),
                sensor_domain_present=any(r['name'] == 'msm/adsp/sensor_pd' and
                                          r['instance'] == 74 for r in rows),
                ssc_service_verified=False, accelerometer_verified=False)


def query(node, port, layout, seconds=2, *, create=socket.socket,
          clock=time.monotonic, boot=lambda: Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
          expected_boot):
    # Endpoints must come from a complete same-boot QRTR inventory. No retries,
    # mapper starts, service registration, listener changes or paging requests.
    if (layout not in LAYOUTS or not 0 < seconds <= 3 or
        type(node) is not int or type(port) is not int or
        not 0 <= node < 0xfffffffe or not 0 < port < 0xfffffffe):
        raise ValueError('invalid bounded query arguments')
    expected_boot = str(UUID(expected_boot))
    evidence = dict(boot_id=expected_boot, endpoint=[node, port], layout=layout,
                    service='tms/servreg', method=METHOD, request_hex=request().hex(),
                    raw_packets=[], complete=False)
    sock = None
    started = clock()
    try:
        if str(UUID(boot())) != expected_boot:
            raise ValueError('boot changed before Servreg query')
        sock = create(socket.AF_QIPCRTR, socket.SOCK_DGRAM, 0)
        local = sock.getsockname()
        sock.bind((local[0], 0))
        evidence['local'] = list(sock.getsockname())
        sock.settimeout(seconds)
        sock.sendto(request(), (node, port))
        data, peer = sock.recvfrom(65536)
        evidence['raw_packets'].append(dict(peer=list(peer), hex=data.hex(),
                                            seconds=clock() - started))
        if peer != (node, port):
            raise ValueError('reply from unexpected Servreg endpoint')
        evidence.update(decode(data, layout))
        if clock() - started > seconds:
            raise ValueError('Servreg response exceeded observation bound')
        if str(UUID(boot())) != expected_boot:
            raise ValueError('boot changed during Servreg query')
        return evidence
    except (OSError, ValueError) as exc:
        evidence.update(complete=False, error=str(exc))
        raise EvidenceError(str(exc), evidence) from exc
    finally:
        evidence['seconds'] = clock() - started
        if sock is not None:
            sock.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--boot-id', required=True)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--node', type=int, required=True)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--layout', choices=LAYOUTS, required=True)
    parser.add_argument('--seconds', type=float, default=2)
    args = parser.parse_args()
    inventory = json.loads(args.inventory.read_text())
    if (str(UUID(inventory['boot_id'])) != str(UUID(args.boot_id)) or
        inventory['complete'] is not True or not any(
            row['service'] == 64 and row['instance'] == 257 and
            row['node'] == args.node and row['port'] == args.port
            for row in inventory['services'])):
        raise ValueError('endpoint not in complete same-boot Servreg inventory')
    try:
        result = query(args.node, args.port, args.layout, args.seconds,
                       expected_boot=args.boot_id)
    except EvidenceError as exc:
        print(json.dumps(exc.evidence, indent=2))
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result['complete'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
