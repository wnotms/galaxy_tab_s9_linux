#!/usr/bin/env python3
"""Bounded native-node QRTR lookup; no QMI method or DSP activation.

Separate from the frozen Test366/369 qrtr-snapshot.py input.
"""
import argparse
import json
from pathlib import Path
import socket
import struct
import time

# Linux 7.2-rc3 include/uapi/linux/qrtr.h and net/qrtr/ns.c:
# five little-endian u32 words; NEW_LOOKUP wildcard, NEW_SERVER all-zero end.
CTRL = 0xfffffffe
NEW_SERVER, NEW_LOOKUP, DEL_LOOKUP = 4, 10, 11


class LookupFault(ValueError):
    def __init__(self, message, raw):
        super().__init__(message)
        self.raw = raw


def packet(command):
    return struct.pack('<5I', command, 0, 0, 0, 0)


def decode(data):
    if len(data) != 20:
        raise ValueError('unexpected QRTR control packet length')
    command, service, instance, node, port = struct.unpack('<5I', data)
    if command != NEW_SERVER:
        raise ValueError('unexpected QRTR lookup command')
    if (service, instance, node, port) == (0, 0, 0, 0):
        return None
    return dict(service=service, instance=instance, node=node, port=port)


def query(seconds=2, *, create=socket.socket, clock=time.monotonic):
    if not 0 < seconds <= 3:
        raise ValueError('bounded lookup only')
    sock = create(socket.AF_QIPCRTR, socket.SOCK_DGRAM, 0)
    rows = []; raw = []; complete = False; local = None
    started = clock()
    try:
        # Linux net/qrtr/af_qrtr.c initializes the socket node before bind;
        # qrtr_bind rejects a different node, including a guessed wildcard0.
        # Read the kernel-assigned node, request an ephemeral port, then retain
        # the actual bound address for nameserver attribution and cleanup.
        node = sock.getsockname()[0]
        sock.bind((node, 0)); local = sock.getsockname()
        peer = (local[0], CTRL)
        sock.sendto(packet(NEW_LOOKUP), peer)
        while len(raw) < 256:
            remaining = seconds - (clock() - started)
            if remaining <= 0:
                break
            sock.settimeout(remaining)
            try:
                data, origin = sock.recvfrom(4096)
            except socket.timeout:
                break
            raw.append(dict(seconds=clock() - started, peer=list(origin), hex=data.hex()))
            if origin != peer:
                raise ValueError('QRTR reply from unexpected nameserver')
            row = decode(data)
            if row is None:
                complete = True
                break
            rows.append(row)
    except Exception as exc:
        raise LookupFault(str(exc), raw) from exc
    finally:
        try:
            if local is not None:
                sock.sendto(packet(DEL_LOOKUP), (local[0], CTRL))
        finally:
            sock.close()
    return dict(complete=complete, services=rows, raw_packets=raw,
                seconds=clock() - started, local=list(local))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--boot-id', required=True)
    parser.add_argument('--seconds', type=float, default=2)
    args = parser.parse_args()
    boot_path = Path('/proc/sys/kernel/random/boot_id')
    before = boot_path.read_text().strip()
    if before.replace('-', '') != args.boot_id.replace('-', ''):
        raise ValueError('boot changed before lookup')
    try:
        result = query(args.seconds)
    except LookupFault as exc:
        print(json.dumps(dict(boot_id=before, complete=False, error=str(exc),
                              raw_packets=exc.raw), indent=2))
        raise SystemExit(2)
    if boot_path.read_text().strip() != before:
        raise ValueError('boot changed during lookup')
    result['boot_id'] = before
    print(json.dumps(result, indent=2))
    if not result['complete']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
