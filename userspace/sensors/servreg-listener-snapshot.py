#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Bounded standard PDR listener cycle on a private QRTR client.

Register once, read the optional initial state, ACK valid indications, unregister
on the same socket, then close. No RPC/DSP start, restart-PD method or retry.
Linux7.2-rc3 pdr_interface.c/pdr_internal.h/qcom_pdr_msg.c define this protocol.
An UP result is not proof of SSC publication, sensor data or rotation.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import socket
import struct
import time
from uuid import UUID

spec = importlib.util.spec_from_file_location('pdr_state_wire', Path(__file__).with_name('servreg-state-snapshot.py'))
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
HEADER, PATH, STATES = S.HEADER, S.PATH, S.STATES
REGISTER, INDICATION, ACK = 0x20, 0x22, 0x23
MAX_PACKETS, MAX_INDICATIONS = 32, 8


def tlv(tag, value):
    return struct.pack('<BH', tag, len(value)) + value


def register(transaction, enable):
    if type(transaction) is not int or not 1 <= transaction <= 65535 or type(enable) is not bool:
        raise ValueError('invalid listener request')
    body = tlv(1, bytes([enable])) + tlv(2, PATH)
    return HEADER.pack(0, transaction, REGISTER, len(body)) + body


def acknowledge(transaction, indication_transaction):
    if (type(transaction) is not int or not 1 <= transaction <= 65535 or
            type(indication_transaction) is not int or not 0 <= indication_transaction <= 65535):
        raise ValueError('invalid indication acknowledgement')
    body = tlv(1, PATH) + tlv(2, struct.pack('<H', indication_transaction))
    return HEADER.pack(0, transaction, ACK, len(body)) + body


def packet(data):
    if len(data) < HEADER.size:
        raise ValueError('truncated QMI header')
    kind, transaction, method, length = HEADER.unpack_from(data)
    if length != len(data) - HEADER.size:
        raise ValueError('QMI payload length mismatch')
    fields, offset = {}, HEADER.size
    while offset < len(data):
        if len(data) - offset < 3:
            raise ValueError('truncated TLV header')
        tag, size = struct.unpack_from('<BH', data, offset); offset += 3
        if tag in fields or size > len(data) - offset:
            raise ValueError('duplicate/truncated TLV')
        fields[tag] = data[offset:offset + size]; offset += size
    return kind, transaction, method, fields


def response(fields, method):
    if set(fields) - ({2, 0x10} if method == REGISTER else {2}) or len(fields.get(2, b'')) != 4:
        raise ValueError('invalid notifier result schema')
    result, error = struct.unpack('<HH', fields[2])
    if result or error:
        raise ValueError(f'notifier failure result={result} error={error}')
    state = None
    if 0x10 in fields:
        if len(fields[0x10]) != 4:
            raise ValueError('invalid current-state length')
        state, = struct.unpack('<I', fields[0x10])
        if state not in STATES:
            raise ValueError('unknown current-state enum')
    return state


def indication(fields):
    if (set(fields) != {1, 2, 3} or len(fields[1]) != 4 or
            fields[2] != PATH or len(fields[3]) != 2):
        raise ValueError('invalid/foreign-domain indication')
    state, = struct.unpack('<I', fields[1])
    transaction, = struct.unpack('<H', fields[3])
    if state not in STATES:
        raise ValueError('unknown indication state')
    return state, transaction


