#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""One bounded notifier response on a fresh private QRTR client.

REGISTER_LISTENER(0x20), enable=0: unregister this client, never subscribe.
Read curr_state only if the server supplies its optional response TLV. Missing
state/unsupported operation remains unknown; never retry with enable=1, send
ACK/restart, activate a DSP or equate domain UP with SSC/sample availability.
Wire/state definitions: Linux7.2-rc3 qcom_pdr_msg.c, pdr_internal.h, pdr.h.
"""
import argparse
import json
import math
from pathlib import Path
import socket
import struct
import time
from uuid import UUID

HEADER = struct.Struct('<BHHH')
METHOD = 0x20
TRANSACTION = 1
PATH = b'msm/adsp/sensor_pd'
STATES = {1: 'LOCATOR_ERROR', 0x0fffffff: 'DOWN', 0x1fffffff: 'UP',
          0x2fffffff: 'EARLY_DOWN', 0x7fffffff: 'UNINIT'}


class EvidenceError(ValueError):
    def __init__(self, message, evidence):
        super().__init__(message)
        self.evidence = evidence


def request():
    # Top-level QMI_STRING is raw path bytes, without an inner length or NUL.
    body = b'\x01\x01\x00\x00' + struct.pack('<BH', 2, len(PATH)) + PATH
    return HEADER.pack(0, TRANSACTION, METHOD, len(body)) + body


def endpoint(inventory, domains, expected_boot):
    try:
        boot = UUID(expected_boot)
        valid = (UUID(inventory['boot_id']) == boot and UUID(domains['boot_id']) == boot and
                 inventory.get('complete') is True and domains.get('complete') is True and
                 isinstance(domains['domains'], list) and isinstance(inventory['services'], list))
        if not valid:
            raise ValueError('incomplete or different-boot endpoint evidence')
        if (any(not isinstance(r, dict) or not {'name', 'instance'} <= r.keys()
                for r in domains['domains']) or
                any(not isinstance(r, dict) or not {'service', 'instance', 'node', 'port'} <= r.keys()
                    for r in inventory['services'])):
            raise ValueError('incomplete domain or server row')
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError('malformed endpoint evidence') from exc
    matches = [r for r in domains['domains'] if r['name'] == PATH.decode()]
    if len(matches) != 1 or type(matches[0]['instance']) is not int or matches[0]['instance'] != 74:
        raise ValueError('no unique native X710 sensor domain')
    # Native mapper instance_id=74 is the notifier instance; QRTR encodes
    # instance<<8 | version. Service66 is NOTIF, not LOC64 or SYSCTRL69.
    servers = [r for r in inventory['services']
               if r['service'] == 66 and r['instance'] == (matches[0]['instance'] << 8 | 1)]
    if len(servers) != 1:
        raise ValueError('no unique advertised sensor notifier')
    server = servers[0]
    if (type(server['node']) is not int or type(server['port']) is not int or
            not 0 <= server['node'] < 0xfffffffe or not 0 < server['port'] < 0xfffffffe):
        raise ValueError('invalid advertised notifier address')
    return server['node'], server['port']


def decode(data):
    if len(data) < HEADER.size:
        raise ValueError('truncated QMI header')
    kind, transaction, method, length = HEADER.unpack_from(data)
    if (kind, transaction, method) != (2, TRANSACTION, METHOD):
        raise ValueError('not the requested notifier response')
    if length != len(data) - HEADER.size:
        raise ValueError('QMI payload length mismatch')
    fields, offset = {}, HEADER.size
    while offset < len(data):
        if len(data) - offset < 3:
            raise ValueError('truncated TLV header')
        tag, length = struct.unpack_from('<BH', data, offset)
        offset += 3
        if tag not in (2, 0x10) or tag in fields or length > len(data) - offset:
            raise ValueError('unexpected/duplicate/truncated TLV')
        fields[tag] = data[offset:offset + length]
        offset += length
    if len(fields.get(2, b'')) != 4:
        raise ValueError('missing QMI result')
    result, error = struct.unpack('<HH', fields[2])
    if result or error:
        raise ValueError(f'notifier failure result={result} error={error}')
    common = dict(protocol_complete=True, complete=False, state_present=False,
                  domain_state='UNKNOWN', SSC_service_verified=False,
                  accelerometer_verified=False)
    if 0x10 not in fields:
        return common
    if len(fields[0x10]) != 4:
        raise ValueError('invalid current-state length')
    state, = struct.unpack('<I', fields[0x10])
    if state not in STATES:
        raise ValueError('unknown current-state enum')
    return dict(common, complete=True, state_present=True,
                state_value=state, domain_state=STATES[state])


def query(inventory, domains, seconds=2, *, expected_boot,
          create=socket.socket, clock=time.monotonic,
          boot=lambda: Path('/proc/sys/kernel/random/boot_id').read_text().strip()):
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 3:
        raise ValueError('invalid query deadline')
    expected_boot = str(UUID(expected_boot))
    node, port = endpoint(inventory, domains, expected_boot)
    evidence = dict(boot_id=expected_boot, endpoint=[node, port],
                    service=66, instance=74, domain=PATH.decode(), method=METHOD,
                    operation='unregister-own-client/read-optional-current-state',
                    enable=0, listener_registered=False, DSP_started=False,
                    request_hex=request().hex(), raw_packets=[], complete=False)
    started, sock = clock(), None
    try:
        if str(UUID(boot())) != expected_boot:
            raise ValueError('boot changed before notifier query')
        sock = create(socket.AF_QIPCRTR, socket.SOCK_DGRAM, 0)
        local = sock.getsockname()
        sock.bind((local[0], 0))
        evidence['local'] = list(sock.getsockname())
        # One absolute observation bound covers send and receive; no retries.
        remaining = seconds - (clock() - started)
        if remaining <= 0:
            raise ValueError('notifier deadline before send')
        sock.settimeout(remaining)
        if sock.sendto(request(), (node, port)) != len(request()):
            raise ValueError('incomplete notifier request send')
        remaining = seconds - (clock() - started)
        if remaining <= 0:
            raise ValueError('notifier deadline after send')
        sock.settimeout(remaining)
        data, peer = sock.recvfrom(256)
        evidence['raw_packets'].append(dict(peer=list(peer), hex=data.hex(),
                                            seconds=clock() - started))
        if peer != (node, port):
            raise ValueError('unexpected notifier peer')
        evidence.update(decode(data))
        if clock() - started > seconds:
            raise ValueError('notifier response exceeded deadline')
        if str(UUID(boot())) != expected_boot:
            raise ValueError('boot changed during notifier query')
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
    parser.add_argument('--domains', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=2)
    args = parser.parse_args()
    try:
        result = query(json.loads(args.inventory.read_text()),
                       json.loads(args.domains.read_text()), args.seconds,
                       expected_boot=args.boot_id)
    except EvidenceError as exc:
        print(json.dumps(exc.evidence, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0 if result['complete'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