def query(inventory, domains, *, expected_boot, create=socket.socket,
          clock=time.monotonic,
          boot=lambda: Path('/proc/sys/kernel/random/boot_id').read_text().strip()):
    expected_boot = str(UUID(expected_boot))
    node, port = S.endpoint(inventory, domains, expected_boot)
    evidence = dict(boot_id=expected_boot, endpoint=[node, port], service=66,
                    instance=74, domain=PATH.decode(), operation='register/state/ACK/unregister/close',
                    register_seconds=2, cleanup_seconds=2, complete=False,
                    domain_state='UNKNOWN', listener_registered=False,
                    registered_acknowledged=False, unregister_acknowledged=False,
                    socket_closed=False, sent_packets=[], raw_packets=[], indications=[],
                    DSP_started=False, SSC_service_verified=False, accelerometer_verified=False)
    started, sock, registration_sent = clock(), None, False
    pending, replies, seen_indications = {}, {}, set()
    errors = []

    def same_boot():
        if str(UUID(boot())) != expected_boot:
            raise ValueError('boot changed during listener cycle')

    def send(data, deadline):
        nonlocal registration_sent
        same_boot()
        remaining = deadline - clock()
        if remaining <= 0:
            raise ValueError('listener deadline before send')
        sock.settimeout(remaining)
        kind, transaction, method, _ = packet(data)
        pending[transaction] = method
        evidence['sent_packets'].append(dict(transaction=transaction, method=method,
                                             hex=data.hex(), seconds=clock()-started))
        if transaction == 1:
            registration_sent = True
            evidence['listener_registered'] = None
        if sock.sendto(data, (node, port)) != len(data):
            raise ValueError('incomplete listener send')

    def receive(deadline, quiet=False):
        remaining = deadline - clock()
        if remaining <= 0:
            raise ValueError('listener receive deadline')
        sock.settimeout(min(.01, remaining) if quiet else remaining)
        try:
            data, peer = sock.recvfrom(256)
        except socket.timeout:
            if quiet and clock() <= deadline:
                return False
            raise
        evidence['raw_packets'].append(dict(peer=list(peer), hex=data.hex(), seconds=clock()-started))
        if len(evidence['raw_packets']) > MAX_PACKETS:
            raise ValueError('listener packet bound exceeded')
        same_boot()
        if clock() > deadline or peer != (node, port):
            raise ValueError('late/foreign notifier packet')
        kind, transaction, method, fields = packet(data)
        if kind == 4 and method == INDICATION:
            state, tid = indication(fields)
            if tid in seen_indications or len(seen_indications) >= MAX_INDICATIONS:
                raise ValueError('duplicate/excess indication transaction')
            seen_indications.add(tid)
            ack_tid = 3 + len(seen_indications) - 1
            evidence['indications'].append(dict(state_value=state, domain_state=STATES[state],
                                                indication_transaction=tid, ack_transaction=ack_tid))
            send(acknowledge(ack_tid, tid), deadline)
        elif kind == 2 and pending.get(transaction) == method:
            # Keep rejected replies in raw evidence; never turn them into UP.
            del pending[transaction]
            state = response(fields, method)
            replies[transaction] = state
            if transaction == 1:
                evidence.update(registered_acknowledged=True, listener_registered=True)
            elif transaction == 2:
                evidence.update(unregister_acknowledged=True, listener_registered=False)
        else:
            raise ValueError('unexpected/duplicate notifier response')
        return True

    def wait(transaction, deadline):
        while transaction not in replies or any(m == ACK for m in pending.values()):
            receive(deadline)

    try:
        same_boot()
        sock = create(socket.AF_QIPCRTR, socket.SOCK_DGRAM, 0)
        sock.bind((sock.getsockname()[0], 0))
        evidence['local'] = list(sock.getsockname())
        deadline = started + 2
        # A send failure/lost response can leave a remote registration unknown.
        send(register(1, True), deadline)
        wait(1, deadline)
        if replies[1] is None:
            raise ValueError('initial current state absent')
        evidence.update(state_value=replies[1], domain_state=STATES[replies[1]])
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
    finally:
        if sock is not None:
            if registration_sent:
                try:
                    same_boot()
                    deadline = clock() + 2  # Separate bounded cleanup even after register timeout.
                    send(register(2, False), deadline)
                    wait(2, deadline)
                    # Drain already queued indications; ACK each within the same cleanup bound.
                    while receive(deadline, quiet=True):
                        while any(m == ACK for m in pending.values()):
                            receive(deadline)
                    same_boot()
                except (OSError, ValueError) as exc:
                    errors.append('cleanup: ' + str(exc))
            try:
                sock.close(); evidence['socket_closed'] = True
            except OSError as exc:
                errors.append('close: ' + str(exc))
        evidence['seconds'] = clock()-started
    evidence['complete'] = (not errors and evidence['registered_acknowledged'] and
                            evidence['unregister_acknowledged'] and evidence['socket_closed'] and
                            'state_value' in evidence)
    if errors:
        evidence['errors'] = errors
        raise S.EvidenceError('; '.join(errors), evidence)
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--boot-id', required=True)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--domains', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = query(json.loads(args.inventory.read_text()), json.loads(args.domains.read_text()),
                       expected_boot=args.boot_id)
    except S.EvidenceError as exc:
        print(json.dumps(exc.evidence, indent=2)); return 1
    print(json.dumps(result, indent=2))
    return 0 if result['complete'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
